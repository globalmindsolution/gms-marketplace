"""acs_lib.yamlsubset — a strict, stdlib-only reader for the YAML subset acs
writes and reads: workflows/ship.yaml, workflows/phases.yaml and the front
matter of the ticket artifacts (ticket.md, analysis.md, test-cases.md).

Hook scripts are stdlib-only, so pyyaml is not an option; and a full YAML
reader would accept far more than the workflow files should ever contain. The
subset is therefore small and every construct outside it is REJECTED with a
line-numbered YamlSubsetError rather than read "best effort":

  accepted   `#` comments; `key: value` mappings nested by exactly 2 spaces;
             block lists (`- item`, `- key: value` mappings, a bare `-` opening
             a nested block); inline scalar lists `[a, "b", 3]` on one line;
             scalars: "double-quoted" (\\ \" \\n \\t \\r escapes), 'single-quoted'
             ('' escape), bare strings, integers, `true`/`false`, `null`/`~`
             (and an empty value); one leading `---` document marker.
  rejected   anchors `&`, aliases `*`, tags `!`, flow mappings `{}`, block
             scalars `|`/`>`, nested or multi-line inline lists, tabs outside
             quotes, duplicate keys, inconsistent indentation, a second `---`.

`loads(text)` returns the value; `parse(text)` also returns a `{path: line}`
map (paths are tuples of keys and list indexes, the root is `()`), which is
what lets the workflow validator report a schema failure at its source line.
"""

import re


class YamlSubsetError(ValueError):
    """A document outside the subset. `line` is 1-based; `path` is the file
    when the document was read from one."""

    def __init__(self, reason, line=None, path=None):
        self.reason = reason
        self.line = line
        self.path = path
        super().__init__(self.render())

    def render(self):
        where = "line %d" % self.line if self.line else "document"
        if self.path:
            where = "%s: %s" % (self.path, where)
        return "%s: %s" % (where, self.reason)


_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.\-]*):(?:\s+(?P<rest>.*))?$")
_INT_RE = re.compile(r"^[-+]?\d+$")
#: A quote opens a quoted scalar only at the start of a value: after a key's
#: colon, a list dash, an inline-list bracket or comma, or at line start.
_QUOTE_OPENERS = (None, ":", "-", "[", ",")
_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "t": "\t", "r": "\r", "/": "/", "'": "'"}


class _Line(object):
    __slots__ = ("number", "indent", "text")

    def __init__(self, number, indent, text):
        self.number = number
        self.indent = indent
        self.text = text


# ---------------------------------------------------------------------------
# Line scanning
# ---------------------------------------------------------------------------

def _strip_comment(raw, number):
    """The line without its trailing comment; raises on a tab outside quotes."""
    quote = None
    last = None  # last non-space character outside quotes; None at line start
    out = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if quote:
            out.append(ch)
            if quote == '"' and ch == "\\" and i + 1 < len(raw):
                out.append(raw[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
                last = ch
        else:
            if ch == "\t":
                raise YamlSubsetError("tab character (indent and separate with spaces)", number)
            if ch == "#" and (i == 0 or raw[i - 1] == " "):
                break
            if ch in ('"', "'") and last in _QUOTE_OPENERS:
                quote = ch
            out.append(ch)
            if ch != " ":
                last = ch
        i += 1
    return "".join(out).rstrip()


def _tokenize(text, line_offset):
    tokens = []
    seen_marker = False
    for number, raw in enumerate(text.splitlines(), 1 + line_offset):
        content = _strip_comment(raw.rstrip("\r"), number)
        if not content.strip():
            continue
        if content.strip() == "---":
            if tokens or seen_marker:
                raise YamlSubsetError("a second document marker; one document per file", number)
            seen_marker = True
            continue
        indent = len(content) - len(content.lstrip(" "))
        tokens.append(_Line(number, indent, content.strip()))
    return tokens


def _is_item(text):
    return text == "-" or text.startswith("- ")


# ---------------------------------------------------------------------------
# Block structure
# ---------------------------------------------------------------------------

def _parse_block(tokens, i, indent, path, lines):
    # A key's own line is already recorded by its mapping; only the root has
    # no recorded line yet.
    lines.setdefault(path, tokens[i].number)
    if _is_item(tokens[i].text):
        return _parse_list(tokens, i, indent, path, lines)
    return _parse_mapping(tokens, i, indent, path, lines)


def _nested_or_null(tokens, i, indent, path, lines):
    """The value of a `key:` / `-` with nothing after it: a nested block on the
    next line at indent+2, or null."""
    if i < len(tokens) and tokens[i].indent > indent:
        if tokens[i].indent != indent + 2:
            raise YamlSubsetError("inconsistent indentation (expected %d spaces)"
                                  % (indent + 2), tokens[i].number)
        return _parse_block(tokens, i, indent + 2, path, lines)
    return None, i


def _parse_mapping(tokens, i, indent, path, lines):
    result = {}
    while i < len(tokens):
        tok = tokens[i]
        if tok.indent < indent:
            break
        if tok.indent > indent:
            raise YamlSubsetError("inconsistent indentation (expected %d spaces)" % indent, tok.number)
        if _is_item(tok.text):
            raise YamlSubsetError("expected a mapping key, found a list item", tok.number)
        match = _KEY_RE.match(tok.text)
        if not match:
            raise YamlSubsetError("expected `key: value` (a mapping key followed by `: `)", tok.number)
        key, rest = match.group("key"), match.group("rest")
        if key in result:
            raise YamlSubsetError("duplicate key %r" % key, tok.number)
        child = path + (key,)
        lines[child] = tok.number
        i += 1
        if not rest:
            value, i = _nested_or_null(tokens, i, indent, child, lines)
        else:
            value = _parse_inline(rest, tok.number, child, lines)
            if i < len(tokens) and tokens[i].indent > indent:
                raise YamlSubsetError("unexpected indentation after a scalar value", tokens[i].number)
        result[key] = value
    return result, i


def _parse_list(tokens, i, indent, path, lines):
    result = []
    while i < len(tokens):
        tok = tokens[i]
        if tok.indent < indent:
            break
        if tok.indent > indent:
            raise YamlSubsetError("inconsistent indentation (expected %d spaces)" % indent, tok.number)
        if not _is_item(tok.text):
            raise YamlSubsetError("expected a list item (`- ...`), found a mapping key", tok.number)
        child = path + (len(result),)
        lines[child] = tok.number
        rest = tok.text[1:].strip()
        if not rest:
            value, i = _nested_or_null(tokens, i + 1, indent, child, lines)
        elif _is_item(rest):
            raise YamlSubsetError("a nested list item on the same line is not supported", tok.number)
        elif _KEY_RE.match(rest) and rest[0] not in ('"', "'"):
            # `- key: value`: a mapping whose first key sits after the dash.
            # Re-token the line at the mapping's own indent and let the mapping
            # parser read it and the keys that follow at that indent.
            tokens[i] = _Line(tok.number, indent + 2, rest)
            value, i = _parse_mapping(tokens, i, indent + 2, child, lines)
        else:
            value = _parse_inline(rest, tok.number, child, lines)
            i += 1
            if i < len(tokens) and tokens[i].indent > indent:
                raise YamlSubsetError("unexpected indentation after a scalar value", tokens[i].number)
        result.append(value)
    return result, i


# ---------------------------------------------------------------------------
# Inline values
# ---------------------------------------------------------------------------

def _parse_inline(text, number, path, lines):
    first = text[0]
    if first == "&":
        raise YamlSubsetError("anchors (&) are not supported", number)
    if first == "*":
        raise YamlSubsetError("aliases (*) are not supported", number)
    if first == "!":
        raise YamlSubsetError("tags (!) are not supported", number)
    if first in ("|", ">"):
        raise YamlSubsetError("block scalars (| and >) are not supported", number)
    if first == "{":
        raise YamlSubsetError("flow mappings ({}) are not supported", number)
    if first == "[":
        return _parse_inline_list(text, number, path, lines)
    if first in ('"', "'"):
        return _parse_quoted(text, number)
    return _bare(text)


def _parse_quoted(text, number):
    quote = text[0]
    out = []
    i = 1
    while i < len(text):
        ch = text[i]
        if quote == '"' and ch == "\\":
            if i + 1 >= len(text):
                raise YamlSubsetError("unterminated quote", number)
            out.append(_ESCAPES.get(text[i + 1], text[i + 1]))
            i += 2
            continue
        if ch == quote:
            if quote == "'" and text[i + 1:i + 2] == "'":
                out.append("'")
                i += 2
                continue
            remainder = text[i + 1:]
            if remainder.strip():
                raise YamlSubsetError("unexpected text after the closing quote: %r"
                                      % remainder.strip(), number)
            return "".join(out)
        out.append(ch)
        i += 1
    raise YamlSubsetError("unterminated quote", number)


def _split_inline_items(inner, number):
    items, buf, quote = [], [], None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf.append(ch)
            if quote == '"' and ch == "\\" and i + 1 < len(inner):
                buf.append(inner[i + 1])
                i += 2
                continue
            if ch == quote:
                if quote == "'" and inner[i + 1:i + 2] == "'":
                    buf.append("'")
                    i += 2
                    continue
                quote = None
        elif ch == ",":
            items.append("".join(buf).strip())
            buf = []
        else:
            if ch in ('"', "'") and not "".join(buf).strip():
                quote = ch
            buf.append(ch)
        i += 1
    if quote:
        raise YamlSubsetError("unterminated quote", number)
    items.append("".join(buf).strip())
    return items


def _parse_inline_list(text, number, path, lines):
    if not text.endswith("]"):
        raise YamlSubsetError("inline list is missing its closing `]` on the same line", number)
    inner = text[1:-1]
    if not inner.strip():
        return []
    values = []
    for index, item in enumerate(_split_inline_items(inner, number)):
        if not item:
            raise YamlSubsetError("empty inline list item", number)
        if item[0] == "[":
            raise YamlSubsetError("nested inline lists are not supported", number)
        lines[path + (index,)] = number
        values.append(_parse_inline(item, number, path + (index,), lines))
    return values


def _bare(text):
    if text in ("null", "~"):
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    if _INT_RE.match(text):
        return int(text)
    return text


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def parse(text, line_offset=0):
    """(value, lines): the document and a {path-tuple: line} map. `line_offset`
    shifts every reported line, for a document embedded in a larger file."""
    tokens = _tokenize(text, line_offset)
    lines = {}
    if not tokens:
        return None, lines
    if tokens[0].indent != 0:
        raise YamlSubsetError("unexpected indentation at the top level", tokens[0].number)
    value, i = _parse_block(tokens, 0, 0, (), lines)
    if i < len(tokens):
        raise YamlSubsetError("inconsistent indentation", tokens[i].number)
    return value, lines


def loads(text):
    """The document as plain Python objects (dict/list/str/int/bool/None)."""
    return parse(text)[0]


def parse_file(path):
    """(value, lines) for a file; a missing or unreadable file is a YamlSubsetError too."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise YamlSubsetError("cannot read: %s" % exc, path=path)
    try:
        return parse(text)
    except YamlSubsetError as exc:
        raise YamlSubsetError(exc.reason, exc.line, path)


def load_file(path):
    return parse_file(path)[0]


def line_for(lines, path):
    """The line of `path`, or of its nearest recorded ancestor (the root when
    nothing deeper was recorded); None for an empty map."""
    path = tuple(path)
    while path and path not in lines:
        path = path[:-1]
    return lines.get(path)


def split_front_matter(text):
    """(mapping, body) for a markdown file with a leading `---` front-matter
    block; (None, text) when there is none. Error lines count from the file
    top. A block that is empty parses as {}; one that is not a mapping raises."""
    if not text.startswith("---"):
        return None, text
    rows = text.splitlines(True)
    if rows[0].rstrip("\r\n") != "---":
        return None, text
    for index in range(1, len(rows)):
        if rows[index].rstrip("\r\n") != "---":
            continue
        value, _lines = parse("".join(rows[1:index]), line_offset=1)
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise YamlSubsetError("front matter must be a mapping", 2)
        return value, "".join(rows[index + 1:])
    return None, text
