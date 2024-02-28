import json
import os
import subprocess

from enum import Enum
from typing import Dict, List, Optional, Tuple

from cfengine import PromiseModule, ValidationError, Result


SYSTEMD_LIB_PATH = "/lib/systemd/system"


class SystemdPromiseTypeStates(Enum):
    RELOADED = "reloaded"
    RESTARTED = "restarted"
    STARTED = "started"
    STOPPED = "stopped"
    ABSENT = "absent"


class SystemdPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super(SystemdPromiseTypeModule, self).__init__(
            "systemd_promise_module", "0.2.2", **kwargs
        )

        def state_must_be_valid(v):
            if v not in (
                SystemdPromiseTypeStates.RELOADED.value,
                SystemdPromiseTypeStates.RESTARTED.value,
                SystemdPromiseTypeStates.STARTED.value,
                SystemdPromiseTypeStates.STOPPED.value,
                SystemdPromiseTypeStates.ABSENT.value,
            ):
                raise ValueError("invalid value")
            return v

        self.add_attribute("daemon_reexec", bool, default=False)
        self.add_attribute("daemon_reload", bool, default=False)
        self.add_attribute("enabled", bool, default=True)
        self.add_attribute("masked", bool, default=False)
        self.add_attribute("name", str, required=True, default_to_promiser=True)
        self.add_attribute("replace", bool, default=True)
        self.add_attribute("state", str, required=True, validator=state_must_be_valid)
        self.add_attribute("unit_description", str)
        self.add_attribute("unit_requires", list, default=[])
        self.add_attribute("unit_wants", list, default=[])
        self.add_attribute("unit_after", list, default=[])
        self.add_attribute("unit_before", list, default=[])
        self.add_attribute("unit_extra", list, default=[])
        self.add_attribute("service_type", str)
        self.add_attribute("service_pid_file", str)
        self.add_attribute("service_user", str)
        self.add_attribute("service_group", str)
        self.add_attribute("service_nice", int)
        self.add_attribute("service_oom_score_adjust", int)
        self.add_attribute("service_exec_start", list, default=[])
        self.add_attribute("service_exec_start_pre", list, default=[])
        self.add_attribute("service_exec_start_post", list, default=[])
        self.add_attribute("service_exec_stop", list, default=[])
        self.add_attribute("service_exec_stop_post", list, default=[])
        self.add_attribute("service_exec_reload", list, default=[])
        self.add_attribute("service_restart", str)
        self.add_attribute("service_restart_sec", str)
        self.add_attribute("service_timeout_sec", str)
        self.add_attribute("service_environment", list, default=[])
        self.add_attribute("service_environment_file", str)
        self.add_attribute("service_working_directory", str)
        self.add_attribute("service_standard_input", str)
        self.add_attribute("service_standard_output", str)
        self.add_attribute("service_standard_error", str)
        self.add_attribute("service_tty_path", str)
        self.add_attribute("service_extra", list, default=[])
        self.add_attribute("install_wanted_by", list, default=[])
        self.add_attribute("install_required_by", list, default=[])
        self.add_attribute("install_extra", list, default=[])

    def prepare_promiser_and_attributes(self, promiser, attributes):
        safe_promiser = promiser.replace(",", "_")
        return (safe_promiser, attributes)

    def evaluate_promise(
        self, safe_promiser: str, attributes: Dict, metadata: Dict
    ) -> Tuple[str, List[str]]:
        model = self.create_attribute_object(safe_promiser, attributes)
        # get the status of the service
        try:
            output = self._exec_command(
                [
                    "systemctl",
                    "show",
                    model.name,
                    "-p",
                    "ActiveState",
                    "-p",
                    "SubState",
                    "-p",
                    "UnitFileState",
                ]
            )
            service_status = dict(k.split("=", 1) for k in output.strip().splitlines())
        except subprocess.CalledProcessError as e:
            self.log_error(
                "Failed to run systemctl: {error}".format(error=e.output or e)
            )
            e.stderr and self.log_error(e.stderr.strip())
            return (
                Result.NOT_KEPT,
                ["{safe_promiser}_show_failed".format(safe_promiser=safe_promiser)],
            )
        # apply the changes
        if model.state == SystemdPromiseTypeStates.ABSENT.value:
            return self._service_absent(model, safe_promiser, service_status)
        else:
            return self._service_present(model, safe_promiser, service_status)

    def _service_absent(
        self, model: object, safe_promiser: str, service_status: dict
    ) -> Tuple[str, List[str]]:
        classes = []
        result = Result.KEPT
        # stop the service, in case it is running
        if (
            service_status["ActiveState"] == "active"
            and service_status["SubState"] == "running"
        ):
            try:
                self._exec_command(["systemctl", "stop", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    ["{safe_promiser}_stop_failed".format(safe_promiser=safe_promiser)],
                )
            self.log_info(
                "Stopped the service {model_name}".format(model_name=model.name)
            )
        # disable the service, in case it is enabled
        if service_status["ActiveState"] == "active":
            try:
                self._exec_command(["systemctl", "disable", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_disable_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Disabled the service {model_name}".format(model_name=model.name)
            )
        # remove the service file
        path = os.path.join(
            SYSTEMD_LIB_PATH, "{model_name}.service".format(model_name=model.name)
        )
        if os.path.exists(path):
            try:
                os.unlink(path)
                result = Result.REPAIRED
            except OSError as e:
                self.log_error(
                    "Failed to remove the service file: {error}".format(error=e)
                )
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_remove_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Removed the service {model_name}".format(model_name=model.name)
            )
        # reload systemctl, if needed
        if result == Result.REPAIRED:
            try:
                self._exec_command(["systemctl", "daemon-reload"])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_daemon_reload_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info("Reloaded the list of services")
            classes.append("{safe_promiser}_absent".format(safe_promiser=safe_promiser))
        return (result, classes)

    def _service_present(
        self, model: object, safe_promiser: str, service_status: dict
    ) -> Tuple[str, List[str]]:
        classes = []
        result = Result.KEPT
        # render the template of the service
        service_template = self._render_service_template(model)
        # create the service file if it doesn't exist, or replace it if the content
        # doesn't match our template and replace is true
        service_path = os.path.join(
            SYSTEMD_LIB_PATH, "{model_name}.service".format(model_name=model.name)
        )
        try:
            if (
                not os.path.exists(service_path)
                or model.replace
                and open(service_path).read() != service_template
            ):
                open(service_path, "w").write(service_template)
                result = Result.REPAIRED
                self.log_info(
                    "Installed the service {model_name}".format(model_name=model.name)
                )
                classes.append(
                    "{safe_promiser}_installed".format(safe_promiser=safe_promiser)
                )
        except OSError as e:
            self.log_error(
                "Failed to install the service file: {error}".format(error=e)
            )
            return (
                Result.NOT_KEPT,
                ["{safe_promiser}_install_failed".format(safe_promiser=safe_promiser)],
            )
        # run systemctl daemon-reexec
        if model.daemon_reexec:
            try:
                self._exec_command(["systemctl", "daemon-reexec"])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_daemon_reexec_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info("Executed systemctl daemon-reexec")
            classes.append(
                "{safe_promiser}_daemon_reexec".format(safe_promiser=safe_promiser)
            )
        # run systemctl daemon-reload
        elif result == Result.REPAIRED or model.daemon_reload:
            try:
                self._exec_command(["systemctl", "daemon-reload"])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_daemon_reload_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info("Executed systemctl daemon-reload")
            classes.append(
                "{safe_promiser}_daemon_reload".format(safe_promiser=safe_promiser)
            )
        # mask the service
        if model.masked and service_status["UnitFileState"] != "masked":
            try:
                self._exec_command(["systemctl", "mask", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    ["{safe_promiser}_mask_failed".format(safe_promiser=safe_promiser)],
                )
            self.log_info(
                "Masked the service {model_name}".format(model_name=model.name)
            )
            classes.append("{safe_promiser}_masked".format(safe_promiser=safe_promiser))
        # unmask the service
        elif not model.masked and service_status["UnitFileState"] == "masked":
            try:
                self._exec_command(["systemctl", "unmask", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_unmask_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Unmasked the service {model_name}".format(model_name=model.name)
            )
            classes.append(
                "{safe_promiser}_unmasked".format(safe_promiser=safe_promiser)
            )
        # enable the service
        if (
            model.enabled
            and not model.masked
            and service_status["UnitFileState"] != "enabled"
        ):
            try:
                self._exec_command(["systemctl", "enable", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_enable_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Enabled the service {model_name}".format(model_name=model.name)
            )
            classes.append(
                "{safe_promiser}_enabled".format(safe_promiser=safe_promiser)
            )
        # disable the service
        elif (
            not model.enabled
            and not model.masked
            and service_status["UnitFileState"] == "enabled"
        ):
            try:
                self._exec_command(["systemctl", "disable", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_disable_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Disabled the service {model_name}".format(model_name=model.name)
            )
            classes.append(
                "{safe_promiser}_disabled".format(safe_promiser=safe_promiser)
            )
        # start the service, if not running
        if model.state == SystemdPromiseTypeStates.STARTED.value and not (
            service_status["ActiveState"] == "active"
            and service_status["SubState"] == "running"
        ):
            try:
                self._exec_command(["systemctl", "start", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_start_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Started the service {model_name}".format(model_name=model.name)
            )
            classes.append(
                "{safe_promiser}_started".format(safe_promiser=safe_promiser)
            )
        # stop the service, if running
        elif (
            model.state == SystemdPromiseTypeStates.STOPPED.value
            and service_status["ActiveState"] == "active"
            and service_status["SubState"] == "running"
        ):
            try:
                self._exec_command(["systemctl", "stop", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    ["{safe_promiser}_stop_failed".format(safe_promiser=safe_promiser)],
                )
            self.log_info(
                "Stopped the service {model_name}".format(model_name=model.name)
            )
            classes.append(
                "{safe_promiser}_stopped".format(safe_promiser=safe_promiser)
            )
        # reload the service
        elif model.state == SystemdPromiseTypeStates.RELOADED.value:
            try:
                self._exec_command(["systemctl", "reload", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_reload_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Reloaded the service {model_name}".format(model_name=model.name)
            )
            classes.append(
                "{safe_promiser}_reloaded".format(safe_promiser=safe_promiser)
            )
        # restart the service
        elif model.state == SystemdPromiseTypeStates.RESTARTED.value:
            try:
                self._exec_command(["systemctl", "restart", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(
                    "Failed to run systemctl: {error}".format(error=e.output or e)
                )
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_restart_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )
            self.log_info(
                "Restarted the service {model_name}".format(model_name=model.name)
            )
            classes.append(
                "{safe_promiser}_restarted".format(safe_promiser=safe_promiser)
            )
        return (result, classes)

    def _exec_command(self, args: List[str], cwd: Optional[str] = None) -> str:
        self.log_verbose("Run: {cmd}".format(cmd=" ".join(args)))
        output = (
            subprocess.check_output(args, cwd=cwd, stderr=subprocess.PIPE)
            .strip()
            .decode("utf-8")
        )
        output != "" and self.log_verbose(output)
        return output

    def _render_service_template(self, model: object) -> str:
        blocks = {
            "unit": [],
            "service": [],
            "install": [],
        }
        for block, attr, key in (
            ("unit", "unit_description", "Description"),
            ("unit", "unit_requires", "Requires"),
            ("unit", "unit_wants", "Wants"),
            ("service", "service_type", "Type"),
            ("service", "service_pid_file", "PIDFile"),
            ("service", "service_user", "User"),
            ("service", "service_group", "Group"),
            ("service", "service_nice", "Nice"),
            ("service", "service_oom_score_adjust", "OOMScoreAdjust"),
            ("service", "service_exec_start", "ExecStart"),
            ("service", "service_exec_start_pre", "ExecStartPre"),
            ("service", "service_exec_start_post", "ExecStartPost"),
            ("service", "service_exec_stop", "ExecStop"),
            ("service", "service_exec_stop_post", "ExecStopPost"),
            ("service", "service_exec_reload", "ExecReload"),
            ("service", "service_restart", "Restart"),
            ("service", "service_restart_sec", "RestartSec"),
            ("service", "service_timeout_sec", "TimeoutStartSec"),
            ("service", "service_environment", "Environment"),
            ("service", "service_environment_file", "EnvironmentFile"),
            ("service", "service_working_directory", "WorkingDirectory"),
            ("service", "service_standard_input", "StandardInput"),
            ("service", "service_standard_output", "StandardOutput"),
            ("service", "service_standard_error", "StandardError"),
            ("service", "service_tty_path", "TTYPath"),
            ("install", "install_wanted_by", "WantedBy"),
            ("install", "install_required_by", "RequiredBy"),
        ):
            value = getattr(model, attr)
            if value is None:
                continue
            elif type(value) == list:
                for item in value:
                    blocks[block].append("{key}={item}".format(key=key, item=item))
            else:
                blocks[block].append("{key}={value}".format(key=key, value=value))
        #
        if model.unit_extra:
            blocks["unit"].extend(model.unit_extra)
        unit_section = "\n".join(blocks["unit"])
        #
        if model.service_extra:
            blocks["unit"].extend(model.service_extra)
        service_section = "\n".join(blocks["service"])
        #
        if model.install_extra:
            blocks["unit"].extend(model.install_extra)
        install_section = "\n".join(blocks["install"])
        #
        return (
            "# Rendered by CFEngine. Do not edit directly\n\n"
            + "[Unit]\n{unit_section}\n\n".format(unit_section=unit_section)
            + "[Service]\n{service_section}\n\n".format(service_section=service_section)
            + "[Install]\n{install_section}\n".format(install_section=install_section)
        )


if __name__ == "__main__":
    SystemdPromiseTypeModule().start()
