import os
import json

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
                    promiser, str(self.types)
                )
            )
        elif len(present_types) > 1:
            raise ValidationError(
                "The attributes {} cannot be together".format(str(self.types))
            )

        filename, _, _ = promiser.partition(":")
        if os.path.exists(filename) and not os.path.isfile(filename):
            raise ValidationError(
                "'{}' already exists and is not a file".format(filename)
            )

        if not filename.endswith(".json"):
            raise ValidationError("'{}' is not a json file")

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
                if not is_json_serializable(model.array):
                    raise ValidationError(
                        "'{}' is not a valid list".format(model.array)
                    )

                if not isinstance(json.loads(model.array), list):
                    raise ValidationError(
                        "'{}' is not a valid data".format(model.array)
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

        # type conversion

        datatype = next(t for t in self.types if t in attributes)

        match datatype:
            case "object" | "array":
                data = (
                    json.loads(attributes[datatype])
                    if isinstance(attributes[datatype], str)
                    else attributes[datatype]
                )
            case "number":
                data = float(model.number) if "." in model.number else int(model.number)
            case "primitive":
                data = None if model.primitive == "null" else model.primitive == "true"
            case _:  # strings
                data = attributes[datatype]

        # json manipulation

        try:
            with open(filename, "r+") as f:
                content = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            content = {}

        if field:
            if field in content and content[field] == data:
                Result.KEPT
            content[field] = data
        else:
            if content == data:
                Result.KEPT
            content = data

        with open(filename, "w") as f:
            json.dump(content, f, indent=4)

        self.log_info("Updated '{}'".format(filename))
        Result.REPAIRED


if __name__ == "__main__":
    JsonPromiseTypeModule().start()
