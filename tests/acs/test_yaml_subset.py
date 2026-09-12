"""Contract tests for acs_lib.yamlsubset -- the stdlib-only YAML subset the
workflow files (workflows/ship.yaml, workflows/phases.yaml) and the ticket
artifacts' front matter are written in.

The subset is deliberately strict: `#` comments, `key: value` mappings nested
by 2-space indentation, block lists (`- item`, `- key: value` mappings), inline
scalar lists `[a, b]`, and scalars (double/single-quoted strings, bare strings,
integers, `true`/`false`, `null`/`~`). Everything else -- anchors, aliases, tags,
flow mappings `{}`, block scalars `|`/`>`, tabs, duplicate keys, inconsistent
indentation -- is rejected with a YamlSubsetError that names the LINE, so a
consumer editing an override file is pointed at the exact offending line.

Every accepted form and every rejected form is pinned here; the rejected forms
assert the reported line number, not just that parsing failed.

Run:  python3 -m unittest tests.acs.test_yaml_subset -v
"""

import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(REPO_ROOT, "plugins", "acs", "hooks", "scripts")
sys.path.insert(0, SCRIPTS)

import acs_lib as lib  # noqa: E402
from acs_lib import yamlsubset  # noqa: E402


class TestAcceptedScalars(unittest.TestCase):

    def test_bare_string(self):
        self.assertEqual(yamlsubset.loads("name: ship"), {"name": "ship"})

    def test_bare_string_keeps_inner_spaces_and_braces(self):
        self.assertEqual(yamlsubset.loads("args: --for-ticket {ticket_id}"),
                         {"args": "--for-ticket {ticket_id}"})

    def test_double_quoted_string_with_escapes(self):
        self.assertEqual(yamlsubset.loads(r'a: "x \"y\" \\ z\n"'), {"a": 'x "y" \\ z\n'})

    def test_double_quoted_string_keeps_a_hash(self):
        self.assertEqual(yamlsubset.loads('a: "not # a comment"'), {"a": "not # a comment"})

    def test_single_quoted_string_with_doubled_quote_escape(self):
        self.assertEqual(yamlsubset.loads("a: 'it''s'"), {"a": "it's"})

    def test_integers(self):
        self.assertEqual(yamlsubset.loads("a: 1\nb: -2\nc: +3\nd: 0"),
                         {"a": 1, "b": -2, "c": 3, "d": 0})

    def test_integers_are_ints_not_bools(self):
        value = yamlsubset.loads("a: 1")["a"]
        self.assertIs(type(value), int)

    def test_booleans(self):
        self.assertEqual(yamlsubset.loads("a: true\nb: false"), {"a": True, "b": False})

    def test_booleans_are_bools(self):
        self.assertIs(yamlsubset.loads("a: true")["a"], True)

    def test_null_spellings(self):
        self.assertEqual(yamlsubset.loads("a: null\nb: ~\nc:"), {"a": None, "b": None, "c": None})

    def test_quoted_true_and_digits_stay_strings(self):
        self.assertEqual(yamlsubset.loads('a: "true"\nb: \'1\''), {"a": "true", "b": "1"})

    def test_a_decimal_is_a_bare_string_not_a_float(self):
        """Floats are outside the subset; a decimal reads as a bare string
        rather than being silently coerced."""
        self.assertEqual(yamlsubset.loads("a: 1.5"), {"a": "1.5"})


class TestAcceptedStructure(unittest.TestCase):

    def test_comments_and_blank_lines_are_ignored(self):
        text = "# leading comment\n\nname: ship  # trailing comment\n\n# another\nversion: 1\n"
        self.assertEqual(yamlsubset.loads(text), {"name": "ship", "version": 1})

    def test_a_leading_document_marker_is_tolerated(self):
        self.assertEqual(yamlsubset.loads("---\na: 1\n"), {"a": 1})

    def test_nested_mapping_by_two_spaces(self):
        text = "outer:\n  inner:\n    leaf: 1\n  other: two\n"
        self.assertEqual(yamlsubset.loads(text),
                         {"outer": {"inner": {"leaf": 1}, "other": "two"}})

    def test_block_list_of_scalars(self):
        self.assertEqual(yamlsubset.loads("xs:\n  - a\n  - 2\n  - true\n"),
                         {"xs": ["a", 2, True]})

    def test_block_list_of_mappings(self):
        text = "steps:\n  - id: a\n    skill: code\n  - id: b\n    needs: [a]\n"
        self.assertEqual(yamlsubset.loads(text), {
            "steps": [{"id": "a", "skill": "code"}, {"id": "b", "needs": ["a"]}]})

    def test_block_list_mapping_with_nested_mapping(self):
        text = ("steps:\n  - id: x\n    on_fail:\n      relay_to: code\n"
                "      max_loops: 2\n  - id: y\n")
        self.assertEqual(yamlsubset.loads(text), {"steps": [
            {"id": "x", "on_fail": {"relay_to": "code", "max_loops": 2}}, {"id": "y"}]})

    def test_dash_alone_opens_a_nested_block(self):
        text = "xs:\n  -\n    a: 1\n  -\n    - inner\n"
        self.assertEqual(yamlsubset.loads(text), {"xs": [{"a": 1}, ["inner"]]})

    def test_top_level_list(self):
        self.assertEqual(yamlsubset.loads("- a\n- b\n"), ["a", "b"])

    def test_inline_scalar_list(self):
        self.assertEqual(yamlsubset.loads('xs: [a, "b, c", 3, true, null]'),
                         {"xs": ["a", "b, c", 3, True, None]})

    def test_empty_inline_list(self):
        self.assertEqual(yamlsubset.loads("xs: []"), {"xs": []})

    def test_inline_list_as_a_block_list_item(self):
        self.assertEqual(yamlsubset.loads("xs:\n  - [a, b]\n"), {"xs": [["a", "b"]]})

    def test_empty_document_is_none(self):
        self.assertIsNone(yamlsubset.loads(""))
        self.assertIsNone(yamlsubset.loads("# only a comment\n"))

    def test_keys_may_carry_dashes_dots_and_underscores(self):
        self.assertEqual(yamlsubset.loads("stop_after: x\nmax-parallel: 1\na.b: 2"),
                         {"stop_after": "x", "max-parallel": 1, "a.b": 2})


class TestLineMap(unittest.TestCase):
    """parse() returns the value plus a path -> line map, which is what lets the
    workflow validator report a schema failure at its source line."""

    def test_parse_records_the_line_of_every_node(self):
        text = "version: 1\nsteps:\n  - id: a\n    skill: code\n  - id: b\n"
        value, lines = yamlsubset.parse(text)
        self.assertEqual(value["steps"][1]["id"], "b")
        self.assertEqual(lines[()], 1)
        self.assertEqual(lines[("version",)], 1)
        self.assertEqual(lines[("steps",)], 2)
        self.assertEqual(lines[("steps", 0)], 3)
        self.assertEqual(lines[("steps", 0, "skill")], 4)
        self.assertEqual(lines[("steps", 1)], 5)
        self.assertEqual(lines[("steps", 1, "id")], 5)

    def test_inline_list_items_map_to_their_line(self):
        _value, lines = yamlsubset.parse("a: 1\nxs: [p, q]\n")
        self.assertEqual(lines[("xs", 1)], 2)

    def test_line_for_walks_up_to_the_nearest_recorded_ancestor(self):
        _value, lines = yamlsubset.parse("a:\n  b: 1\n")
        self.assertEqual(yamlsubset.line_for(lines, ("a", "b", "missing")), 2)
        self.assertEqual(yamlsubset.line_for(lines, ("zzz",)), 1)


class TestRejectedForms(unittest.TestCase):
    """Each rejected form names the offending line."""

    def assertRejects(self, text, line, fragment):
        with self.assertRaises(yamlsubset.YamlSubsetError) as ctx:
            yamlsubset.loads(text)
        self.assertEqual(ctx.exception.line, line,
                         "expected line %d, got %r" % (line, ctx.exception))
        self.assertIn(fragment, str(ctx.exception))
        self.assertIn("line %d" % line, str(ctx.exception))

    def test_anchor(self):
        self.assertRejects("a: 1\nb: &x 2\n", 2, "anchor")

    def test_alias(self):
        self.assertRejects("a: 1\nb: *x\n", 2, "alias")

    def test_tag(self):
        self.assertRejects("a: !!str 1\n", 1, "tag")

    def test_flow_mapping(self):
        self.assertRejects("a: 1\nb: {x: 1}\n", 2, "flow mapping")

    def test_flow_mapping_inside_an_inline_list(self):
        self.assertRejects("xs: [a, {b: 1}]\n", 1, "flow mapping")

    def test_nested_inline_list(self):
        self.assertRejects("xs: [a, [b]]\n", 1, "nested")

    def test_literal_block_scalar(self):
        self.assertRejects("a: 1\nb: |\n  text\n", 2, "block scalar")

    def test_folded_block_scalar(self):
        self.assertRejects("b: >\n  text\n", 1, "block scalar")

    def test_tab_in_indentation(self):
        self.assertRejects("a:\n\tb: 1\n", 2, "tab")

    def test_tab_inside_a_bare_value(self):
        self.assertRejects("a: x\ty\n", 1, "tab")

    def test_tab_inside_a_quoted_value_is_fine(self):
        self.assertEqual(yamlsubset.loads('a: "x\ty"'), {"a": "x\ty"})

    def test_duplicate_key(self):
        self.assertRejects("a: 1\nb: 2\na: 3\n", 3, "duplicate key")

    def test_duplicate_key_inside_a_list_mapping(self):
        self.assertRejects("xs:\n  - id: a\n    id: b\n", 3, "duplicate key")

    def test_odd_indentation(self):
        self.assertRejects("a:\n   b: 1\n", 2, "indent")

    def test_dedent_to_no_open_level(self):
        self.assertRejects("a:\n    b: 1\n  c: 2\n", 2, "indent")

    def test_indented_line_after_a_scalar_value(self):
        self.assertRejects("a: 1\n  b: 2\n", 2, "indent")

    def test_list_item_where_a_mapping_key_is_expected(self):
        self.assertRejects("a: 1\n- b\n", 2, "mapping")

    def test_mapping_key_where_a_list_item_is_expected(self):
        self.assertRejects("- a\nb: 1\n", 2, "list item")

    def test_unterminated_double_quote(self):
        self.assertRejects('a: "oops\n', 1, "quote")

    def test_text_after_a_closing_quote(self):
        self.assertRejects('a: "x" y\n', 1, "after")

    def test_unterminated_inline_list(self):
        self.assertRejects("xs: [a, b\n", 1, "]")

    def test_empty_inline_list_item(self):
        self.assertRejects("xs: [a, , b]\n", 1, "empty")

    def test_line_without_a_key(self):
        self.assertRejects("a: 1\njust text\n", 2, "key")

    def test_key_without_separator_space(self):
        self.assertRejects("a:1\n", 1, "key")

    def test_second_document_marker(self):
        self.assertRejects("a: 1\n---\nb: 2\n", 2, "document")

    def test_multi_line_inline_list_is_rejected(self):
        """Inline lists are single-line: a wrapped one is reported where it
        opens, not swallowed as a bare string."""
        self.assertRejects("xs: [a,\n  b]\n", 1, "]")

    def test_error_carries_path_when_available(self):
        with self.assertRaises(yamlsubset.YamlSubsetError) as ctx:
            yamlsubset.loads("a:\n  b: &x 1\n")
        self.assertEqual(ctx.exception.line, 2)


class TestFilesAndFrontMatter(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="acs-yaml-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def _write(self, name, text):
        path = os.path.join(self.tmp, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_load_file_parses_the_file(self):
        path = self._write("a.yaml", "a: 1\n")
        self.assertEqual(yamlsubset.load_file(path), {"a": 1})

    def test_load_file_error_names_the_path_and_line(self):
        path = self._write("b.yaml", "a: 1\nb: {x}\n")
        with self.assertRaises(yamlsubset.YamlSubsetError) as ctx:
            yamlsubset.load_file(path)
        self.assertEqual(ctx.exception.line, 2)
        self.assertEqual(ctx.exception.path, path)
        self.assertIn(path, str(ctx.exception))

    def test_load_file_missing_raises_a_yaml_subset_error(self):
        with self.assertRaises(yamlsubset.YamlSubsetError):
            yamlsubset.load_file(os.path.join(self.tmp, "nope.yaml"))

    def test_split_front_matter_returns_mapping_and_body(self):
        text = "---\nticket: SHOP-1\napi_surface: true\n---\n# Title\n\nbody\n"
        front, body = yamlsubset.split_front_matter(text)
        self.assertEqual(front, {"ticket": "SHOP-1", "api_surface": True})
        self.assertEqual(body, "# Title\n\nbody\n")

    def test_split_front_matter_without_a_block(self):
        front, body = yamlsubset.split_front_matter("# Title\n")
        self.assertIsNone(front)
        self.assertEqual(body, "# Title\n")

    def test_split_front_matter_unterminated_block(self):
        front, body = yamlsubset.split_front_matter("---\na: 1\nno end\n")
        self.assertIsNone(front)
        self.assertEqual(body, "---\na: 1\nno end\n")

    def test_split_front_matter_error_lines_count_from_the_file_top(self):
        with self.assertRaises(yamlsubset.YamlSubsetError) as ctx:
            yamlsubset.split_front_matter("---\na: 1\nb: &x 2\n---\n")
        self.assertEqual(ctx.exception.line, 3)

    def test_facade_exports_the_module_and_the_error(self):
        self.assertIs(lib.yamlsubset, yamlsubset)
        self.assertIs(lib.YamlSubsetError, yamlsubset.YamlSubsetError)


if __name__ == "__main__":
    unittest.main()
