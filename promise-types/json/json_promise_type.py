import os
import json
import tempfile
import shutil

from cfengine import PromiseModule, ValidationError, Result, AttributeObject


def is_number(num):
    try:
        float(num)
        return True
    except ValueError:
        return False


def is_json_serializable(string):
    try:
        json.loads(string)
        return True
    except json.JSONDecodeError:
        return False


class JsonPromiseTypeModule(PromiseModule):

    def __init__(self, **kwargs):
        super(JsonPromiseTypeModule, self).__init__(
            name="json_promise_module", version="0.0.1", **kwargs
        )

        self.types = ["object", "array", "string", "number", "primitive"]
        self.valid_attributes = (
            self.types
        )  # for now, the only valid attributes are the types.

    def create_attribute_object(self, attributes):
        data = {t: None for t in self.valid_attributes}
        for attr, val in attributes.items():
            data[attr] = val
        return AttributeObject(data)

    def validate_promise(self, promiser, attributes, metadata):

        for attr in attributes:
            if attr not in self.valid_attributes:
                raise ValidationError("Unknown attribute '{}'".format(attr))

        present_types = [t for t in self.types if t in attributes]
        if present_types == 0:
            raise ValidationError(
                "The promiser '{}' is missing a type attribute. The possible types are {}".format(
                    promiser, ", ".join(["'{}'".format(t) for t in self.types])
                )
            )
        elif len(present_types) > 1:
            raise ValidationError(
                "The attributes {} cannot be together".format(
                    ", ".join(["'{}'".format(t) for t in self.types])
                )
            )

        filename, colon, field = promiser.partition(":")

        if not filename:
            raise ValidationError("Invalid syntax: missing file name")

        if colon and not field:
            raise ValidationError("Invalid syntax: field specified but empty")

        model = self.create_attribute_object(attributes)
        if (
            model.object
            and isinstance(model.object, str)
            and not is_json_serializable(model.object)
        ):
            raise ValidationError(
                "'{}' is not a valid data container".format(model.object)
            )

        if model.array:
            if isinstance(model.array, str):
                try:
                    array = json.loads(model.array)

                except:
                    raise ValidationError(
                        "'{}' cannot be serialized to a json array".format(model.array)
                    )
                if not isinstance(array, list):
                    raise ValidationError(
                        "'{}' is not a valid data array".format(model.array)
                    )

            elif not isinstance(model.array, list):
                raise ValidationError(
                    "'{}' is not a valid data array".format(model.array)
                )

        if model.number and not is_number(model.number):
            raise ValidationError(
                "'{}' is not a valid int or real".format(model.number)
            )

        if model.primitive and model.primitive not in ["true", "false", "null"]:
            raise ValidationError(
                "expected 'true', 'false' or 'null' but got '{}".format(model.primitive)
            )

    def evaluate_promise(self, promiser, attributes, metadata):
        model = self.create_attribute_object(attributes)
        filename, _, field = promiser.partition(":")

        if os.path.exists(filename) and not os.path.isfile(filename):
            self.log_error(
                "'{}' already exists and is not a regular file".format(filename)
            )
            return Result.NOT_KEPT

        # type conversion

        datatype = next(t for t in self.types if t in attributes)

        if isinstance(attributes[datatype], str) and not model.string:
            data = json.loads(attributes[datatype])
        else:
            data = attributes[datatype]

        # json manipulation

        try:
            with open(filename, "r+") as f:
                content = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            content = {}
        except Exception as e:
            self.log_error("Failed to read '{}': {}".format(filename, e))
            return Result.NOT_KEPT

        if field:
            if not isinstance(content, dict):
                content = {}
                self.log_warning(
                    "Tried to access '{}' in '{}' when the content is not subscriptable. Overwriting the file...".format(
                        field, filename
                    )
                )

            if field in content and content[field] == data:
                self.log_info("'{}' is already up to date".format(promiser))
                return Result.KEPT
            content[field] = data
        else:
            if content == data:
                self.log_info("'{}' is already up to date".format(promiser))
                return Result.KEPT
            content = data

        fd, tmp = tempfile.mkstemp()
        json_bytes = json.dumps(content, indent=4).encode("utf-8")
        written = os.write(fd, json_bytes)
        os.close(fd)
        shutil.move(tmp, filename)

        if written != len(json_bytes):
            self.log_error(
                "Couldn't write all the data to the file '{}'. Wrote {} out of {} bytes".format(
                    filename, written, len(json_bytes)
                )
            )
            return Result.NOT_KEPT

        self.log_info("Updated '{}'".format(filename))
        return Result.REPAIRED


if __name__ == "__main__":
    JsonPromiseTypeModule().start()
