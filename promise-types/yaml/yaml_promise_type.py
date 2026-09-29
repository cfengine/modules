import os
import stat
import tempfile

from cfengine_module_library import PromiseModule, ValidationError, Result

import yaml_lite
import jq_filter

_STATES = ("present", "absent")

# Each repair changes one match and re-parses the file, so this only guards
# against a promise that never converges
_MAX_REPAIRS = 1000


class YamlPromiseTypeModule(PromiseModule):
    def __init__(self):
        super(YamlPromiseTypeModule, self).__init__("yaml_promise_module", "0.0.0")

    def validate_promise(self, promiser, attributes, metadata):
        target = attributes.get("target")
        if not target:
            raise ValidationError("Attribute 'target' is required")
        try:
            steps = jq_filter.parse_filter(target)
        except jq_filter.FilterError as e:
            raise ValidationError("Invalid 'target': %s" % e)

        state = attributes.get("state")
        if state not in _STATES:
            raise ValidationError(
                "Attribute 'state' must be one of: %s" % ", ".join(_STATES)
            )

        # Without a value, 'present' adds an item to a sequence of mappings,
        # built from the select() condition
        if state == "present" and "value" not in attributes:
            if not _is_item_select(steps):
                raise ValidationError(
                    "State 'present' requires 'value', or a target ending in "
                    "'[] | select(.key == value)'"
                )

        if state == "absent" and "value" in attributes:
            if not isinstance(steps[-1], jq_filter.IterStep):
                raise ValidationError(
                    "State 'absent' with 'value' removes sequence items, "
                    "use a target ending in '[]'"
                )

        # Removing by position is not convergent: the next run would remove
        # whatever moved into that position
        if (
            state == "absent"
            and "value" not in attributes
            and isinstance(steps[-1], jq_filter.IndexStep)
        ):
            raise ValidationError(
                "State 'absent' can not remove a sequence item by index, "
                "use '[]' with 'value', or select(), to match it by content"
            )

    def evaluate_promise(self, promiser, attributes, metadata):
        state = attributes["state"]
        target = attributes["target"]
        value = attributes.get("value")
        steps = jq_filter.parse_filter(target)

        # Like the json promise type, a missing file is treated as empty and
        # created when something is added to it
        if os.path.exists(promiser) and not os.path.isfile(promiser):
            self.log_error("'%s' already exists and is not a regular file" % promiser)
            return Result.NOT_KEPT
        content = ""
        if os.path.exists(promiser):
            with open(promiser, "r", newline="") as f:
                content = f.read()
        # Edit with \n line endings and write back with the file's own
        newline = "\r\n" if "\r\n" in content else "\n"
        content = content.replace("\r\n", "\n")
        # New lines are added after the last one, so it needs a line ending.
        # Only written to the file if something else changes too.
        if content and not content.endswith("\n"):
            content += "\n"

        changed = False
        for _ in range(_MAX_REPAIRS):
            lines, root = yaml_lite.parse_document(content)
            if root is None:
                # Empty document (or only comments): new keys go at the end
                root = yaml_lite.MappingNode(start_line=len(lines) - 1, indent=0)
            try:
                if state == "present" and value is None:
                    # The sequence(s) that '[] | select()' looks in
                    sequences = jq_filter.evaluate(steps[:-2], root)
                    repaired = _present_selected(lines, sequences, steps[-1])
                elif value is not None and isinstance(steps[-1], jq_filter.IterStep):
                    # '.list[]' with a value: the sequence contains it or not
                    sequences = jq_filter.evaluate(steps[:-1], root)
                    repaired = _repair_one(lines, sequences, state, value, True)
                else:
                    matches = jq_filter.evaluate(steps, root)
                    repaired = _repair_one(lines, matches, state, value, False)
                if not repaired:
                    break
            except (jq_filter.FilterError, _OperationError) as e:
                self.log_error("Target '%s' failed on '%s': %s" % (target, promiser, e))
                return Result.NOT_KEPT
            content = "".join(lines)
            changed = True
        else:
            self.log_error("'%s' did not converge for target '%s'" % (promiser, target))
            return Result.NOT_KEPT

        if not changed:
            return Result.KEPT

        try:
            self._write_atomically(promiser, content, newline)
        except OSError as e:
            self.log_error("Failed to write '%s': %s" % (promiser, e))
            return Result.NOT_KEPT
        self.log_info(
            "Updated '%s' (target '%s', state '%s')" % (promiser, target, state)
        )
        return Result.REPAIRED

    def _write_atomically(self, path, content, newline):
        """Write to a temporary file next to 'path' and rename it into place,
        so readers never see a partially written file."""
        # Edit the file a symlink points to, not replace the symlink
        path = os.path.realpath(path)
        # Dirs/files are created with mode 0700 and 0600 respectively
        directory = os.path.dirname(path)
        if not os.path.isdir(directory):
            os.makedirs(directory, 0o700)
            self.log_info("Created directory for '%s'" % path)
        fd, tmp = tempfile.mkstemp(
            prefix="." + os.path.basename(path) + ".", suffix=".tmp", dir=directory
        )
        try:
            with os.fdopen(fd, "w", newline=newline) as f:
                # Keep the permissions and owner of an existing file
                if os.path.exists(path):
                    st = os.stat(path)
                    os.fchmod(f.fileno(), stat.S_IMODE(st.st_mode))
                    if (st.st_uid, st.st_gid) != (os.getuid(), os.getgid()):
                        os.fchown(f.fileno(), st.st_uid, st.st_gid)
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


class _OperationError(Exception):
    pass


def _repair_one(lines, matches, state, value, in_sequence):
    """Fix the first match that isn't in the desired state. Returns False if
    all matches are already in the desired state. With in_sequence, matches
    are sequences and value an item of them."""
    for match in matches:
        if match.missing_parent:
            if state == "absent":
                continue
            # Create the missing key empty, the next repair adds to it
            yaml_lite.insert_mapping_key(lines, match.container, match.key, "")
            return True
        if in_sequence:
            if state == "present":
                repaired = _present(lines, match, value)
            else:
                repaired = _absent_item(lines, match, value)
            if repaired:
                return True
        elif state == "present":
            if _set(lines, match, value):
                return True
        elif match.exists:
            yaml_lite.delete_slot(lines, yaml_lite.get_slot(match.container, match.key))
            return True
    return False


def _set(lines, match, value):
    if not match.exists:
        if isinstance(match.container, yaml_lite.SequenceNode):
            raise _OperationError("Can not set a sequence item that does not exist")
        yaml_lite.insert_mapping_key(
            lines, match.container, match.key, yaml_lite.format_scalar(value)
        )
        return True
    node = match.node
    if isinstance(node, yaml_lite.SequenceNode):
        raise _OperationError(
            "Value is a sequence, end the target with '[]' to add an item to it"
        )
    style = node.style if isinstance(node, yaml_lite.ScalarNode) else None
    new_text = yaml_lite.format_scalar(value, style)
    if isinstance(node, yaml_lite.ScalarNode) and node.raw == new_text:
        return False
    yaml_lite.set_slot_value(
        lines, yaml_lite.get_slot(match.container, match.key), new_text
    )
    return True


def _sequence_or_slot(match):
    """The sequence the filter points at, or the empty 'key:' slot to create
    it under."""
    if isinstance(match.node, yaml_lite.SequenceNode):
        return match.node
    if match.exists and match.node is None:
        return yaml_lite.get_slot(match.container, match.key)
    raise _OperationError("Target ending in '[]' is not a sequence")


def _item_text(node):
    if not isinstance(node, yaml_lite.ScalarNode):
        return None
    return node.raw if node.style == "plain" else node.value


def _present(lines, match, value):
    if not match.exists:
        if isinstance(match.container, yaml_lite.SequenceNode):
            raise _OperationError("Target ending in '[]' is not a sequence")
        yaml_lite.insert_mapping_key(lines, match.container, match.key, "")
        return True
    seq = _sequence_or_slot(match)
    if isinstance(seq, yaml_lite.SequenceNode):
        if any(_item_text(item.value) == value for item in seq.items):
            return False
    yaml_lite.append_sequence_item(lines, seq, yaml_lite.format_scalar(value))
    return True


def _is_item_select(steps):
    return (
        len(steps) >= 2
        and isinstance(steps[-2], jq_filter.IterStep)
        and isinstance(steps[-1], jq_filter.SelectStep)
        and len(steps[-1].path) == 1
        and isinstance(steps[-1].path[0], jq_filter.KeyStep)
    )


def _literal_text(literal):
    """YAML text for a select() literal that reads back as the same value."""
    if literal is None:
        return "null"
    if isinstance(literal, bool):
        return "true" if literal else "false"
    if isinstance(literal, int):
        return str(literal)
    text = yaml_lite.format_scalar(literal)
    if text == literal and yaml_lite.decode_plain_scalar(text) != literal:
        # e.g. the string "true" or "8080", which would be read as non-strings
        return yaml_lite.format_scalar(literal, "double")
    return text


def _present_selected(lines, matches, select):
    """Append a '- key: value' item to every sequence where select() matches
    no item. Returns False if all of them already have one."""
    key = select.path[0].name
    for match in matches:
        if match.missing_parent or not match.exists:
            if isinstance(match.container, yaml_lite.SequenceNode):
                raise _OperationError("Target ending in '[]' is not a sequence")
            # Create the missing 'key:', the next repair adds the item
            yaml_lite.insert_mapping_key(lines, match.container, match.key, "")
            return True
        seq = _sequence_or_slot(match)
        if isinstance(seq, yaml_lite.SequenceNode) and any(
            jq_filter.selects(item.value, select) for item in seq.items
        ):
            continue
        item = yaml_lite.format_scalar(key) + ": " + _literal_text(select.literal)
        yaml_lite.append_sequence_item(lines, seq, item)
        return True
    return False


def _absent_item(lines, match, value):
    seq = _sequence_or_slot(match)
    if not isinstance(seq, yaml_lite.SequenceNode):
        return False
    for item in seq.items:
        if _item_text(item.value) == value:
            yaml_lite.delete_slot(lines, item)
            return True
    return False


if __name__ == "__main__":
    YamlPromiseTypeModule().start()
