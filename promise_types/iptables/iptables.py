"""
This module attempts to follow the naming conventions of iptables
as they are in `man iptables`
"""

from cfengine import PromiseModule, ValidationError, Result, AttributeObject
from typing import Callable, List, Dict, Tuple
from collections import namedtuple
from itertools import takewhile, dropwhile, groupby
from operator import attrgetter
from copy import copy
from collections import OrderedDict
from enum import Enum
import sys
import ipaddress
import re
import subprocess


def iptables_enumerate(iterable):
    return enumerate(iterable, start=1)


def is_policy_rule(rule: str):
    return rule.startswith("-P")


def rule_spec_in_rules(rule_spec: List[str], rules: Tuple[str, ...]) -> bool:
    rule_spec_str = " ".join(rule_spec)
    return any(rule_spec_str in rule for rule in rules)


def rule_spec_in_rule(rule_spec: List[str], rule: str):
    return " ".join(rule_spec) in rule


RULE_PRIORITY_STR = "CF3:priority:"


def rule_priority(rule: str) -> str:
    """Regex group matches CF3:priority: followed by an integer, potentially enclosed in double quotes"""
    match = re.search(
        r'-m comment --comment "?{}(-?\d+)"?'.format(RULE_PRIORITY_STR), rule
    )
    return match.group(1) if match else ""


def rule_spec_priority(rule_spec: List[str]):
    return rule_priority(" ".join(rule_spec))


def process_source(source: str) -> str:
    """Iptables presents the ips masked therefore any source should be postprocessed to what
    iptables presents in order to be able to match it during evaluation.
    Examples:
    1.2.3.4 -> 1.2.3.4/32
    1.2.3.4/24 -> 1.2.3.0/24
    """
    ip_int = ipaddress.ip_interface(source)
    mask = int(ip_int.netmask)
    ip = int(ip_int.ip)
    new_ip_address = ipaddress.ip_address(ip & mask)
    return "{}/{}".format(new_ip_address, bin(mask).count("1"))


class IptablesError(Exception):
    pass


class IndexRulePair(namedtuple("IndexRulePair", "index rule")):
    def rule_contains_rule_spec(self, rule_spec: List[str]):
        return rule_spec_in_rule(rule_spec, self.rule)


class RuleBlocks(OrderedDict):
    """Map priorities to tuples of IndexRulePairs.
    Tracking the index of the rule individualy is necessary in order to know
    where to insert later. All this is necessary because iptables doesnt have index lookup...

    The indexes of the IndexRulePairs are always in ascending order.
    Example:
    For packet rules:
    -A INPUT -s 1.2.3.4/32 -m comment --comment "CF3:priority:5" -j ACCEPT
    -A INPUT -p tcp -m tcp --dport 22 -m comment --comment "CF3:priority:6" -j ACCEPT
    -A INPUT -p tcp -m tcp --dport 23 -m comment --comment "CF3:priority:6" -j DROP
    -A INPUT -s 5.6.7.8/32 -m comment --comment "CF3:priority:-1" -j DROP

    RuleBlocks -> {
        "5": ( IndexRulePair(index=1, rule="-s 1.2.3.4/32 -m comment --comment "CF3:priority:5" -j ACCEPT"), ),
        "6": (
               IndexRulePair(index=2, rule="-p tcp -m tcp --dport 22 -m comment --comment "CF3:priority:6" -j ACCEPT"),
               IndexRulePair(index=3, rule="-p tcp -m tcp --dport 23 -m comment --comment "CF3:priority:6" -j DROP")
             ),
        "-1": ( IndexRulePair(index=4, rule="-s 5.6.7.8/32 -m comment --comment "CF3:priority:-1" -j DROP"), )
    }

    Any rules added externally to the chain that do not conform to the "CF3:priority:XX" (where XX is -1 or >=1)
    are filtered out and may cause fragmentation.
    """

    def __init__(self, rules: List[str]):
        super().__init__()
        data = (
            (priority, tuple(IndexRulePair(index, rule) for index, rule in grouping))
            for priority, grouping in groupby(
                iptables_enumerate(rules), key=lambda pair: rule_priority(pair[1])
            )
        )

        def validate_data_pair(pair: Tuple[str, Tuple[IndexRulePair, ...]]) -> bool:
            priority = pair[0]
            if priority == "":
                return False
            priority = int(priority)
            return priority == -1 or priority >= 1

        data = filter(validate_data_pair, data)  # Ignore non cfe added rules

        for priority, pairs in data:
            self.setdefault(priority, []).extend(pairs)

    def index_of_rule_spec_in_priority_block(self, priority: str, rule_spec: List[str]):
        """Find index of rule containing `rule_spec` or return the index after the last one."""
        if len(self) == 0:
            return 1

        for pair in self[priority]:
            if pair.rule_contains_rule_spec(rule_spec):
                return pair.index
        else:
            return pair.index + 1

    def index_of_first_rule_with_priority_ge(self, required_priority: str) -> int:
        """May return the index of a present rule or the index of where a rule would be, meaning
        after the last rule
        """
        if len(self) == 0:
            return 1

        items = map(
            lambda kv: (int(kv[0]) if kv[0] != "-1" else sys.maxsize, kv[1]),
            self.items(),
        )

        required_priority = int(required_priority)

        for priority, pairs in items:
            if priority == required_priority:
                return pairs[-1].index + 1
            elif priority > required_priority:
                return pairs[0].index
        else:
            return pairs[-1].index + 1

    def rule_spec_is_in_priority_block(
        self, priority: str, rule_spec: List[str]
    ) -> bool:
        return any(pair.rule_contains_rule_spec(rule_spec) for pair in self[priority])

    def __repr__(self):
        return "RuleBlocks{{{}}}".format(
            ", ".join("{!r}: {!r}".format(k, v) for k, v in self.items())
        )


class Parameter:
    """Class that holds the format string for an iptables parameter.
    The constructor format string assumes:
      * That one value will be used for all format brackets and the brackets are empty.
    Examples:
    Parameter("-s {}").cmdline_args("1.2.3.4") -> ["-s", "1.2.3.4"]
    Parameter("-p {} -m {}").cmdline_args("tcp") -> ["-p", "tcp", "-m", "tcp"]
    """

    def __init__(self, fmt: str):
        self._fmt = fmt.replace("{}", "{0}")

    def cmdline_args(self, value: str) -> List[str]:
        return self._fmt.format(value).split()


class CheckResult(Enum):
    IN = "in table"
    NOT_IN = "not in table"


Command = namedtuple("Command", "flag denied_attrs")


class Model:
    def __init__(
        self,
        attr_obj: AttributeObject,
        *,
        commands: Dict[str, Command],
        parameters: OrderedDict
    ):
        self.attributes = self._postprocess_attributes(attr_obj)
        self._commands = commands
        self._parameters = parameters

    @property
    def rule_spec(self) -> List[str]:
        """A rule spec is the sequence of "parameters" after the chain argument
        Examples for a couple of promises:

        iptables:
            "delete_accept_cfengine"
              command => "delete",
              chain => "INPUT",
              source => "34.107.174.45",
              target => "ACCEPT";

        model.rule_spec -> ['-s', '34.107.174.45', '-j', 'ACCEPT']

        iptables:
            "delete_accept_cfengine"
              command => "append",
              chain => "INPUT",
              protocol => "tcp",
              destination_port => "22"
              target => "ACCEPT";

        model.rule_spec -> ['-p', 'tcp', '-m', 'tcp', '--dport', '22', '-j', 'ACCEPT']
        """
        rule_spec = []
        for attr_name, param in self._parameters.items():
            value = getattr(self.attributes, attr_name, None)
            if value:
                rule_spec.extend(param.cmdline_args(value))
        return rule_spec

    @property
    def rule(self) -> List[str]:
        """A rule starts from the command flag.
        Examples for a couple of promises:

        iptables:
            "delete_accept_cfengine"
              command => "delete",
              chain => "INPUT",
              source => "34.107.174.45",
              target => "ACCEPT";

        model.rule -> ['-D', 'INPUT', -s', '34.107.174.45', '-j', 'ACCEPT']

        iptables:
            "delete_accept_cfengine"
              command => "append",
              chain => "INPUT",
              protocol => "tcp",
              destination_port => "22"
              target => "ACCEPT";

        model.rule -> ['-A', 'INPUT', '-p', 'tcp', '-m', 'tcp', '--dport', '22', '-j', 'ACCEPT']
        """
        command = self.attributes.command
        rule = [self._commands[command].flag]
        if command != "flush" or self.attributes.chain != "ALL":
            rule.append(self.attributes.chain)
        if command == "policy":
            rule.append(self.attributes.target)
        else:
            rule.extend(self.rule_spec)
        return rule

    @property
    def exclusive_rule_specs(self) -> List[List[str]]:
        rule_specs = []
        for spec in self.attributes.rules["rule_specs"].values():
            rule_spec = []
            for attr_name, param in self._parameters.items():
                value = spec.get(attr_name)
                if value:
                    rule_spec.extend(param.cmdline_args(value))
            rule_specs.append(rule_spec)
        return rule_specs

    @property
    def log_str(self) -> str:
        command = self.attributes.command
        if command == "append":
            return "Appending rule '{rule}' on table '{table}'".format(
                rule=" ".join(self.rule), table=self.attributes.table
            )
        if command == "insert":
            return "Inserting rule '{rule}' on table '{table}' with priority '{priority}'".format(
                rule=" ".join(self.rule),
                table=self.attributes.table,
                priority=self.attributes.priority,
            )
        if command == "delete":
            return "Deleting rule '{rule}' from table '{table}'".format(
                rule=" ".join(self.rule),
                table=self.attributes.table,
            )
        if command == "policy":
            return "Setting policy of chain '{chain}' in table '{table}' to '{target}'".format(
                chain=self.attributes.chain,
                table=self.attributes.table,
                target=self.attributes.target,
            )
        if command == "flush":
            return "Flushing '{}' chain(s) in table '{}'".format(
                self.attributes.chain, self.attributes.table
            )
        if command == "exclusive":
            return "Ensuring only rules with rule_specs {rule_specs} are present in '{chain}' of table '{table}'".format(
                rule_specs=self.attributes.rules["rule_specs"],
                chain=self.attributes.chain,
                table=self.attributes.table,
            )
        return "Command '{}' has no log string".format(command)

    def _postprocess_attributes(self, attr_obj: AttributeObject) -> AttributeObject:
        attributes = copy(attr_obj)

        priority = getattr(attributes, "priority", None)
        if not priority:
            if attributes.command == "append":
                # All appended rules have priority -1, validation will ensure priority is None here
                attributes.priority = -1
            elif attributes.command == "insert":
                # If priority is not specified for insert rules are put at the top block
                attributes.priority = 1

        # Process source strings to what iptables presents when listing rules
        if attributes.command == "exclusive":
            attributes.rules.setdefault("rule_specs", {})
            for specs in attributes.rules["rule_specs"].values():
                source = specs.get("source")
                if source:
                    specs["source"] = process_source(source)
        elif getattr(attributes, "source", None):
            attributes.source = process_source(attributes.source)

        return attributes

    def __repr__(self):
        return "Model({})".format(
            ", ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items())
        )


class IptablesPromiseTypeModule(PromiseModule):
    # The `COMMANDS` dict pairs the command name with a Command object containing its iptables flag and a
    # set of promise attributes it does *not* accept. The latter is used during `validate_promise` to
    # catch any unwanted attributes.
    COMMANDS = {
        "append": Command("-A", {"priority", "rules"}),
        "insert": Command(
            "-I",
            {
                "rules",
            },
        ),
        "delete": Command(
            "-D",
            {
                "rules",
            },
        ),
        "policy": Command(
            "-P", {"protocol", "destination_port", "source", "priority", "rules"}
        ),
        "flush": Command(
            "-F",
            {
                "protocol",
                "destination_port",
                "source",
                "priority",
                "rules",
                "target",
            },
        ),
        "exclusive": Command(
            None,
            {"protocol", "destination_port", "source", "priority", "target"},
        ),
    }

    # The `PARAMETERS` OrderedDict contains the sequence of parameters the model goes through when creating
    # its rule specification. The order of parameters in the sequence *matters*.
    # "protocol" must precede "destination_port" and "target" must be last.
    PARAMETERS = OrderedDict(
        (
            ("source", Parameter("-s {}")),
            ("protocol", Parameter("-p {} -m {}")),
            ("destination_port", Parameter("--dport {}")),
            # Rule specs (and rules) will be created by surrounding the priority string with quotes just like
            # they would have been typed on the terminal.
            # > iptables -A INPUT -m comment --comment "CF3:priority:-1" -j ACCEPT
            # > iptables -S INPUT
            # -P INPUT ACCEPT
            # -A INPUT -m comment --comment "CF3:priority:-1" -j ACCEPT
            #
            # However this is a problem for subprocess because it will surround them with double quotes again leading to:
            # -A INPUT -m comment --comment "\"CF3:priority:-1\"" -j ACCEPT.
            # Just as convention its chosen to not spread validation around but keep a simple sanitising function
            # at the very end of appending/inserting rules
            (
                "priority",
                Parameter('-m comment --comment "{}{{}}"'.format(RULE_PRIORITY_STR)),
            ),
            ("target", Parameter("-j {}")),
        )
    )

    # Below are sets of accepted values for the promise. They are used as arguments of the `must_be_one_of`
    # validator that is used in the promise's constructor.

    TABLES = {
        "filter",
    }

    CHAINS = {
        "ALL",
        "INPUT",
        "FORWARD",
        "OUTPUT",
    }

    PROTOCOLS = {"tcp", "udp"}

    TARGETS = {
        "ACCEPT",
        "REJECT",
        "DROP",
    }

    def __init__(self, **kwargs):
        super().__init__("iptables_promise_module", "0.1.1", **kwargs)

        # Validators
        #
        def must_be_one_of(items) -> Callable:
            def validator(v):
                if v not in items:
                    raise ValidationError(
                        "Attribute value '{}' is not valid. Available values are: {}".format(
                            v, sorted(items)
                        )
                    )

            return validator

        def must_be_positive(v):
            if v <= 0:
                raise ValidationError("Value must be greater or equal to 1")

        def must_be_non_negative(v):
            if v < 0:
                raise ValidationError("Value must be greater or equal to 0")

        def must_be_minus_one_or_positive(v):
            if v != -1 and v < 1:
                raise ValidationError("Value must be '-1' or greater than 0")

        def keys_must_only_be_table_chain_rule_specs(v: dict):
            # TODO: If we want to be pedantic/safe we should do the same same
            # type validation done on the promise in general.

            # 'table' and 'chain' arent used by 'exclusive' but allowing them in the dictionary
            # can help the user keep relevant data close together. See test.cf
            denied_keys = set(v).difference({"table", "chain", "rule_specs"})
            if denied_keys:
                raise ValidationError(
                    "Dictionary for attribute 'rules' contains denied keys {}".format(
                        denied_keys
                    )
                )

            denied_params_per_rule = {}
            if "rule_specs" not in v:
                raise ValidationError(
                    "At least key 'rule_specs' must be present in 'rules' attribute data"
                )

            rule_specs = v["rule_specs"]
            if not isinstance(rule_specs, dict):
                raise ValidationError("Value of 'rule_specs' must be a dictionary")
            if not rule_specs:
                self.log_warning(
                    "Empty 'rule_specs' will flush the entire chain, consider using the 'flush' command instead"
                )

            for rule_name, rule_specs in rule_specs.items():
                denied_params = set(rule_specs).difference(self.PARAMETERS)
                if denied_params:
                    denied_params_per_rule[rule_name] = denied_params

            if denied_params_per_rule:
                raise ValidationError(
                    "Invalid parameters for rule_specs in rules: {}".format(
                        denied_params_per_rule
                    )
                )

        #
        # ------------------------------------

        self.add_attribute(
            "command",
            str,
            required=True,
            # Unfortunate validator argument but otherwise 'dict_keys(...)' as output
            validator=must_be_one_of(tuple(self.COMMANDS.keys())),
        )
        self.add_attribute(
            "table", str, default="filter", validator=must_be_one_of(self.TABLES)
        )
        self.add_attribute(
            "chain", str, required=True, validator=must_be_one_of(self.CHAINS)
        )
        self.add_attribute("protocol", str, validator=must_be_one_of(self.PROTOCOLS))
        self.add_attribute("destination_port", int, validator=must_be_non_negative)
        self.add_attribute("source", str)
        self.add_attribute("target", str, validator=must_be_one_of(self.TARGETS))
        self.add_attribute("priority", int, validator=must_be_minus_one_or_positive)
        self.add_attribute(
            "rules", dict, validator=keys_must_only_be_table_chain_rule_specs
        )
        self.add_attribute("executable", str, default="iptables")

    def validate_promise(self, promiser: str, attributes: dict):
        command = attributes["command"]

        denied_attrs = self._collect_denied_attributes_of_command(command, attributes)
        if denied_attrs:
            raise ValidationError(
                "Attributes {} are invalid for command '{}'".format(
                    denied_attrs, command
                )
            )

        if command in {"delete", "append", "insert"}:
            if attributes.get("destination_port") and not attributes.get("protocol"):
                raise ValidationError(
                    "Attribute 'destination_port' needs 'protocol' present"
                )
            if command == "insert":
                priority = attributes.get("priority")
                if priority and priority < 1:
                    raise ValidationError(
                        "Command 'insert' only accepts 'priority' >=1"
                    )

        if command == "policy":
            target = attributes.get("target")
            if not target:
                raise ValidationError("Command 'policy' requires 'target' attribute")
            if target not in {"ACCEPT", "DROP"}:
                raise ValidationError(
                    "The 'target' for the 'policy' command must be either 'ACCEPT' or 'DROP'"
                )

        if command != "flush" and attributes.get("chain") == "ALL":
            raise ValidationError("Chain 'ALL' is only available for command 'flush'")

    def evaluate_promise(self, promiser: str, attributes: dict):
        safe_promiser = promiser.replace(",", "_")

        model = Model(
            self.create_attribute_object(promiser, attributes),
            commands=self.COMMANDS,
            parameters=self.PARAMETERS,
        )

        attrs = model.attributes
        command = model.attributes.command

        result = Result.NOT_KEPT
        classes = []

        try:
            if command == "append":
                result = self.evaluate_command_append(
                    attrs.executable, attrs.table, attrs.chain, model.rule_spec
                )

            elif command == "insert":
                result = self.evaluate_command_insert(
                    attrs.executable, attrs.table, attrs.chain, model.rule_spec
                )

            elif command == "delete":
                result = self.evaluate_command_delete(
                    attrs.executable, attrs.table, attrs.chain, model.rule_spec
                )

            elif command == "policy":
                result = self.evaluate_command_policy(
                    attrs.executable, attrs.table, attrs.chain, attrs.target
                )

            elif command == "flush":
                result = self.evaluate_command_flush(
                    attrs.executable, attrs.table, attrs.chain
                )

            elif command == "exclusive":
                result = self.evaluate_command_exclusive(
                    attrs.executable,
                    attrs.table,
                    attrs.chain,
                    model.exclusive_rule_specs,
                )

            else:
                raise NotImplementedError(
                    "Command '{}' not implemented".format(command)
                )

        except (IptablesError, NotImplementedError) as e:
            self.log_error(e)
            result = Result.NOT_KEPT

        except Exception as e:
            self.log_error("Unexpected '{}' occured: {}".format(type(e).__name__, e))
            result = Result.NOT_KEPT

        finally:
            if result == Result.NOT_KEPT:
                classes.append("{}_{}_failed".format(safe_promiser, command))
            elif result in {Result.KEPT, Result.REPAIRED}:
                result == Result.REPAIRED and self.log_info(model.log_str)

                classes.append("{}_{}_successful".format(safe_promiser, command))
            else:
                classes.append("{}_{}_unknown".format(safe_promiser, command))

            return result, classes

    # --------------------------------
    #      Evaluation Functions
    # --------------------------------

    def evaluate_command_insert(
        self, executable, table, chain, rule_spec: List[str]
    ) -> Result:
        check_result, index = self._iptables_check_insert(
            executable, table, chain, rule_spec
        )
        if check_result == CheckResult.IN:
            self.log_verbose(
                "Promise to insert rule '-A {} {}' to table '{}' at position '{}' already kept".format(
                    chain, " ".join(rule_spec), table, index
                )
            )

            return Result.KEPT

        self._iptables_insert(
            executable,
            table,
            chain,
            index,
            rule_spec,
        )
        return Result.REPAIRED

    def evaluate_command_append(
        self, executable, table, chain, rule_spec: List[str]
    ) -> Result:
        """
        CAUTION: UNSTABLE
        -----------------

        Randomly the '-C' command fails to see the rule in the table. Cause unknown.
        Debugging shows that the command run by ``self._run`` is correct syntactically.
        Perhaps a problem outside this module?
        """
        check_result = self._iptables_check_append(executable, table, chain, rule_spec)
        if check_result == CheckResult.IN:
            self.log_verbose(
                "Promise to append rule '-A {} {}' to table '{}' already kept".format(
                    chain, " ".join(rule_spec), table
                )
            )

            return Result.KEPT

        self._iptables_append(
            executable,
            table,
            chain,
            rule_spec,
        )
        return Result.REPAIRED

    def evaluate_command_delete(
        self, executable, table, chain, rule_spec: List[str]
    ) -> Result:
        if (
            self._iptables_check(executable, table, chain, rule_spec)
            == CheckResult.NOT_IN
        ):
            self.log_verbose(
                "Promise to delete rule '-A {} {}' from table '{}' already kept".format(
                    chain, rule_spec, table
                )
            )

            return Result.KEPT

        self._iptables_delete_rule_spec(executable, table, chain, rule_spec)
        return Result.REPAIRED

    def evaluate_command_policy(self, executable, table, chain, target) -> Result:
        policy_rules = self._iptables_policy_rules_of(executable, table, chain)
        assert len(policy_rules) == 1 and len(policy_rules[0].split()) >= 1

        policy_target = policy_rules[0].split()[-1]
        if policy_target == target:
            self.log_verbose(
                "Promise to set '{}' policy in chain '{}' of table '{}' already kept".format(
                    target, chain, table
                )
            )

            return Result.KEPT

        self._iptables_policy(executable, table, chain, target)
        return Result.REPAIRED

    def evaluate_command_flush(self, executable, table, chain) -> Result:
        packet_rules = self._iptables_packet_rules_of(executable, table, chain)
        if len(packet_rules) == 0:
            self.log_verbose(
                "Promise to flush '{}' chain(s) of table '{}' already kept".format(
                    chain, table
                )
            )

            return Result.KEPT

        self._iptables_flush(executable, table, chain)
        return Result.REPAIRED

    def evaluate_command_exclusive(
        self, executable, table, chain, exclusive_rule_specs: List[List[str]]
    ) -> Result:
        denied_rule_indexes = self._iptables_check_exclusive(
            executable, table, chain, exclusive_rule_specs
        )
        if not denied_rule_indexes:
            self.log_verbose(
                "Promise to ensure rule exclusivity in chain '{}' of table '{}'".format(
                    chain, table
                )
            )

            return Result.KEPT

        for index in reversed(denied_rule_indexes):  # Reverse to keep indexes valid
            self._iptables_delete_index(executable, table, chain, index)
        return Result.REPAIRED

    # ----------------------------------------
    #      Primary iptables interface
    # ----------------------------------------

    def _run(self, args: List[str]) -> List[str]:
        self.log_verbose("Running command: '{}'".format(" ".join(args)))

        try:
            return (
                subprocess.run(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                .stdout.decode("utf-8")
                .strip()
                .split("\n")
            )
        except subprocess.CalledProcessError as e:
            raise IptablesError(e) from e

    def _sanitize_rule_spec_for_addition_command(
        self, rule_spec: List[str]
    ) -> List[str]:
        """Sanitize rule spec by removing the double quotes surrounding the priority comment.
        Subprocess puts extra double qoutes on the arguments by default.
        See "priority" parameter in IptablesPromiseTypeModule.PARAMETERS doc above.
        """

        assert rule_priority(
            " ".join(rule_spec)
        ), "Every rule appended/inserted must have a priority"

        rule_spec = copy(rule_spec)
        priority_i = rule_spec.index("--comment") + 1
        rule_spec[priority_i] = rule_spec[priority_i].replace('"', "")

        return rule_spec

    def _iptables_append(
        self,
        executable,
        table,
        chain,
        rule_spec: List[str],
    ):
        assert chain != "ALL"
        rule_spec = self._sanitize_rule_spec_for_addition_command(rule_spec)

        self._run([executable, "-t", table, "-A", chain] + rule_spec)

    def _iptables_insert(self, executable, table, chain, index, rule_spec: List[str]):
        assert chain != "ALL", "'insert' does not accept 'ALL' as chain"
        rule_spec = self._sanitize_rule_spec_for_addition_command(rule_spec)

        self._run([executable, "-t", table, "-I", chain, index] + rule_spec)

    def _iptables_delete_rule_spec(
        self, executable, table, chain, rule_spec: List[str]
    ):
        assert chain != "ALL", "'delete' does not accept 'ALL' as chain"

        self._run([executable, "-t", table, "-D", chain] + rule_spec)

    def _iptables_delete_index(self, executable, table, chain, index: str):
        assert chain != "ALL", "'delete' does not accept 'ALL' as chain"

        self._run([executable, "-t", table, "-D", chain, index])

    def _iptables_policy(self, executable, table, chain, target):
        assert chain != "ALL", "'policy' does not accept 'ALL' as chain"

        self._run([executable, "-t", table, "-P", chain, target])

    def _iptables_flush(self, executable, table, chain):
        args = [executable, "-t", table, "-F"]
        if chain != "ALL":
            args.append(chain)
        self._run(args)

    # -------------------------------
    #       Iptables utilities
    # -------------------------------

    def _iptables_check(
        self, executable, table, chain, rule_spec: List[str]
    ) -> CheckResult:
        try:
            self._run([executable, "-t", table, "-C", chain] + rule_spec)
            return CheckResult.IN
        except IptablesError as e:
            return CheckResult.NOT_IN

    def _iptables_check_append(
        self, executable, table, chain, rule_spec: List[str]
    ) -> CheckResult:
        """Check if rule_spec is in the proper rule block (with priority "-1") in the chain.
        Appended rules should be found together at the end of the chain in a sequence.
        """
        required_priority = rule_spec_priority(rule_spec)
        assert required_priority == "-1", "'append' only accepts priority '-1'"

        rules = self._iptables_packet_rules_of(executable, table, chain)
        result = CheckResult.NOT_IN
        rule_blocks = RuleBlocks(rules)
        required_block = rule_blocks.get(required_priority)

        if required_block:
            rule_spec_in_block = rule_blocks.rule_spec_is_in_priority_block(
                required_priority, rule_spec
            )

            result = CheckResult.IN if rule_spec_in_block else CheckResult.NOT_IN

        return result

    def _iptables_check_insert(
        self, executable, table, chain, rule_spec: List[str]
    ) -> Tuple[CheckResult, str]:
        """Return information of whether the rule is in the chain and an index (of where to insert, or where it is)
        Note: returned indexes start from 1, just like iptables.
        Algorithm:
        * Find priority block
          --> No block found return: NOT_IN, index_of_insertion
        * Check if rule_spec in block
          --> rule_spec IN block return: IN, index_of_position
          --> rule_spec NOT IN block return: NOT INT, index_of_insertion

        This does not take into account outside actors adding rules to the table, and will
        result in fragmentation depending on how external rules are added.
        """
        required_priority = rule_spec_priority(rule_spec)
        assert int(required_priority) >= 1, "'insert' only accepts priority >=1"

        rules = self._iptables_packet_rules_of(executable, table, chain)
        result = CheckResult.NOT_IN
        return_index = None
        rule_blocks = RuleBlocks(rules)

        required_block = rule_blocks.get(required_priority)
        if not required_block:
            result = CheckResult.NOT_IN
            return_index = rule_blocks.index_of_first_rule_with_priority_ge(
                required_priority
            )
        else:
            rule_spec_in_block = rule_blocks.rule_spec_is_in_priority_block(
                required_priority, rule_spec
            )

            result = CheckResult.IN if rule_spec_in_block else CheckResult.NOT_IN
            return_index = rule_blocks.index_of_rule_spec_in_priority_block(
                required_priority, rule_spec
            )

        return result, str(return_index)

    def _iptables_check_exclusive(
        self, executable, table, chain, rule_specs: List[List[str]]
    ) -> Tuple[str, ...]:
        """Return a tuple of indexes of rules that must be deleted (no spec from rule_specs argument can be found in any of them)"""
        rules_with_indexes = iptables_enumerate(
            self._iptables_packet_rules_of(executable, table, chain)
        )
        denied_rules_with_indexes = filter(
            lambda pair: not any(
                rule_spec_in_rule(rule_spec, pair[1]) for rule_spec in rule_specs
            ),
            rules_with_indexes,
        )
        denied_indexes = map(lambda pair: str(pair[0]), denied_rules_with_indexes)
        return tuple(denied_indexes)

    def _iptables_all_rules_of(self, executable, table, chain) -> List[str]:
        """The list always starts with a sequence of policy rules followed by a sequence of chain rules.
        If chain is specified then only _one_ policy rule will be on top.
        """
        args = [executable, "-t", table, "-S"]
        if chain != "ALL":
            args.append(chain)
        return self._run(args)

    def _iptables_policy_rules_of(self, executable, table, chain) -> Tuple[str, ...]:
        rules = self._iptables_all_rules_of(executable, table, chain)
        return tuple(takewhile(is_policy_rule, rules))

    def _iptables_packet_rules_of(self, executable, table, chain) -> Tuple[str, ...]:
        rules = self._iptables_all_rules_of(executable, table, chain)
        return tuple(dropwhile(is_policy_rule, rules))

    # --------------------------
    #      Misc Utilities
    # --------------------------

    def _collect_denied_attributes_of_command(self, command, attributes: dict) -> set:
        return self.COMMANDS[command].denied_attrs.intersection(attributes)


if __name__ == "__main__":
    IptablesPromiseTypeModule().start()
