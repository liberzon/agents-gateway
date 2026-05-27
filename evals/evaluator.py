import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import yaml  # type: ignore[import-untyped]


@dataclass
class TestCase:
    name: str
    input: str
    expected_patterns: List[str] = field(default_factory=list)
    expected_tools: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    test_case: TestCase
    passed: bool
    pattern_matches: List[bool] = field(default_factory=list)
    tool_matches: List[bool] = field(default_factory=list)
    missing_patterns: List[str] = field(default_factory=list)
    missing_tools: List[str] = field(default_factory=list)


def load_cases(path: str) -> List[TestCase]:
    """Load test cases from a YAML file."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Cases file not found: {path}")

    with open(file_path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, list):
        raise ValueError(f"Expected a list of test cases in {path}")

    cases = []
    for entry in raw:
        cases.append(
            TestCase(
                name=entry["name"],
                input=entry["input"],
                expected_patterns=entry.get("expected_patterns", []),
                expected_tools=entry.get("expected_tools", []),
            )
        )
    return cases


def check_patterns(content: str, patterns: List[str]) -> tuple[List[bool], List[str]]:
    """Check if content matches all regex patterns.

    Returns a tuple of (match results per pattern, list of missing patterns).
    """
    matches = []
    missing = []
    for pattern in patterns:
        matched = bool(re.search(pattern, content))
        matches.append(matched)
        if not matched:
            missing.append(pattern)
    return matches, missing


def check_tools(called_tools: List[str], expected_tools: List[str]) -> tuple[List[bool], List[str]]:
    """Check if expected tools were called.

    Returns a tuple of (match results per tool, list of missing tools).
    """
    matches = []
    missing = []
    for tool in expected_tools:
        found = tool in called_tools
        matches.append(found)
        if not found:
            missing.append(tool)
    return matches, missing


def evaluate_response(test_case: TestCase, response_content: str, called_tools: List[str]) -> EvalResult:
    """Evaluate an agent response against a test case."""
    pattern_matches, missing_patterns = check_patterns(response_content, test_case.expected_patterns)
    tool_matches, missing_tools = check_tools(called_tools, test_case.expected_tools)

    passed = len(missing_patterns) == 0 and len(missing_tools) == 0
    return EvalResult(
        test_case=test_case,
        passed=passed,
        pattern_matches=pattern_matches,
        tool_matches=tool_matches,
        missing_patterns=missing_patterns,
        missing_tools=missing_tools,
    )


def run_eval(cases_path: str) -> None:
    """Load cases and print a summary report.

    This function loads test cases and prints them for review.
    Actual evaluation requires agent responses, so this serves as
    a dry-run to validate case definitions.
    """
    cases = load_cases(cases_path)
    total = len(cases)

    print(f"Loaded {total} test case(s) from {cases_path}")
    print("-" * 60)

    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{total}] {case.name}")
        print(f"  Input: {case.input}")
        if case.expected_tools:
            print(f"  Expected tools: {', '.join(case.expected_tools)}")
        if case.expected_patterns:
            print(f"  Expected patterns: {', '.join(case.expected_patterns)}")

    print("\n" + "-" * 60)
    print(f"Total cases: {total}")
    print("Run with agent integration to execute evaluations.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent evaluation runner")
    parser.add_argument("--cases", required=True, help="Path to YAML test cases file")
    args = parser.parse_args()

    try:
        run_eval(args.cases)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
