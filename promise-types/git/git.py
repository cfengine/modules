import os
import subprocess

from typing import Dict, List, Optional

from cfengine import PromiseModule, ValidationError, Result


class GitPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super(GitPromiseTypeModule, self).__init__(
            "git_promise_module", "0.2.3", **kwargs
        )

        def destination_must_be_absolute(v):
            if not os.path.isabs(v):
                raise ValidationError("must be an absolute path, not '{v}'".format(v=v))

        def depth_must_be_zero_or_more(v):
            if v < 0:
                raise ValidationError("must be 0 or more, not '{v}'".format(v=v))

        self.add_attribute(
            "destination",
            str,
            default_to_promiser=True,
            validator=destination_must_be_absolute,
        )
        self.add_attribute("repository", str, required=True)
        self.add_attribute("bare", bool, default=False)
        self.add_attribute("clone", bool, default=True)
        self.add_attribute(
            "depth", int, default=0, validator=depth_must_be_zero_or_more
        )
        self.add_attribute("executable", str, default="git")
        self.add_attribute("force", bool, default=False)
        self.add_attribute("recursive", bool, default=True)
        self.add_attribute("reference", str)
        self.add_attribute("remote", str, default="origin")
        self.add_attribute("ssh_executable", str, default="ssh")
        self.add_attribute("ssh_options", str)
        self.add_attribute("update", bool, default=True)
        self.add_attribute("version", str, default="HEAD")

    def evaluate_promise(self, promiser: str, attributes: Dict, metadata: Dict):
        safe_promiser = promiser.replace(",", "_")
        attributes.setdefault("destination", promiser)
        model = self.create_attribute_object(promiser, attributes)

        classes = []
        result = Result.KEPT

        # if the repository doesn't exist
        if not os.path.exists(model.destination):
            if not model.clone:
                return (
                    Result.NOT_KEPT,
                    ["{safe_promiser}_not_found".format(safe_promiser=safe_promiser)],
                )
            try:
                self.log_info(
                    "Cloning '{repository}:{version}' to '{destination}'".format(
                        repository=model.repository,
                        version=model.version,
                        destination=model.destination,
                    )
                )
                clone_options = []
                if model.bare:
                    clone_options += ["--bare"]
                if model.depth:
                    clone_options += ["--depth={depth}".format(depth=model.depth)]
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
                classes.append(
                    "{safe_promiser}_cloned".format(safe_promiser=safe_promiser)
                )
                result = Result.REPAIRED
            except subprocess.CalledProcessError as e:
                self.log_error("Failed clone: {error}".format(error=e.output or e))
                e.stderr and self.log_error(e.stderr.strip())
                return (
                    Result.NOT_KEPT,
                    [
                        "{safe_promiser}_clone_failed".format(
                            safe_promiser=safe_promiser
                        )
                    ],
                )

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
                        self.log_info(
                            "Reset '{destination}' to HEAD".format(
                                destination=model.destination
                            )
                        )
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
                        classes.append(
                            "{safe_promiser}_reset".format(safe_promiser=safe_promiser)
                        )
                        result = Result.REPAIRED
                except subprocess.CalledProcessError as e:
                    self.log_error("Failed reset: {error}".format(error=e.output or e))
                    e.stderr and self.log_error(e.stderr.strip())
                    return (
                        Result.NOT_KEPT,
                        [
                            "{safe_promiser}_reset_failed".format(
                                safe_promiser=safe_promiser
                            )
                        ],
                    )

            # Update the repository
            if model.update:
                try:
                    self.log_verbose(
                        "Fetch '{repository}' in '{destination}'".format(
                            repository=model.repository, destination=model.destination
                        )
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
                        [model.executable, "rev-parse", "--abbrev-ref", "HEAD".format()],
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
                            "Checkout '{repository}:{version}' in '{destination}'".format(
                                repository=model.repository,
                                version=model.version,
                                destination=model.destination,
                            )
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
                                "..{remote}/{version}".format(
                                    remote=model.remote, version=model.version
                                ),
                            ],
                            cwd=model.destination,
                        )
                        if output != "":
                            self.log_info(
                                "Merge '{remote}/{version}' in '{destination}'".format(
                                    remote=model.remote,
                                    version=model.version,
                                    destination=model.destination,
                                )
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
                    classes.append(
                        "{safe_promiser}_updated".format(safe_promiser=safe_promiser)
                    )
                except subprocess.CalledProcessError as e:
                    self.log_error("Failed fetch: {error}".format(error=e.output or e))
                    e.stderr and self.log_error(e.stderr.strip())
                    return (
                        Result.NOT_KEPT,
                        [
                            "{safe_promiser}_update_failed".format(
                                safe_promiser=safe_promiser
                            )
                        ],
                    )

        # everything okay
        return (result, classes)

    def _git(self, model: object, args: List[str], cwd: Optional[str] = None) -> str:
        self.log_verbose("Run: {cmd}".format(cmd=" ".join(args)))
        output = (
            subprocess.check_output(
                args,
                env=self._git_envvars(model),
                cwd=cwd,
                stderr=subprocess.PIPE,
            )
            .strip()
            .decode("utf-8")
        )
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
