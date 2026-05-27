# Evaluation Framework

Lightweight framework for testing agent responses against expected patterns and tool calls.

## How It Works

The evaluator loads test cases from YAML files and checks agent responses for:
- **Pattern matching**: Regex patterns that should appear in the response content
- **Tool verification**: Tools that should have been called during the interaction

## YAML Test Case Format

Each test case has:

```yaml
- name: "descriptive test name"
  input: "the user message to send to the agent"
  expected_tools: ["tool_name_1", "tool_name_2"]
  expected_patterns: ["regex_pattern_1", "literal_text"]
```

- `name` (required): Human-readable test name
- `input` (required): The user message
- `expected_tools` (optional): List of tool names the agent should call
- `expected_patterns` (optional): List of regex patterns to match in the response

## Running

Dry-run to validate case definitions:

```bash
python -m evals.evaluator --cases evals/cases/sample.yaml
```

Programmatic usage with agent responses:

```python
from evals.evaluator import load_cases, evaluate_response

cases = load_cases("evals/cases/sample.yaml")
for case in cases:
    response_content = "..."  # from agent
    called_tools = ["schedule_meeting"]  # from agent run
    result = evaluate_response(case, response_content, called_tools)
    print(f"{case.name}: {'PASS' if result.passed else 'FAIL'}")
```

## Adding New Cases

1. Create a new YAML file in `evals/cases/` (or add to an existing one)
2. Follow the format above
3. Run the dry-run command to validate syntax
4. Integrate with your agent test harness to execute
