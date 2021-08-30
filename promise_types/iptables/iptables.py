from cfengine import PromiseModule, ValidationError, Result, AttributeObject
from typing import Callable, List, Dict, Tuple
from collections import namedtuple
from copy import deepcopy
from itertools import takewhile
import subprocess

Command = namedtuple("Command", "flag denied_attrs")
Parameter = namedtuple("Parameter", "attr_name flag")


class Model:
    def __init__(
        self,
        attr_obj: AttributeObject,
        *,
        commands: Dict[str, Command],
        parameters: Tuple[Parameter]
    ):
        for k, v in attr_obj.__dict__.items():
            if v is not None:
                setattr(self, k, str(v))
        self._commands = commands
        self._parameters = parameters

    @property
    def rule_spec(self) -> List[str]:
        rule_spec = []
        for param in self._parameters:
            value = getattr(self, param.attr_name, None)
            if value:
                rule_spec.extend([param.flag, value])
        return rule_spec

    @property
    def rule(self) -> List[str]:
        rule = [self._commands[self.command].flag]

        if self.command != "flush" or self.chain != "ALL":
            rule.append(self.chain)

        if self.command == "policy":
            rule.append(self.target)
        else:
            rule.extend(self.rule_spec)

        return rule

    @property
    def args(self) -> List[str]:
        args = [self.executable]
        args.extend(["-t", self.table])
        args.extend(self.rule)
        return args

    @property
    def log_str(self) -> str:
        if self.command in {"append", "insert", "delete"}:
            return "{cmd}-ing rule '{rule}' at chain '{chain}' of table '{table}' {rulenum}".format(
                cmd=self.command.capitalize(),
                rule=" ".join(self.rule),
                chain=self.chain,
                table=self.table,
                rulenum="at position '{}'".format(self.rulenum)
                if getattr(self, "rulenum", None)
                else "",
            )

        elif self.command == "policy":
            return "Setting policy of chain '{chain}' in table '{table}' to '{target}'".format(
                chain=self.chain, table=self.table, target=self.target
            )

        elif self.command == "flush":
            return "Flushing '{}' chain(s)".format(self.chain)

    @staticmethod
    def make_check_command_model(model: "Model") -> "Model":
        check_model = deepcopy(model)
        check_model.command = "check"
        return check_model

    def __repr__(self):
        return "Model({})".format(
            ", ".join("{}={!r}".format(k, v) for k, v in self.__dict__.items())
        )


class IptablesPromiseTypeModule(PromiseModule):
    COMMANDS = {
        "append": Command(
            "-A",
            {
                "rulenum",
            },
        ),
        "insert": Command("-I", set()),
        "delete": Command(
            "-D",
            {
                "rulenum",
            },
        ),
        "policy": Command("-P", {"rulenum", "protocol", "destination_port", "source"}),
        "flush": Command(
            "-F", {"rulenum", "protocol", "destination_port", "source", "target"}
        ),
        "check": Command("-C", None),  # Not directly used by user
    }

    PARAMETERS = (
        Parameter("source", "-s"),
        Parameter(
            "protocol", "-p"
        ),  # Some work on differentiating "sub" options may be necessary (?) (example --dport is a match option for -p tcp)
        Parameter("destination_port", "--dport"),
        Parameter("target", "-j"),
    )

    TABLES = {
        "filter",
    }

    CHAINS = {
        "ALL",
        "INPUT",
        "OUTPUT",
    }

    TARGETS = {
        "ACCEPT",
        "REJECT",
        "DROP",
    }

    def __init__(self, **kwargs):
        super().__init__("iptables_promise_module", "0.1.1", **kwargs)

        # TODO: How much validation required?

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

        def must_be_ip_address(v):
            # if not re.match(..., v):
            #    raise ValidationError("...")
            return

        self.add_attribute(
            "command",
            str,
            required=True,
            validator=must_be_one_of(self.COMMANDS),
        )
        self.add_attribute(
            "table", str, default="filter", validator=must_be_one_of(self.TABLES)
        )
        self.add_attribute("rulenum", int, validator=must_be_positive)
        self.add_attribute(
            "chain", str, required=True, validator=must_be_one_of(self.CHAINS)
        )
        self.add_attribute("protocol", str, validator=must_be_one_of({"tcp", "udp"}))
        self.add_attribute("destination_port", int, validator=must_be_non_negative)
        self.add_attribute("source", str, validator=must_be_ip_address)
        self.add_attribute("target", str, validator=must_be_one_of(self.TARGETS))
        self.add_attribute("executable", str, default="iptables")

    def validate_promise(self, promiser: str, attributes: dict):
        command = attributes["command"]

        present_denied_attrs = self.COMMANDS[command].denied_attrs.intersection(
            attributes
        )
        if present_denied_attrs:
            raise ValidationError(
                "Attributes {} are invalid for command '{}'".format(
                    present_denied_attrs, command
                )
            )

        if command in {"append", "insert", "delete"}:
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

        if command != "flush" and attributes.get("target") == "ALL":
            raise ValidationError(
                "Value 'ALL' for attribute 'chain' is only valid for command 'flush'"
            )

    def evaluate_promise(self, promiser: str, attributes: dict):
        safe_promiser = promiser.replace(",", "_")
        model = Model(
            self.create_attribute_object(promiser, attributes),
            commands=self.COMMANDS,
            parameters=self.PARAMETERS,
        )
        result = Result.NOT_KEPT
        classes = []

        self.log_info(model.log_str)

        if model.command in {"append", "insert", "delete"}:
            self.log_verbose(
                "Checking for rule specification '{}' in chain '{}' of table '{}'".format(
                    " ".join(model.rule_spec), model.chain, model.table
                )
            )

            try:
                self._iptables_check(model)

                self.log_verbose(
                    "Promise to '{}' rule '{}' to chain '{}' of table '{}' already kept".format(
                        model.command,
                        " ".join(model.rule_spec),
                        model.chain,
                        model.table,
                    )
                )

                return Result.KEPT, [
                    "{}_{}_successful".format(safe_promiser, model.command)
                ]
            except subprocess.CalledProcessError as e:
                pass

        else:
            rules = self._iptables_list_rules(model)
            policy_rules = tuple(takewhile(lambda s: s.startswith("-P"), rules))
            chain_rules = rules[len(policy_rules) :]

            if model.command == "policy":
                # Always one item for 'policy' command
                policy_target = policy_rules[0].split()[-1]
                if policy_target == model.target:
                    self.log_verbose(
                        "Promise to set '{}' chain's policy to '{}' already kept".format(
                            model.chain, model.target
                        )
                    )

                    return Result.KEPT, [
                        "{}_{}_successful".format(safe_promiser, model.command)
                    ]

            elif model.command == "flush" and len(chain_rules) == 0:
                self.log_verbose(
                    "Promise to flush '{}' chain(s) already kept".format(model.chain)
                )

                return Result.KEPT, [
                    "{}_{}_successful".format(safe_promiser, model.command)
                ]

        try:
            self._iptables(model)
            result = Result.REPAIRED
            classes.append("{}_{}_successful".format(safe_promiser, model.command))
        except subprocess.CalledProcessError as e:
            if model.command != "delete":
                self.log_error(
                    "Failed command {}: {}".format(e.args[1], e.stderr.decode("utf-8"))
                )

                result = Result.NOT_KEPT
                classes.append("{}_{}_failed".format(safe_promiser, model.command))
            else:
                self.log_verbose(
                    "Promise to 'delete' rule '{}' from chain '{}' of table '{}' already kept".format(
                        " ".join(model.rule_spec), model.chain, model.table
                    )
                )

                result = Result.KEPT
                classes.append("{}_{}_successful".format(safe_promiser, model.command))

        return result, classes

    def _run(self, args: List[str]):
        self.log_verbose("Running command: '{}'".format(args))
        return subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def _iptables_check(self, model: Model):
        check_model = Model.make_check_command_model(model)
        self._run(check_model.args)  # interested in the potential exception

    def _iptables_list_rules(self, model: Model) -> List[str]:
        """The list always starts with a sequence of policy rules followed by a sequence of chain rules"""
        args = [model.executable, "-S"]
        if model.chain != "ALL":
            args.append(model.chain)
        return self._run(args).stdout.decode("utf-8").strip().split("\n")

    def _iptables(self, model: Model):
        return self._run(model.args)


if __name__ == "__main__":
    IptablesPromiseTypeModule().start()
