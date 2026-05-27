import unittest

from prompts.parser import (
    extract_variables,
    normalize_template,
    parse_tags,
    parse_tools_config,
    render_template,
    validate_template,
)


class TestNormalizeTemplate(unittest.TestCase):
    """Tests for normalize_template function."""

    def test_removes_leading_trailing_whitespace(self):
        template = "  \n  Hello world  \n  "
        result = normalize_template(template)
        self.assertEqual(result, "Hello world")

    def test_preserves_internal_structure(self):
        template = """
        You are a helpful assistant.

        Please help the user with their request.
        """
        result = normalize_template(template)
        self.assertIn("You are a helpful assistant.", result)
        self.assertIn("Please help the user with their request.", result)

    def test_removes_trailing_spaces_per_line(self):
        template = "Line 1   \nLine 2   "
        result = normalize_template(template)
        lines = result.split("\n")
        self.assertEqual(lines[0], "Line 1")
        self.assertEqual(lines[1], "Line 2")


class TestExtractVariables(unittest.TestCase):
    """Tests for extract_variables function."""

    def test_single_brace_variables(self):
        template = "Hello {name}, welcome to {place}!"
        result = extract_variables(template)
        self.assertEqual(result, ["name", "place"])

    def test_double_brace_variables(self):
        template = "Hello {{name}}, welcome to {{place}}!"
        result = extract_variables(template)
        self.assertEqual(result, ["name", "place"])

    def test_removes_duplicates(self):
        template = "{name} {name} {other}"
        result = extract_variables(template)
        self.assertEqual(result, ["name", "other"])

    def test_empty_template(self):
        result = extract_variables("")
        self.assertEqual(result, [])


class TestValidateTemplate(unittest.TestCase):
    """Tests for validate_template function."""

    def test_valid_template(self):
        template = "You are a helpful assistant that helps with coding."
        is_valid, errors = validate_template(template)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_empty_template(self):
        is_valid, errors = validate_template("")
        self.assertFalse(is_valid)
        self.assertIn("Template cannot be empty", errors)

    def test_short_template(self):
        is_valid, errors = validate_template("Hi")
        self.assertFalse(is_valid)
        self.assertIn("Template is too short (minimum 10 characters)", errors)

    def test_unmatched_braces(self):
        template = "Hello {name, welcome to the app"
        is_valid, errors = validate_template(template)
        self.assertFalse(is_valid)
        self.assertTrue(any("Unmatched braces" in e for e in errors))


class TestRenderTemplate(unittest.TestCase):
    """Tests for render_template function."""

    def test_single_brace_render(self):
        template = "Hello {name}!"
        result = render_template(template, {"name": "World"})
        self.assertEqual(result, "Hello World!")

    def test_double_brace_render(self):
        template = "Hello {{name}}!"
        result = render_template(template, {"name": "World"})
        self.assertEqual(result, "Hello World!")

    def test_multiple_variables(self):
        template = "{greeting} {name}, welcome to {place}!"
        result = render_template(template, {"greeting": "Hi", "name": "Alice", "place": "Wonderland"})
        self.assertEqual(result, "Hi Alice, welcome to Wonderland!")

    def test_missing_variable_unchanged(self):
        template = "Hello {name}!"
        result = render_template(template, {})
        self.assertEqual(result, "Hello {name}!")


class TestParseToolsConfig(unittest.TestCase):
    """Tests for parse_tools_config function."""

    def test_valid_json(self):
        json_str = '[{"name": "search", "description": "Search the web"}]'
        result = parse_tools_config(json_str)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "search")

    def test_empty_string(self):
        result = parse_tools_config("")
        self.assertEqual(result, [])

    def test_none(self):
        result = parse_tools_config(None)
        self.assertEqual(result, [])

    def test_invalid_json(self):
        result = parse_tools_config("not valid json")
        self.assertEqual(result, [])


class TestParseTags(unittest.TestCase):
    """Tests for parse_tags function."""

    def test_valid_json(self):
        json_str = '["tag1", "tag2", "tag3"]'
        result = parse_tags(json_str)
        self.assertEqual(result, ["tag1", "tag2", "tag3"])

    def test_empty_string(self):
        result = parse_tags("")
        self.assertEqual(result, [])

    def test_none(self):
        result = parse_tags(None)
        self.assertEqual(result, [])

    def test_invalid_json(self):
        result = parse_tags("not valid json")
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
