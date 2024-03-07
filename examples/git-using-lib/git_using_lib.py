import os
from cfengine import PromiseModule, ValidationError, Result


class GitPromiseTypeModule(PromiseModule):
    def __init__(self):
        super().__init__("git_promise_module", "0.0.1")

    def validate_promise(self, promiser, attributes, metadata):
        if not promiser.startswith("/"):
            raise ValidationError(f"File path '{promiser}' must be absolute")
        if "repository" not in attributes:
            raise ValidationError(f"Attribute 'repository' is required")

    def evaluate_promise(self, promiser, attributes, metadata):
        url = attributes["repository"]
        folder = promiser

        if os.path.exists(folder):
            self.log_verbose(f"'{folder}' already exists, nothing to do")
            return Result.KEPT

        self.log_info(f"Cloning '{url}' -> '{folder}'...")
        os.system(f"git clone {url} {folder} 2>/dev/null")

        if os.path.exists(folder):
            self.log_info(f"Successfully cloned '{url}' -> '{folder}'")
            return Result.REPAIRED
        else:
            self.log_error(f"Failed to clone '{url}' -> '{folder}'")
            return Result.NOT_KEPT


if __name__ == "__main__":
    GitPromiseTypeModule().start()
