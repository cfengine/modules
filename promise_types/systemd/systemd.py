import json
import os
import subprocess

from enum import Enum
from typing import Dict, List, Optional, Tuple

from cfengine import PromiseModule, ValidationError, Result
from pydantic import (
    BaseModel,
    ValidationError as PydanticValidationError,
    validator,
)


SYSTEMD_LIB_PATH = "/lib/systemd/system"


class SystemdPromiseTypeStates(Enum):
    RELOADED = "reloaded"
    RESTARTED = "restarted"
    STARTED = "started"
    STOPPED = "stopped"
    ABSENT = "absent"


class SystemdPromiseTypeModel(BaseModel):
    daemon_reexec: bool = False
    daemon_reload: bool = False
    enabled: bool = True
    masked: bool = False
    name: str
    replace: bool = True
    state: str
    unit_description: Optional[str]
    unit_requires: List[str] = []
    unit_wants: List[str] = []
    unit_after: List[str] = []
    unit_before: List[str] = []
    unit_extra: List[str] = []
    service_type: Optional[str]
    service_pid_file: Optional[str]
    service_user: Optional[str]
    service_group: Optional[str]
    service_nice: Optional[int]
    service_oom_score_adjust: Optional[int]
    service_exec_start: List[str] = []
    service_exec_start_pre: List[str] = []
    service_exec_start_post: List[str] = []
    service_exec_stop: List[str] = []
    service_exec_stop_post: List[str] = []
    service_exec_reload: List[str] = []
    service_restart: Optional[str]
    service_restart_sec: Optional[str]
    service_timeout_sec: Optional[str]
    service_environment: List[str] = []
    service_environment_file: Optional[str]
    service_working_directory: Optional[str]
    service_standard_input: Optional[str]
    service_standard_output: Optional[str]
    service_standard_error: Optional[str]
    service_tty_path: Optional[str]
    service_extra: List[str] = []
    install_wanted_by: List[str] = []
    install_required_by: List[str] = []
    install_extra: List[str] = []

    @validator("state")
    def state_must_be_valid(cls, v):
        if v not in (
            SystemdPromiseTypeStates.RELOADED.value,
            SystemdPromiseTypeStates.RESTARTED.value,
            SystemdPromiseTypeStates.STARTED.value,
            SystemdPromiseTypeStates.STOPPED.value,
            SystemdPromiseTypeStates.ABSENT.value,
        ):
            raise ValueError("invalid value")
        return v


class SystemdPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super(SystemdPromiseTypeModule, self).__init__(
            "systemd_promise_module", "0.1.0", **kwargs
        )

    def validate_promise(self, promiser: str, attributes: Dict):
        attributes.setdefault("name", promiser)
        if type(attributes.get("environment")) == str:
            attributes["environment"] = json.loads(attributes["environment"])
        try:
            SystemdPromiseTypeModel(**attributes)
        except PydanticValidationError as e:
            errors = [
                ".".join(map(str, err["loc"])) + ": " + err["msg"] for err in e.errors()
            ]
            raise ValidationError(", ".join(errors))

    def evaluate_promise(
        self, promiser: str, attributes: Dict
    ) -> Tuple[str, List[str]]:
        safe_promiser = promiser.replace(",", "_")
        attributes.setdefault("name", promiser)
        if type(attributes.get("environment")) == str:
            attributes["environment"] = json.loads(attributes["environment"])
        model = SystemdPromiseTypeModel(**attributes)
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
            self.log_error(f"Failed to run systemctl: {e.output or e}")
            e.stderr and self.log_error(e.stderr.strip())
            return (Result.NOT_KEPT, [f"{safe_promiser}_show_failed"])
        # apply the changes
        if model.state == SystemdPromiseTypeStates.ABSENT.value:
            return self._service_absent(model, safe_promiser, service_status)
        else:
            return self._service_present(model, safe_promiser, service_status)

    def _service_absent(
        self, model: SystemdPromiseTypeModel, safe_promiser: str, service_status: dict
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
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_stop_failed"])
            self.log_info(f"Stopped the service {model.name}")
        # disable the service, in case it is enabled
        if service_status["ActiveState"] == "active":
            try:
                self._exec_command(["systemctl", "disable", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_disable_failed"])
            self.log_info(f"Disabled the service {model.name}")
        # remove the service file
        path = os.path.join(SYSTEMD_LIB_PATH, f"{model.name}.service")
        if os.path.exists(path):
            try:
                os.unlink(path)
                result = Result.REPAIRED
            except OSError as e:
                self.log_error(f"Failed to remove the service file: {e}")
                return (Result.NOT_KEPT, [f"{safe_promiser}_remove_failed"])
            self.log_info(f"Removed the service {model.name}")
        # reload systemctl, if needed
        if result == Result.REPAIRED:
            try:
                self._exec_command(["systemctl", "daemon-reload"])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_daemon_reload_failed"])
            self.log_info(f"Reloaded the list of services")
            classes.append(f"{safe_promiser}_absent")
        return (result, classes)

    def _service_present(
        self, model: SystemdPromiseTypeModel, safe_promiser: str, service_status: dict
    ) -> Tuple[str, List[str]]:
        classes = []
        result = Result.KEPT
        # render the template of the service
        service_template = self._render_service_template(model)
        # create the service file if it doesn't exist, or replace it if the content
        # doesn't match our template and replace is true
        service_path = os.path.join(SYSTEMD_LIB_PATH, f"{model.name}.service")
        try:
            if (
                not os.path.exists(service_path)
                or model.replace
                and open(service_path).read() != service_template
            ):
                open(service_path, "w").write(service_template)
                result = Result.REPAIRED
                self.log_info(f"Installed the service {model.name}")
                classes.append(f"{safe_promiser}_installed")
        except OSError as e:
            self.log_error(f"Failed to install the service file: {e}")
            return (Result.NOT_KEPT, [f"{safe_promiser}_install_failed"])
        # run systemctl daemon-reexec
        if model.daemon_reexec:
            try:
                self._exec_command(["systemctl", "daemon-reexec"])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_daemon_reexec_failed"])
            self.log_info("Executed systemctl daemon-reexec")
            classes.append(f"{safe_promiser}_daemon_reexec")
        # run systemctl daemon-reload
        elif result == Result.REPAIRED or model.daemon_reload:
            try:
                self._exec_command(["systemctl", "daemon-reload"])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_daemon_reload_failed"])
            self.log_info("Executed systemctl daemon-reload")
            classes.append(f"{safe_promiser}_daemon_reload")
        # mask the service
        if model.masked and service_status["UnitFileState"] != "masked":
            try:
                self._exec_command(["systemctl", "mask", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_mask_failed"])
            self.log_info(f"Masked the service {model.name}")
            classes.append(f"{safe_promiser}_masked")
        # unmask the service
        elif not model.masked and service_status["UnitFileState"] == "masked":
            try:
                self._exec_command(["systemctl", "unmask", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_unmask_failed"])
            self.log_info(f"Unmasked the service {model.name}")
            classes.append(f"{safe_promiser}_unmasked")
        # enable the service
        if (
            model.enabled
            and not model.masked
            and service_status["UnitFileState"] != "enabled"
        ):
            try:
                self._exec_command(["systemctl", "enable", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_enable_failed"])
            self.log_info(f"Enabled the service {model.name}")
            classes.append(f"{safe_promiser}_enabled")
        # disable the service
        elif (
            not model.enabled
            and not model.masked
            and service_status["UnitFileState"] == "enabled"
        ):
            try:
                self._exec_command(["systemctl", "disable", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_disable_failed"])
            self.log_info(f"Disabled the service {model.name}")
            classes.append(f"{safe_promiser}_disabled")
        # start the service, if not running
        if model.state == SystemdPromiseTypeStates.STARTED.value and not (
            service_status["ActiveState"] == "active"
            and service_status["SubState"] == "running"
        ):
            try:
                self._exec_command(["systemctl", "start", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_start_failed"])
            self.log_info(f"Started the service {model.name}")
            classes.append(f"{safe_promiser}_started")
        # stop the service, if running
        elif (
            model.state == SystemdPromiseTypeStates.STOPPED.value
            and service_status["ActiveState"] == "active"
            and service_status["SubState"] == "running"
        ):
            try:
                self._exec_command(["systemctl", "stop", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_stop_failed"])
            self.log_info(f"Stopped the service {model.name}")
            classes.append(f"{safe_promiser}_stopped")
        # reload the service
        elif model.state == SystemdPromiseTypeStates.RELOADED.value:
            try:
                self._exec_command(["systemctl", "reload", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_reload_failed"])
            self.log_info(f"Reloaded the service {model.name}")
            classes.append(f"{safe_promiser}_reloaded")
        # restart the service
        elif model.state == SystemdPromiseTypeStates.RESTARTED.value:
            try:
                self._exec_command(["systemctl", "restart", model.name])
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed to run systemctl: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_restart_failed"])
            self.log_info(f"Restarted the service {model.name}")
            classes.append(f"{safe_promiser}_restarted")
        return (result, classes)

    def _exec_command(self, args: List[str], cwd: Optional[str] = None) -> str:
        self.log_verbose(f"Run: {' '.join(args)}")
        output = subprocess.check_output(
            args, cwd=cwd, stderr=subprocess.PIPE, text=True,
        ).strip()
        output != "" and self.log_verbose(output)
        return output

    def _render_service_template(self, model: SystemdPromiseTypeModel) -> str:
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
                    blocks[block].append(f"{key}={item}")
            else:
                blocks[block].append(f"{key}={str(value)}")
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
            f"# Rendered by CFEngine. Do not edit directly\n\n"
            + f"[Unit]\n{unit_section}\n\n"
            + f"[Service]\n{service_section}\n\n"
            + f"[Install]\n{install_section}\n"
        )


if __name__ == "__main__":
    SystemdPromiseTypeModule().start()
