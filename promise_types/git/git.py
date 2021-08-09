import os
import subprocess

from typing import Dict, List, Optional

from cfengine import PromiseModule, ValidationError, Result

class GitPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super(GitPromiseTypeModule, self).__init__(
            "git_promise_module", "0.1.1", **kwargs
        )

        def destination_must_be_absolute(v):
            if not os.path.isabs(v):
                raise ValidationError(f"must be an absolute path, not '{v}'")

        def depth_must_be_zero_or_more(v):
            if v < 0:
                raise ValidationError(f"must be 0 or more, not '{v}'")

        self.add_attribute("destination", str, default_to_promiser=True, validator=destination_must_be_absolute)
        self.add_attribute("repository", str, required=True)
        self.add_attribute("bare", bool, default=False)
        self.add_attribute("clone", bool, default=True)
        self.add_attribute("depth", int, default=0, validator=depth_must_be_zero_or_more)
        self.add_attribute("executable", str, default="git")
        self.add_attribute("force", bool, default=False)
        self.add_attribute("recursive", bool, default=True)
        self.add_attribute("reference", str)
        self.add_attribute("remote", str, default="origin")
        self.add_attribute("ssh_executable", str, default="ssh")
        self.add_attribute("ssh_options", str)
        self.add_attribute("update", bool, default=True)
        self.add_attribute("version", str, default="HEAD")

    def evaluate_promise(self, promiser: str, attributes: Dict):
        safe_promiser = promiser.replace(",", "_")
        attributes.setdefault("destination", promiser)
        model = self.create_attribute_object(promiser, attributes)

        classes = []
        result = Result.KEPT

        # if the repository doesn't exist
        if not os.path.exists(model.destination):
            if not model.clone:
                return (Result.NOT_KEPT, [f"{safe_promiser}_not_found"])
            try:
                self.log_info(
                    f"Cloning '{model.repository}:{model.version}' to '{model.destination}'"
                )
                clone_options = []
                if model.bare:
                    clone_options += ["--bare"]
                if model.depth:
                    clone_options += [f"--depth={str(model.depth)}"]
                if model.reference:
                    clone_options += ["--reference", model.reference]
                self._git(
                    model,
                    [
                        model.executable,
                        "clone",
                        model.repository,
                        model.destination,
                        "--origin",
                        model.remote,
                        "--branch",
                        model.version,
                    ]
                    + clone_options,
                )
                classes.append(f"{safe_promiser}_cloned")
                result = Result.REPAIRED
            except subprocess.CalledProcessError as e:
                self.log_error(f"Failed clone: {e.output or e}")
                e.stderr and self.log_error(e.stderr.strip())
                return (Result.NOT_KEPT, [f"{safe_promiser}_clone_failed"])

        else:
            # discard local changes to the repository
            if model.force:
                try:
                    output = self._git(
                        model,
                        [model.executable, "status", "--porcelain"],
                        cwd=model.destination,
                    )
                    if output != "":
                        self.log_info(f"Reset '{model.destination}' to HEAD")
                        self._git(
                            model,
                            [model.executable, "reset", "--hard", "HEAD"],
                            cwd=model.destination,
                        )
                        self._git(
                            model,
                            [model.executable, "clean", "-f"],
                            cwd=model.destination,
                        )
                        classes.append(f"{safe_promiser}_reset")
                        result = Result.REPAIRED
                except subprocess.CalledProcessError as e:
                    self.log_error(f"Failed reset: {e.output or e}")
                    e.stderr and self.log_error(e.stderr.strip())
                    return (Result.NOT_KEPT, [f"{safe_promiser}_reset_failed"])

            # Update the repository
            if model.update:
                try:
                    self.log_verbose(
                        f"Fetch '{model.repository}' in '{model.destination}'"
                    )
                    # fetch the remote
                    self._git(
                        model,
                        [model.executable, "fetch", model.remote],
                        cwd=model.destination,
                    )
                    # checkout the branch, if different from the current one
                    output = self._git(
                        model,
                        [model.executable, "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=model.destination,
                    )
                    detached = False
                    if output == "HEAD":
                        detached = True
                        output = self._git(
                            model,
                            [model.executable, "rev-parse", "HEAD"],
                            cwd=model.destination,
                        )
                    if output != model.version:
                        self.log_info(
                            f"Checkout '{model.repository}:{model.version}' in '{model.destination}'"
                        )
                        self._git(
                            model,
                            [model.executable, "checkout", model.version],
                            cwd=model.destination,
                        )
                        result = Result.REPAIRED
                    # check if merge with the remote branch is needed
                    if not detached:
                        output = self._git(
                            model,
                            [
                                model.executable,
                                "diff",
                                f"..{model.remote}/{model.version}",
                            ],
                            cwd=model.destination,
                        )
                        if output != "":
                            self.log_info(
                                f"Merge '{model.remote}/{model.version}' in '{model.destination}'"
                            )
                            self._git(
                                model,
                                [
                                    model.executable,
                                    "merge",
                                    model.remote + "/" + model.version,
                                ],
                                cwd=model.destination,
                            )
                            result = Result.REPAIRED
                    classes.append(f"{safe_promiser}_updated")
                except subprocess.CalledProcessError as e:
                    self.log_error(f"Failed fetch: {e.output or e}")
                    e.stderr and self.log_error(e.stderr.strip())
                    return (Result.NOT_KEPT, [f"{safe_promiser}_update_failed"])

        # everything okay
        return (result, classes)

    def _git(
        self, model: object, args: List[str], cwd: Optional[str] = None
    ) -> str:
        self.log_verbose(f"Run: {' '.join(args)}")
        output = subprocess.check_output(
            args,
            env=self._git_envvars(model),
            cwd=cwd,
            stderr=subprocess.PIPE,
            text=True,
        ).strip()
        output != "" and self.log_verbose(output)
        return output

    def _git_envvars(self, model: object):
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = model.ssh_executable
        if model.ssh_options:
            env["GIT_SSH_COMMAND"] += " " + model.ssh_options
        return env


if __name__ == "__main__":
    GitPromiseTypeModule().start()
