import os
from cfengine_module_library import PromiseModule, ValidationError, Result


class SymlinksPromiseTypeModule(PromiseModule):

    def __init__(self, **kwargs):
        super(SymlinksPromiseTypeModule, self).__init__(
            name="symlinks_promise_module",
            version="0.0.0",
            **kwargs,
        )

        def is_absolute_dir(v):
            if not os.path.isabs(v):
                raise ValidationError("must be an absolute path, not '{v}'".format(v=v))
            if not os.path.exists(v):
                raise ValidationError("directory must exists")
            if not os.path.isdir(v):
                raise ValidationError("must be a dir")

        def is_absolute_file(v):
            if not os.path.isabs(v):
                raise ValidationError("must be an absolute path, not '{v}'".format(v=v))
            if not os.path.exists(v):
                raise ValidationError("file must exists")
            if not os.path.isfile(v):
                raise ValidationError("must be a file")

        self.add_attribute("directory", str, validator=is_absolute_dir)
        self.add_attribute("file", str, validator=is_absolute_file)

    def validate_promise(self, promiser, attributes, metadata):
        model = self.create_attribute_object(promiser, attributes)

        if not model.file and not model.directory:
            raise ValidationError("missing 'file' or 'directory' attribute")

        if model.file and model.directory:
            raise ValidationError("must specify either 'file' or 'directory', not both")

    def evaluate_promise(self, promiser, attributes, metadata):
        model = self.create_attribute_object(promiser, attributes)
        link_target = model.file if model.file else model.directory

        try:
            os.symlink(link_target, promiser, target_is_directory=bool(model.directory))
            self.log_info("Created symlink '{}' -> '{}'".format(promiser, link_target))
            return Result.REPAIRED
        except FileExistsError:

            if not os.path.islink(promiser):
                self.log_error("Symlink '{}' is already a path".format(promiser))
                return Result.NOT_KEPT

            if os.path.realpath(promiser) != link_target:
                self.log_warning(
                    "Symlink '{}' already exists but has wrong target '{}'".format(
                        promiser, os.path.realpath(promiser)
                    )
                )
                try:
                    os.unlink(promiser)
                except FileNotFoundError:
                    self.log_error(
                        "'{}' is already unlinked from its old target".format(promiser)
                    )
                    return Result.NOT_KEPT
                except Exception:
                    self.log_error(
                        "'{}' has wrong target but couldn't be unlinked: {}".format(
                            promiser, e
                        )
                    )
                    return Result.NOT_KEPT
                try:
                    os.symlink(
                        link_target, promiser, target_is_directory=bool(model.directory)
                    )
                except FileExistsError:
                    self.log_error(
                        "Couldn't symlink '{}' to '{}'. A symlink already exists".format(
                            link_target, promiser
                        )
                    )
                    return Result.NOT_KEPT
                except FileNotFoundError:
                    self.log_error("'{}' doesn't exist".format(link_target))
                    return Result.NOT_KEPT
                except Exception as e:
                    self.log_error(
                        "Couldn't symlink '{}' to '{}': {}".format(
                            link_target, promiser, e
                        )
                    )
                    return Result.NOT_KEPT

                self.log_info(
                    "Corrected symlink '{}' -> '{}'".format(promiser, link_target)
                )
                return Result.REPAIRED

            return Result.KEPT

        except FileNotFoundError:
            self.log_error("'{}' doesn't exist".format(promiser))
            return Result.NOT_KEPT

        except Exception as e:
            self.log_error(
                "Couldn't symlink '{}' to '{}': {}".format(link_target, promiser, e)
            )
            return Result.NOT_KEPT


if __name__ == "__main__":
    SymlinksPromiseTypeModule().start()
