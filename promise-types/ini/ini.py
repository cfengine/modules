"""A CFEngine custom promise module for INI files"""

import json
import subprocess
import sys

from cfengine import PromiseModule, ValidationError, Result


class AnsiballINIModule(PromiseModule):
    def __init__(self):
        super().__init__("ansible_ini_promise_module", "0.0.1")

        self.add_attribute("path", str, default_to_promiser=True)

    def validate_attributes(self, promiser, attributes, meta):
        # Just pass the attributes on transparently to Ansible INI The Ansible
        # module will report if the missing parameters are not in Ansible attributes

        return True

    def validate_promise(self, promiser: str, attributes: dict, meta: dict) -> None:
        self.log_error(
            "Validating the ansible ini promise: %s %s %s"
            % (promiser, attributes, meta)
        )
        if not meta.get("promise_type"):
            raise ValidationError("Promise type not specified")

        assert meta.get("promise_type") == "ini"

    def evaluate_promise(self, promiser: str, attributes: dict, meta: dict):
        self.log_error(
            "Evaluating the ansible ini promise %s, %s, %s"
            % (promiser, attributes, meta)
        )

        if "module_path" not in attributes:
            attributes.setdefault(
                "module_path",
                "/tmp/ini_file.py",
            )

        # NOTE: INI module specific - should not be passed on to Ansible
        module_path = attributes["module_path"]
        del attributes["module_path"]

        # NOTE - needed because 'default_to_promiser' is not respected
        attributes.setdefault("path", promiser)

        self.log_error(
            "Evaluating the ansible ini promise %s, %s, %s"
            % (promiser, attributes, meta)
        )

        proc = subprocess.run(
            [
                "python",
                module_path,
            ],
            input=json.dumps({"ANSIBLE_MODULE_ARGS": attributes}).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not proc:
            self.log_error("Failed to run the ansible module")
            return (
                Result.NOT_KEPT,
                [],
            )

        if proc.returncode != 0:
            self.log_error("Failed to run the ansible module")
            self.log_error("Ansible INI module returned(stdout): %s" % proc.stdout)
            self.log_error("Ansible INI module returned(stderr): %s" % proc.stderr)
            return (
                Result.NOT_KEPT,
                [],
            )

        self.log_debug("Received output: %s (stdout)" % proc.stdout)
        self.log_debug("Received output: (stderr): %s" % proc.stderr)

        try:
            d = json.loads(proc.stdout.decode("UTF-8").strip())
            if d.get("changed", False):
                self.log_info(
                    "Edited content of '%s' (%s)" % (promiser, d.get("msg", ""))
                )
        except Exception as e:
            self.log_error(
                "Failed to decode the JSON returned from the Ansible INI module. Error: %s"
                % e
            )
            return (Result.NOT_KEPT, [])

        return (
            Result.KEPT,
            [],
        )


if __name__ == "__main__":
    AnsiballINIModule().start()
