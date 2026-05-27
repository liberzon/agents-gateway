import os
import tempfile
import unittest

os.environ["TESTING"] = "true"

import yaml  # type: ignore[import-untyped]

from evals.evaluator import (
    TestCase,
    check_patterns,
    check_tools,
    evaluate_response,
    load_cases,
)


class TestLoadCases(unittest.TestCase):
    """Test loading test cases from YAML."""

    def test_load_cases(self):
        """Loads YAML file and returns a list of TestCase objects."""
        cases_data = [
            {
                "name": "greet user",
                "input": "Hello there",
                "expected_patterns": ["hello", "hi"],
                "expected_tools": ["greet"],
            },
            {
                "name": "search query",
                "input": "Find documents about AI",
                "expected_patterns": ["AI"],
                "expected_tools": ["search"],
            },
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(cases_data, f)
            tmp_path = f.name

        try:
            cases = load_cases(tmp_path)
            self.assertEqual(len(cases), 2)
            self.assertIsInstance(cases[0], TestCase)
            self.assertEqual(cases[0].name, "greet user")
            self.assertEqual(cases[0].input, "Hello there")
            self.assertEqual(cases[0].expected_patterns, ["hello", "hi"])
            self.assertEqual(cases[0].expected_tools, ["greet"])
            self.assertEqual(cases[1].name, "search query")
        finally:
            os.unlink(tmp_path)

    def test_load_cases_file_not_found(self):
        """Raises FileNotFoundError for missing file."""
        with self.assertRaises(FileNotFoundError):
            load_cases("/nonexistent/path/cases.yaml")

    def test_load_cases_defaults(self):
        """Missing optional fields default to empty lists."""
        cases_data = [{"name": "minimal", "input": "just input"}]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(cases_data, f)
            tmp_path = f.name

        try:
            cases = load_cases(tmp_path)
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].expected_patterns, [])
            self.assertEqual(cases[0].expected_tools, [])
        finally:
            os.unlink(tmp_path)


class TestCheckPatterns(unittest.TestCase):
    """Test regex pattern matching against content."""

    def test_check_patterns_match(self):
        """All regex patterns match the content."""
        content = "The meeting is scheduled for 2pm with alice@example.com"
        patterns = [r"alice@example\.com", r"\d+pm"]

        matches, missing = check_patterns(content, patterns)

        self.assertEqual(matches, [True, True])
        self.assertEqual(missing, [])

    def test_check_patterns_no_match(self):
        """Pattern does not match the content."""
        content = "Hello world"
        patterns = [r"goodbye", r"world"]

        matches, missing = check_patterns(content, patterns)

        self.assertEqual(matches, [False, True])
        self.assertEqual(missing, ["goodbye"])

    def test_check_patterns_empty(self):
        """Empty patterns list returns empty results."""
        matches, missing = check_patterns("any content", [])

        self.assertEqual(matches, [])
        self.assertEqual(missing, [])


class TestCheckTools(unittest.TestCase):
    """Test tool presence checking."""

    def test_check_tools_match(self):
        """All expected tools are present in called tools."""
        called = ["search", "summarize", "greet"]
        expected = ["search", "summarize"]

        matches, missing = check_tools(called, expected)

        self.assertEqual(matches, [True, True])
        self.assertEqual(missing, [])

    def test_check_tools_missing(self):
        """Missing tool is reported."""
        called = ["search"]
        expected = ["search", "send_email"]

        matches, missing = check_tools(called, expected)

        self.assertEqual(matches, [True, False])
        self.assertEqual(missing, ["send_email"])

    def test_check_tools_empty_expected(self):
        """No expected tools always passes."""
        matches, missing = check_tools(["search"], [])

        self.assertEqual(matches, [])
        self.assertEqual(missing, [])


class TestEvaluateResponse(unittest.TestCase):
    """Test full evaluation of an agent response."""

    def test_evaluate_response_pass(self):
        """Full evaluation passes when all patterns and tools match."""
        case = TestCase(
            name="schedule test",
            input="Schedule meeting",
            expected_patterns=[r"meeting", r"scheduled"],
            expected_tools=["schedule_meeting"],
        )

        result = evaluate_response(
            test_case=case,
            response_content="Your meeting has been scheduled for tomorrow",
            called_tools=["schedule_meeting"],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.missing_patterns, [])
        self.assertEqual(result.missing_tools, [])
        self.assertEqual(result.pattern_matches, [True, True])
        self.assertEqual(result.tool_matches, [True])

    def test_evaluate_response_fail(self):
        """Evaluation fails when a pattern is missing."""
        case = TestCase(
            name="email test",
            input="Send email",
            expected_patterns=[r"email", r"sent successfully"],
            expected_tools=["send_email"],
        )

        result = evaluate_response(
            test_case=case,
            response_content="Your email is being prepared",
            called_tools=["send_email"],
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.missing_patterns, ["sent successfully"])
        self.assertEqual(result.missing_tools, [])

    def test_evaluate_response_fail_missing_tool(self):
        """Evaluation fails when an expected tool was not called."""
        case = TestCase(
            name="multi tool test",
            input="Search and email results",
            expected_patterns=[r"results"],
            expected_tools=["search", "send_email"],
        )

        result = evaluate_response(
            test_case=case,
            response_content="Here are your results",
            called_tools=["search"],
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.missing_tools, ["send_email"])


if __name__ == "__main__":
    unittest.main()
