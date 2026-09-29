"""
A small jq-like path language used to locate nodes inside a parsed
yaml document.

Supported syntax:

    .a.b.c                      key access
    .a["b.c"]                   quoted key access
    .a[1]  .a[-1]               numeric index (negative counts from the end)
    .a[]                        every item of a sequence
    .a[] | select(.b == "x")    items where .b equals a string, number,
                                true, false or null
"""

import re

from yaml_lite import MappingNode, SequenceNode, ScalarNode, get_slot


class FilterError(Exception):
    pass


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_TOKEN_SPEC = [
    ("DOT", r"\."),
    ("PIPE", r"\|"),
    ("LBRACKET", r"\["),
    ("RBRACKET", r"\]"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("EQ", r"=="),
    ("STRING", r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''),
    ("NUMBER", r"-?\d+"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_-]*"),
]
_TOKEN_RE = re.compile("|".join("(?P<%s>%s)" % pair for pair in _TOKEN_SPEC))
_WS_RE = re.compile(r"\s+")
_LITERALS = {"true": True, "false": False, "null": None}


class Token(object):
    __slots__ = ("type", "value", "pos")

    def __init__(self, type_, value, pos):
        self.type = type_
        self.value = value
        self.pos = pos


def tokenize(text):
    tokens = []
    pos = 0
    length = len(text)
    while pos < length:
        m = _WS_RE.match(text, pos)
        if m:
            pos = m.end()
            continue
        m = _TOKEN_RE.match(text, pos)
        if not m:
            raise FilterError(
                "Unexpected character %r at position %d in filter %r"
                % (text[pos], pos, text)
            )
        kind = m.lastgroup or ""
        tokens.append(Token(kind, m.group(kind), pos))
        pos = m.end()
    return tokens


def _unquote(raw):
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
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(char)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Steps / AST
# ---------------------------------------------------------------------------


class KeyStep(object):
    def __init__(self, name):
        self.name = name


class IndexStep(object):
    def __init__(self, index):
        self.index = index


class IterStep(object):
    pass


class SelectStep(object):
    def __init__(self, path, literal):
        self.path = path
        self.literal = literal


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _parse_steps(tokens, i, in_select):
    steps = []
    length = len(tokens)
    while i < length:
        token = tokens[i]
        if token.type in ("DOT", "PIPE"):
            if token.type == "PIPE" and in_select:
                raise FilterError("Unexpected '|' inside select()")
            i += 1
            continue
        if token.type == "EQ" and in_select:
            return steps, i
        if token.type == "LBRACKET":
            i += 1
            if i < length and tokens[i].type == "RBRACKET":
                if in_select:
                    raise FilterError("'[]' is not supported inside select()")
                steps.append(IterStep())
            elif i < length and tokens[i].type == "NUMBER":
                steps.append(IndexStep(int(tokens[i].value)))
                i += 1
            elif i < length and tokens[i].type == "STRING":
                steps.append(KeyStep(_unquote(tokens[i].value)))
                i += 1
            else:
                raise FilterError("Invalid index expression in filter")
            if i >= length or tokens[i].type != "RBRACKET":
                raise FilterError("Expected ']' in filter")
            i += 1
            continue
        if (
            token.type == "IDENT"
            and token.value == "select"
            and i + 1 < length
            and tokens[i + 1].type == "LPAREN"
        ):
            if in_select:
                raise FilterError("Nested select() is not supported")
            path, i = _parse_steps(tokens, i + 2, True)
            if i >= length or tokens[i].type != "EQ":
                raise FilterError("Expected '==' in select()")
            i += 1
            if i >= length:
                raise FilterError("Expected a value after '==' in select()")
            lit = tokens[i]
            if lit.type == "STRING":
                literal = _unquote(lit.value)
            elif lit.type == "NUMBER":
                literal = int(lit.value)
            elif lit.type == "IDENT" and lit.value in _LITERALS:
                literal = _LITERALS[lit.value]
            else:
                raise FilterError("Invalid value %r in select()" % lit.value)
            i += 1
            if i >= length or tokens[i].type != "RPAREN":
                raise FilterError("Expected ')' in select()")
            steps.append(SelectStep(path, literal))
            i += 1
            continue
        if token.type in ("IDENT", "STRING"):
            name = token.value if token.type == "IDENT" else _unquote(token.value)
            steps.append(KeyStep(name))
            i += 1
            continue
        raise FilterError("Unexpected token %r in filter" % token.value)
    if in_select:
        raise FilterError("Unexpected end of filter inside select()")
    return steps, i


def parse_filter(text):
    steps, _ = _parse_steps(tokenize(text), 0, False)
    if not steps:
        raise FilterError("Filter must select a key or item, not the whole document")
    return steps


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


class Match(object):
    """A location in the document. 'container' is the mapping/sequence that
    holds the node (or the empty MappingEntry/SequenceItem slot to create it
    under), 'key' its key or index and 'exists' whether it's there - a bare
    'key:' exists but its node is None. 'missing_parent' means 'key' is a
    missing key the filter goes through, which can be created."""

    __slots__ = ("container", "key", "node", "exists", "missing_parent")

    def __init__(self, container, key, node, exists, missing_parent=False):
        self.container = container
        self.key = key
        self.node = node
        self.exists = exists
        self.missing_parent = missing_parent


def _step(match, step, rest):
    if match.missing_parent:
        return [match]
    node = match.node
    if isinstance(step, KeyStep):
        if node is None and match.exists:
            # Key under an empty 'parent:'
            container, entry = get_slot(match.container, match.key), None
        elif isinstance(node, MappingNode):
            container, entry = node, node.get_entry(step.name)
        else:
            raise FilterError(
                "Cannot look up key '%s' on a non-mapping value" % step.name
            )
        if entry is not None:
            return [Match(node, step.name, entry.value, True)]
        if not rest:
            return [Match(container, step.name, None, False)]
        # Missing keys can only be created if the rest of the path is keys too
        if all(isinstance(s, KeyStep) for s in rest):
            return [Match(container, step.name, None, False, missing_parent=True)]
        raise FilterError("Key '%s' not found" % step.name)
    if isinstance(step, IndexStep):
        if not isinstance(node, SequenceNode):
            raise FilterError("Cannot index a non-sequence value")
        idx = step.index if step.index >= 0 else step.index + len(node.items)
        if not 0 <= idx < len(node.items):
            raise FilterError("Index %d out of range" % step.index)
        return [Match(node, idx, node.items[idx].value, True)]
    if isinstance(step, IterStep):
        if not isinstance(node, SequenceNode):
            raise FilterError("Cannot iterate over a non-sequence value")
        return [Match(node, i, item.value, True) for i, item in enumerate(node.items)]
    if isinstance(step, SelectStep):
        return [match] if selects(node, step) else []
    raise FilterError("Unknown filter step")


def selects(node, step):
    """Whether select() step keeps node."""
    for sub in step.path:
        if isinstance(sub, KeyStep) and isinstance(node, MappingNode):
            entry = node.get_entry(sub.name)
            node = entry.value if entry is not None else None
        elif isinstance(sub, IndexStep) and isinstance(node, SequenceNode):
            idx = sub.index if sub.index >= 0 else sub.index + len(node.items)
            node = node.items[idx].value if 0 <= idx < len(node.items) else None
        else:
            return False
        if node is None:
            return step.literal is None
    return isinstance(node, ScalarNode) and node.value == step.literal


def evaluate(steps, root):
    """Return every Match the filter resolves to."""
    matches = [Match(None, None, root, True)]
    for pos, step in enumerate(steps):
        rest = steps[pos + 1 :]
        matches = [m2 for m in matches for m2 in _step(m, step, rest)]
    return matches
