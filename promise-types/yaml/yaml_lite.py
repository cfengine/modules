"""
Minimal YAML editor.

This is NOT a general-purpose YAML library. It only understands the subset of
YAML needed by the 'yaml' promise type: block mappings, block sequences,
plain/quoted scalars and comments. Block scalars (`|`/`>`) and flow
collections (`{...}` / `[...]`) are not supported.

Every node keeps track of the source line(s) it came from, so that edits can
be applied as text splices on the original lines instead of a full
re-parse/re-dump of the document. This preserves comments, key order,
quoting style and formatting of everything the caller didn't touch.
"""

import re


class YamlSyntaxError(Exception):
    pass


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


class ScalarNode(object):
    def __init__(
        self, start_line, end_line, col_start, col_end, value, raw, style, trailing=""
    ):
        self.start_line = start_line
        self.end_line = end_line
        self.col_start = col_start
        self.col_end = col_end
        self.value = value
        self.raw = raw
        self.style = style  # 'plain' | 'single' | 'double'
        # Whitespace/comment text that followed the value on its source line
        # (e.g. " # primary"), preserved across edits.
        self.trailing = trailing


class MappingEntry(object):
    def __init__(
        self,
        key,
        key_line,
        key_col,
        colon_col,
        value_start_col,
        needs_space,
        value,
        end_line,
    ):
        self.key = key
        self.key_line = key_line
        self.key_col = key_col
        self.colon_col = colon_col
        self.value_start_col = value_start_col
        self.needs_space = needs_space
        self.value = value
        self.end_line = end_line


class MappingNode(object):
    def __init__(self, start_line, indent):
        self.start_line = start_line
        self.indent = indent
        self.entries = []
        self.end_line = start_line

    def get_entry(self, key):
        for entry in self.entries:
            if entry.key == key:
                return entry
        return None


class SequenceItem(object):
    def __init__(self, item_line, dash_col, value_start_col, value, needs_space):
        self.item_line = item_line
        self.dash_col = dash_col
        self.value_start_col = value_start_col
        self.value = value
        self.needs_space = needs_space
        self.end_line = value.end_line if value is not None else item_line


class SequenceNode(object):
    def __init__(self, start_line, indent):
        self.start_line = start_line
        self.indent = indent
        self.items = []
        self.end_line = start_line


# ---------------------------------------------------------------------------
# Low-level line helpers
# ---------------------------------------------------------------------------


def _strip_newline(line):
    if line.endswith("\r\n"):
        return line[:-2]
    if line.endswith("\n"):
        return line[:-1]
    return line


def _leading_spaces(line):
    return len(line) - len(line.lstrip(" "))


def _is_noise(line):
    s = line.strip()
    return s == "" or s.startswith("#") or s in ("---", "...")


def _find_comment_start(text):
    i = 1
    length = len(text)
    while i < length:
        if text[i] == "#" and text[i - 1] in " \t":
            return i
        i += 1
    return None


def _find_dquote_end(text):
    i = 1
    length = len(text)
    while i < length:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i
        i += 1
    return length - 1


def _find_squote_end(text):
    i = 1
    length = len(text)
    while i < length:
        if text[i] == "'":
            if i + 1 < length and text[i + 1] == "'":
                i += 2
                continue
            return i
        i += 1
    return length - 1


def _find_key_colon(text):
    """Return the index of the ':' that separates a mapping key from its
    value on this (indent-stripped, newline-stripped) line, or -1 if the
    line doesn't look like a mapping entry."""
    i = 0
    length = len(text)
    if length == 0:
        return -1
    if text[0] == "'":
        i = _find_squote_end(text) + 1
    elif text[0] == '"':
        i = _find_dquote_end(text) + 1
    while i < length:
        char = text[i]
        if char == ":":
            if i + 1 == length or text[i + 1] in " \t":
                return i
        elif char == "#" and (i == 0 or text[i - 1] in " \t"):
            return -1
        i += 1
    return -1


def _decode_double_quoted(raw):
    body = raw[1:-1]
    out = []
    i = 0
    length = len(body)
    while i < length:
        char = body[i]
        if char == "\\" and i + 1 < length:
            nxt = body[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            elif nxt == "r":
                out.append("\r")
            elif nxt in ('"', "\\"):
                out.append(nxt)
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


def _decode_single_quoted(raw):
    return raw[1:-1].replace("''", "'")


def _decode_scalar_text(text):
    if text.startswith('"'):
        end = _find_dquote_end(text)
        return _decode_double_quoted(text[: end + 1])
    if text.startswith("'"):
        end = _find_squote_end(text)
        return _decode_single_quoted(text[: end + 1])
    return text.strip()


def decode_plain_scalar(raw):
    if raw == "" or raw == "~" or raw.lower() == "null":
        return None
    low = raw.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser(object):
    def __init__(self, lines):
        self.lines = lines
        self.line_count = len(lines)

    def _skip_noise(self, idx):
        while idx < self.line_count and _is_noise(self.lines[idx]):
            idx += 1
        return idx

    def parse_block(self, idx, min_indent):
        idx = self._skip_noise(idx)
        if idx >= self.line_count:
            return None, idx
        line = self.lines[idx]
        indent = _leading_spaces(line)
        if indent < min_indent:
            return None, idx
        content = _strip_newline(line)[indent:]
        if content == "-" or content.startswith("- "):
            return self._parse_sequence(idx, indent)
        if _find_key_colon(content) != -1:
            return self._parse_mapping(idx, indent)
        node = self._parse_inline_scalar(idx, indent, content)
        return node, idx + 1

    # -- mappings ---------------------------------------------------------

    def _parse_mapping(self, idx, indent):
        node = MappingNode(start_line=idx, indent=indent)
        idx = self._parse_mapping_body(node, idx, indent)
        node.end_line = node.entries[-1].end_line if node.entries else node.start_line
        return node, idx

    def _parse_inline_mapping(
        self, dash_line, key_col, key_line_content, indent_for_siblings
    ):
        node = MappingNode(start_line=dash_line, indent=indent_for_siblings)
        entry, next_idx = self._make_entry_from_content(
            dash_line, key_col, key_line_content
        )
        node.entries.append(entry)
        idx = self._parse_mapping_body(node, next_idx, indent_for_siblings)
        node.end_line = node.entries[-1].end_line
        return node, idx

    def _parse_mapping_body(self, node, idx, indent):
        while True:
            idx = self._skip_noise(idx)
            if idx >= self.line_count:
                break
            line = self.lines[idx]
            if _leading_spaces(line) != indent:
                break
            content = _strip_newline(line)[indent:]
            if _find_key_colon(content) == -1:
                break
            entry, idx = self._make_entry_from_content(idx, indent, content)
            node.entries.append(entry)
        return idx

    def _make_entry_from_content(self, line_idx, key_col, content):
        colon_idx = _find_key_colon(content)
        key_text = content[:colon_idx]
        key = _decode_scalar_text(key_text)
        rest = content[colon_idx + 1 :]
        rest_lstripped = rest.lstrip(" ")
        leading_ws_len = len(rest) - len(rest_lstripped)
        value_col = key_col + colon_idx + 1 + leading_ws_len

        if rest_lstripped == "" or rest_lstripped.startswith("#"):
            nxt = self._skip_noise(line_idx + 1)
            if nxt < self.line_count and _leading_spaces(self.lines[nxt]) > key_col:
                value_node, next_idx = self.parse_block(line_idx + 1, key_col + 1)
            else:
                value_node, next_idx = None, line_idx + 1
        elif rest_lstripped == "-" or rest_lstripped.startswith("- "):
            value_node, next_idx = self._parse_inline_sequence(
                line_idx, value_col, rest_lstripped, value_col
            )
        elif _find_key_colon(rest_lstripped) != -1:
            value_node, next_idx = self._parse_inline_mapping(
                line_idx, value_col, rest_lstripped, value_col
            )
        else:
            value_node = self._parse_inline_scalar(line_idx, value_col, rest_lstripped)
            next_idx = line_idx + 1

        entry = MappingEntry(
            key=key,
            key_line=line_idx,
            key_col=key_col,
            colon_col=key_col + colon_idx,
            value_start_col=value_col,
            needs_space=(leading_ws_len == 0),
            value=value_node,
            end_line=value_node.end_line if value_node is not None else line_idx,
        )
        return entry, next_idx

    # -- sequences ----------------------------------------------------------

    def _parse_sequence(self, idx, indent):
        node = SequenceNode(start_line=idx, indent=indent)
        idx = self._parse_sequence_body(node, idx, indent)
        node.end_line = node.items[-1].end_line if node.items else node.start_line
        return node, idx

    def _parse_inline_sequence(self, dash_line, col, content, indent_for_siblings):
        node = SequenceNode(start_line=dash_line, indent=indent_for_siblings)
        item, next_idx = self._make_item_from_content(dash_line, col, content)
        node.items.append(item)
        idx = self._parse_sequence_body(node, next_idx, indent_for_siblings)
        node.end_line = node.items[-1].end_line
        return node, idx

    def _parse_sequence_body(self, node, idx, indent):
        while True:
            idx = self._skip_noise(idx)
            if idx >= self.line_count:
                break
            line = self.lines[idx]
            if _leading_spaces(line) != indent:
                break
            content = _strip_newline(line)[indent:]
            if content != "-" and not content.startswith("- "):
                break
            item, idx = self._make_item_from_content(idx, indent, content)
            node.items.append(item)
        return idx

    def _make_item_from_content(self, line_idx, dash_col, content):
        if content == "-":
            rest = ""
            marker_width = 1
        else:
            rest = content[2:]
            marker_width = 2
        rest_lstripped = rest.lstrip(" ")
        leading_ws_len = len(rest) - len(rest_lstripped)
        value_col = dash_col + marker_width + leading_ws_len

        if rest_lstripped == "" or rest_lstripped.startswith("#"):
            nxt = self._skip_noise(line_idx + 1)
            if nxt < self.line_count and _leading_spaces(self.lines[nxt]) > dash_col:
                value_node, next_idx = self.parse_block(line_idx + 1, dash_col + 1)
            else:
                value_node, next_idx = None, line_idx + 1
        elif rest_lstripped == "-" or rest_lstripped.startswith("- "):
            value_node, next_idx = self._parse_inline_sequence(
                line_idx, value_col, rest_lstripped, value_col
            )
        elif _find_key_colon(rest_lstripped) != -1:
            value_node, next_idx = self._parse_inline_mapping(
                line_idx, value_col, rest_lstripped, value_col
            )
        else:
            value_node = self._parse_inline_scalar(line_idx, value_col, rest_lstripped)
            next_idx = line_idx + 1

        item = SequenceItem(
            item_line=line_idx,
            dash_col=dash_col,
            value_start_col=value_col,
            value=value_node,
            needs_space=(content == "-"),
        )
        return item, next_idx

    # -- scalars --------------------------------------------------------

    def _parse_inline_scalar(self, line_idx, col, text):
        if text.startswith('"'):
            end = _find_dquote_end(text)
            raw = text[: end + 1]
            value = _decode_double_quoted(raw)
            style = "double"
            col_end = col + end + 1
        elif text.startswith("'"):
            end = _find_squote_end(text)
            raw = text[: end + 1]
            value = _decode_single_quoted(raw)
            style = "single"
            col_end = col + end + 1
        else:
            cut = _find_comment_start(text)
            raw = text[:cut] if cut is not None else text
            raw = raw.rstrip()
            value = decode_plain_scalar(raw)
            style = "plain"
            col_end = col + len(raw)
        return ScalarNode(
            start_line=line_idx,
            end_line=line_idx,
            col_start=col,
            col_end=col_end,
            value=value,
            raw=raw,
            style=style,
            trailing=text[len(raw) :],
        )


def parse_document(text):
    lines = text.splitlines(True) if text else []
    parser = _Parser(lines)
    idx = parser._skip_noise(0)
    if idx >= parser.line_count:
        return lines, None
    root, _ = parser.parse_block(idx, 0)
    return lines, root


# ---------------------------------------------------------------------------
# Scalar formatting (for writing new/changed values back out)
# ---------------------------------------------------------------------------

# Plain scalars that YAML 1.1 parsers read as booleans. true/false/null are
# left alone, so that values can be written as booleans/null on purpose.
_RESERVED_PLAIN_WORDS = set(["yes", "no", "on", "off", "y", "n"])
# YAML 1.1 reads e.g. 22:22 as a base 60 number
_SEXAGESIMAL_RE = re.compile(r"^[0-9][0-9_]*(:[0-5]?[0-9])+(\.[0-9_]*)?$")
_COLON_SPACE_RE = re.compile(r":(\s|$)")
_SPACE_HASH_RE = re.compile(r"\s#")


def _needs_quote(s):
    if s == "":
        return True
    if s != s.strip():
        return True
    if "\n" in s or "\r" in s:
        return True
    if s.lower() in _RESERVED_PLAIN_WORDS:
        return True
    if s[0] in "!&*?|>%@`\"'#,[]{}":
        return True
    if s[0] == "-" and (len(s) == 1 or s[1] == " "):
        return True
    if _COLON_SPACE_RE.search(s):
        return True
    if _SPACE_HASH_RE.search(s):
        return True
    if _SEXAGESIMAL_RE.match(s):
        return True
    return False


def _encode_double_quoted(s):
    out = ['"']
    for ch in s:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def _encode_single_quoted(s):
    return "'" + s.replace("'", "''") + "'"


def format_scalar(value, preferred_style=None):
    value = "" if value is None else str(value)
    if "\n" in value or "\r" in value:
        return _encode_double_quoted(value)
    if preferred_style == "single":
        return _encode_single_quoted(value)
    if preferred_style == "double":
        return _encode_double_quoted(value)
    if _needs_quote(value):
        return _encode_double_quoted(value)
    return value


# ---------------------------------------------------------------------------
# Mutation helpers (line splicing)
# ---------------------------------------------------------------------------


def get_slot(container, key):
    if isinstance(container, MappingNode):
        entry = container.get_entry(key)
        assert entry is not None
        return entry
    return container.items[key]


def slot_line(slot):
    return slot.key_line if isinstance(slot, MappingEntry) else slot.item_line


def set_slot_value(lines, slot, new_value_text):
    def_line = slot_line(slot)
    line = lines[def_line]
    if line.endswith("\r\n"):
        nl = "\r\n"
    elif line.endswith("\n"):
        nl = "\n"
    else:
        nl = "\n"
    prefix = line[: slot.value_start_col]
    if slot.needs_space:
        prefix += " "
    trailing = ""
    if (
        isinstance(slot.value, ScalarNode)
        and slot.value.start_line == def_line
        and slot.value.end_line == def_line
    ):
        trailing = slot.value.trailing
    new_line = prefix + new_value_text + trailing + nl
    old_end = slot.value.end_line if slot.value is not None else def_line
    lines[def_line : old_end + 1] = [new_line]


def delete_slot(lines, slot):
    start = slot_line(slot)
    end = slot.end_line
    del lines[start : end + 1]


def _child_insert_point(container):
    """Return (line index, indent) for a new last child of container: a
    mapping/sequence node, or an empty 'key:' / '-' slot."""
    if isinstance(container, (MappingEntry, SequenceItem)):
        col = (
            container.key_col
            if isinstance(container, MappingEntry)
            else container.dash_col
        )
        return slot_line(container) + 1, col + 2
    children = (
        container.entries if isinstance(container, MappingNode) else container.items
    )
    at = children[-1].end_line + 1 if children else container.start_line + 1
    return at, container.indent


def insert_mapping_key(lines, container, key, value_text):
    at, indent = _child_insert_point(container)
    # An empty value_text creates an empty 'key:' to add children under
    value = ": " + value_text if value_text else ":"
    lines.insert(at, " " * indent + format_scalar(key) + value + "\n")


def append_sequence_item(lines, container, value_text):
    at, indent = _child_insert_point(container)
    lines.insert(at, " " * indent + "- " + value_text + "\n")
