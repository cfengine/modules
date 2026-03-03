import os

from typing import Dict, Tuple, List
from cfengine_module_library import PromiseModule, ValidationError, Result

try:
    import ansible.context as context
    from ansible.cli import CLI
    from ansible.executor.playbook_executor import PlaybookExecutor
    from ansible.inventory.manager import InventoryManager
    from ansible.module_utils.common.collections import ImmutableDict
    from ansible.parsing.dataloader import DataLoader
    from ansible.plugins.callback import CallbackBase
    from ansible.vars.manager import VariableManager
    from ansible.plugins.loader import init_plugin_loader

    class CallbackModule(CallbackBase):
        CALLBACK_VERSION = 1.0
        CALLBACK_TYPE = "stdout"
        CALLBACK_NAME = "cfengine"

        def __init__(self, *args, promise, **kw):
            self.promise = promise
            self.hosts = set()
            self.changed = False
            super(CallbackModule, self).__init__(*args, **kw)

        def v2_runner_on_start(self, host, task):
            self.hosts.add(str(host))
            self.promise.log_verbose(
                "Task '" + task.name + "' started on '" + str(host) + "'"
            )

        def v2_runner_on_ok(self, result):
            is_changed = result.is_changed()
            if is_changed:
                self.changed = True
                self.promise.log_info(
                    "Task '" + result.task_name + "' successfully changed"
                )
            else:
                self.promise.log_verbose(
                    "Task '" + result.task_name + "' didn't change"
                )

        def v2_runner_on_failed(self, result, ignore_errors=False):
            self.promise.log_error("Task '" + result.task_name + "' failed")

        def v2_runner_on_skipped(self, result):
            self.promise.log_error("Task '" + result.task_name + "' was skipped")

        def v2_playbook_on_stats(self, stats):
            for host in self.hosts:
                summary_dict = stats.summarize(host)
                summary = " ".join(
                    "%s=%s" % (k, v) for k, v in summary_dict.items() if v > 0
                )
                if summary_dict.get("unreachable"):
                    self.promise.log_error("Host '" + host + "' is unreachable")
                elif summary:
                    self.promise.log_verbose(
                        "Summary of the tasks for '" + host + "' is: " + summary
                    )

    class AnsiblePromiseTypeModule(PromiseModule):
        def __init__(self, **kwargs):
            super(AnsiblePromiseTypeModule, self).__init__(
                "ansible_promise_module", "0.0.0", **kwargs
            )

            def must_be_absolute(v):
                if not os.path.isabs(v):
                    raise ValidationError(
                        "Must be an absolute path, not '{v}'".format(v=v)
                    )

            self.add_attribute(
                "playbook", str, default_to_promiser=True, validator=must_be_absolute
            )
            self.add_attribute("inventory", str, validator=must_be_absolute)
            self.add_attribute("limit", list, default=["localhost"])
            self.add_attribute("tags", list, default=[])
            self.add_attribute("become", bool, default=False)
            self.add_attribute("become_method", str, default="sudo")
            self.add_attribute("become_user", str, default="root")
            self.add_attribute("connection", str, default="local")
            self.add_attribute("forks", int, default=1)
            self.add_attribute("private_key_file", str, validator=must_be_absolute)
            self.add_attribute("remote_user", str, default="root")

        def prepare_promiser_and_attributes(self, promiser, attributes):
            safe_promiser = promiser.replace(",", "_")
            return (safe_promiser, attributes)

        def validate_promise(self, promiser: str, attributes: Dict, metadata: Dict):
            return

        def evaluate_promise(
            self, safe_promiser: str, attributes: Dict, metadata: Dict
        ) -> Tuple[str, List[str]]:
            model = self.create_attribute_object(safe_promiser, attributes)

            classes = []
            result = Result.KEPT

            context.CLIARGS = ImmutableDict(
                tags=model.tags,
                listtags=False,
                listtasks=False,
                listhosts=False,
                syntax=False,
                connection=model.connection,
                module_path=None,
                remote_user=model.remote_user,
                private_key_file=model.private_key_file,
                ssh_common_args=None,
                ssh_extra_args=None,
                sftp_extra_args=None,
                scp_extra_args=None,
                become=model.become,
                become_method=model.become_method,
                become_user=model.become_user,
                forks=model.forks,
                verbosity=0,
                check=False,
                start_at_task=None,
            )

            loader = DataLoader()
            inventory = InventoryManager(
                loader=loader,
                sources=(model.inventory,) if model.inventory else (),
            )

            variable_manager = VariableManager(
                loader=loader,
                inventory=inventory,
                version_info=CLI.version_info(gitinfo=False),
            )
            pbex = PlaybookExecutor(
                playbooks=[attributes["playbook"]],
                inventory=inventory,
                variable_manager=variable_manager,
                loader=loader,
                passwords={},
            )
            callback = CallbackModule(promise=self)
            pbex._tqm._stdout_callback = callback  # type: ignore

            exit_code = pbex.run()
            if exit_code != 0:
                classes.append(
                    "{safe_promiser}_failed".format(safe_promiser=safe_promiser)
                )
                result = Result.NOT_KEPT
            elif callback.changed:
                result = Result.REPAIRED

            return (result, classes)

    if __name__ == "__main__":
        init_plugin_loader()
        AnsiblePromiseTypeModule().start()

except ModuleNotFoundError:

    class UnavailableAnsiblePromiseTypeModule(PromiseModule):

        def __init__(self, **kwargs):
            super(UnavailableAnsiblePromiseTypeModule, self).__init__(
                "ansible_promise_module", "0.0.0", **kwargs
            )

        def validate_promise(self, promiser: str, attributes: Dict, metadata: Dict):
            raise ValidationError("Ansible Python module not available")

    if __name__ == "__main__":
        UnavailableAnsiblePromiseTypeModule().start()
