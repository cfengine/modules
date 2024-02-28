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
    """Class pairing the iptables promise (parameter) attribute with its corresponding
    iptables command line parameter arguments

    source => ["-s"]
    protocol => ["-p"]
    priority => ["-m", "comment", "--comment"]
    """

    def __init__(self, attr_name: str, cmdline_parameter_args: str):
        self.attr_name = attr_name
        self.cmdline_args = cmdline_parameter_args.split()


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
    def log_str(self) -> str:
        command = self.attributes.command
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
        Parameter("source", "-s"),
        Parameter("protocol", "-p"),
        Parameter("destination_port", "--dport"),
        Parameter("priority", "-m comment --comment"),
        Parameter("target", "-j"),
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
        super().__init__("iptables_promise_module", "0.2.2", **kwargs)

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

    def validate_promise(self, promiser: str, attributes: dict, metadata: dict):
        command = attributes["command"]

        denied_attrs = self._collect_denied_attributes_of_command(command, attributes)
        if denied_attrs:
            raise ValidationError(
                "Attributes {} are invalid for command '{}'".format(
                    denied_attrs, command
                )
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

    def evaluate_promise(self, promiser: str, attributes: Dict, metadata: Dict):
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
            if command == "policy":
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

    def _iptables_policy(self, executable, table, chain, target):
        assert chain != "ALL"

        self._run([executable, "-t", table, "-P", chain, target])

    def _iptables_flush(self, executable, table, chain):
        args = [executable, "-t", table, "-F"]
        if chain != 'ALL':
            args.append(chain)
        self._run(args)

    def _iptables_all_rules_of(self, executable, table, chain) -> List[str]:
        """The list always starts with a sequence of policy rules followed by a sequence of chain rules.
        If chain is specified then only _one_ policy rule will be on top.
        """
        args = [executable, "-t", table, "-S"]
        if chain != 'ALL':
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
