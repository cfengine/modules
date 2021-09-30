"""
This module attempts to follow the naming conventions of iptables
as they are in `man iptables`
"""

from cfengine import PromiseModule, ValidationError, Result, AttributeObject
from typing import Callable, List, Dict, Tuple
from collections import namedtuple
from itertools import takewhile, dropwhile
import subprocess


def is_policy_rule(rule: str):
    return rule.startswith("-P")


class IptablesError(Exception):
    pass


Command = namedtuple("Command", "flag denied_attrs")


class Parameter:
    """Class that holds the format string for an iptables parameter.
    The constructor format string assumes:
      * That one value will be used for all format brackets and the brackets are empty.
    Examples:
    Parameter("source", "-s {}").cmdline_args("1.2.3.4") -> ["-s", "1.2.3.4"]
    Parameter("protocol", "-p {} -m {}").cmdline_args("tcp") -> ["-p", "tcp", "-m", "tcp"]
    """

    def __init__(self, attr_name: str, fmt: str):
        self.attr_name = attr_name
        self._fmt = fmt.replace("{}", "{0}")

    def cmdline_args(self, value: str) -> List[str]:
        return self._fmt.format(value).split()


class Model:
    def __init__(
        self,
        attr_obj: AttributeObject,
        *,
        commands: Dict[str, Command],
        parameters: Tuple[Parameter, ...]
    ):
        self.attributes = attr_obj
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
        for param in self._parameters:
            value = getattr(self.attributes, param.attr_name, None)
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
    def log_str(self) -> str:
        command = self.attributes.command
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

        return "Command '{}' has no log string".format(command)

    def __repr__(self):
        return "Model({})".format(
            ", ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items())
        )


class IptablesPromiseTypeModule(PromiseModule):
    # The `COMMANDS` dict pairs the command name with a Command object containing its iptables flag and a
    # set of promise attributes it does *not* accept. The latter is used during `validate_promise` to
    # catch any unwanted attributes.
    COMMANDS = {
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
            {"protocol", "destination_port", "source", "priority", "rules", "target"},
        ),
    }

    # The `PARAMETERS` tuple contains the sequence of parameters the model goes through when creating
    # its rule specification. The order of parameters in the sequence *matters*.
    # "protocol" must precede "destination_port" and "target" must be last.
    PARAMETERS = (
        Parameter("source", "-s {}"),
        Parameter("protocol", "-p {} -m {}"),
        Parameter("destination_port", "--dport {}"),
        Parameter("priority", "-m comment --comment {}"),
        Parameter("target", "-j {}"),
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

        def must_be_one_of(items) -> Callable:
            def validator(v):
                if v not in items:
                    raise ValidationError(
                        "Attribute value '{}' is not valid. Available values are: {}".format(
                            v, items
                        )
                    )

            return validator

        def must_be_positive(v):
            if v <= 0:
                raise ValidationError("Value must be greater or equal to 1")

        def must_be_non_negative(v):
            if v < 0:
                raise ValidationError("Value must be greater or equal to 0")

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
        self.add_attribute("priority", int, default=0)
        self.add_attribute("rules", dict)
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

        if command == "delete":
            if attributes.get("destination_port") and not attributes.get("protocol"):
                raise ValidationError(
                    "Attribute 'destination_port' needs 'protocol' present"
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
            if command == "delete":
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

            else:
                raise NotImplementedError(command)

        except IptablesError as e:
            self.log_error(e)
            result = Result.NOT_KEPT

        if result == Result.NOT_KEPT:
            classes.append("{}_{}_failed".format(safe_promiser, command))
        elif result in {Result.KEPT, Result.REPAIRED}:
            result == Result.REPAIRED and self.log_info(model.log_str)

            classes.append("{}_{}_successful".format(safe_promiser, command))
        else:
            classes.append("{}_{}_unknown".format(safe_promiser, command))

        return result, classes

    def evaluate_command_delete(self, executable, table, chain, rule_spec: List[str]):
        if not self._iptables_check(executable, table, chain, rule_spec):
            self.log_verbose(
                "Promise to delete rule '-A {} {}' from table '{}' already kept".format(
                    chain, rule_spec, table
                )
            )

            return Result.KEPT

        self._iptables_delete(executable, table, chain, rule_spec)
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

    def evaluate_command_flush(self, executable, table, chain):
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

    def _run(self, args: List[str]) -> List[str]:
        self.log_verbose("Running command: '{}'".format(args))

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

    def _iptables_delete(self, executable, table, chain, rule_spec: List[str]):
        assert chain != "ALL"

        self._run([executable, "-t", table, "-D", chain] + rule_spec)

    def _iptables_policy(self, executable, table, chain, target):
        assert chain != "ALL"

        self._run([executable, "-t", table, "-P", chain, target])

    def _iptables_flush(self, executable, table, chain):
        args = [executable, "-t", table, "-F"]
        if chain != "ALL":
            args.append(chain)
        self._run(args)

    def _iptables_check(self, executable, table, chain, rule_spec: List[str]) -> bool:
        try:
            self._run([executable, "-t", table, "-C", chain] + rule_spec)
            return True
        except IptablesError as e:
            return False

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

    def _collect_denied_attributes_of_command(self, command, attributes: dict) -> set:
        return self.COMMANDS[command].denied_attrs.intersection(attributes)


if __name__ == "__main__":
    IptablesPromiseTypeModule().start()
