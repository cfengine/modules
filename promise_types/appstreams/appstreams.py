import os
from cfengine import PromiseModule, ValidationError, Result


class AppstreamsPromiseTypeModule(PromiseModule):
    def __init__(self, **kwargs):
        super().__init__("appstreams_module", "0.0.1", **kwargs)

    def validate_promise(self, promiser, attributes):
        pass

    def evaluate_promise(self, promiser, attributes):
        self.log_error("appstreams module not implemented yet!")
        return Result.NOT_KEPT


if __name__ == "__main__":
    AppstreamsPromiseTypeModule().start()
