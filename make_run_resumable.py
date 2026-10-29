
"""
Task 8: Resumable Instamart refund agent.

- Saves a checkpoint after every tool observation.
- Simulates a crash after the second tool execution.
- Resumes from the checkpoint without repeating completed tools.
- Validates the required S1 tool sequence and refund amount.

Run:
    python make_run_resumable.py
"""

import csv
import json
import os
import time
from pathlib import Path

import mock_llm

from refund_tools import (
    get_order,
    search_policy,
    calculate_refund,
    issue_refund,
    escalate_to_human,
)


# =========================================================
# 1. PATHS AND CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = BASE_DIR / "data" / "raw" / "agent_scenarios.csv"
STATE_DIR = BASE_DIR / "state"

STATE_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """
You are an Instamart customer support refund agent.

Use the available tools to inspect orders and refund policies.
Only completed orders can be refunded.
For delivered orders, delivery taking more than 45 minutes
qualifies for a full refund. Delivery within 45 minutes does
not qualify for a refund.
Refunds above INR 1000 must be escalated to a human lead.
Never claim that a refund was issued unless the tool confirms it.
Base your decision on the tool observations.
When finished, provide a concise answer beginning with a status
such as REFUND, DENIED, ESCALATE, or NOT_FOUND.
"""

MAX_ITERATIONS = 6
TOKEN_LIMIT = 6000
TIME_LIMIT_SECONDS = 10


# =========================================================
# 2. TOOL SCHEMAS
# =========================================================

TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Retrieve an order by its order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "Search the refund policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_refund",
            "description": "Calculate an eligible refund.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Issue an approved simulated refund.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "amount": {"type": "number"},
                },
                "required": ["order_id", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate a case to a human lead.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["order_id", "reason"],
            },
        },
    },
]

TOOL_FUNCTIONS = {
    "get_order": get_order,
    "search_policy": search_policy,
    "calculate_refund": calculate_refund,
    "issue_refund": issue_refund,
    "escalate_to_human": escalate_to_human,
}


# =========================================================
# 3. GENERAL HELPERS
# =========================================================

class SimulatedCrash(Exception):
    """Raised after a tool observation has been checkpointed."""


def load_scenarios():
    """Load the scenarios CSV."""
    if not SCENARIOS_FILE.exists():
        raise FileNotFoundError(
            f"Scenario file not found: {SCENARIOS_FILE}"
        )

    with SCENARIOS_FILE.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        return list(csv.DictReader(file))


def get_scenario(scenario_id):
    """Return the scenario with the requested ID."""
    for scenario in load_scenarios():
        if scenario.get("scenario_id") == scenario_id:
            return scenario

    raise ValueError(
        f"Scenario {scenario_id!r} was not found."
    )


def checkpoint_path(run_id):
    return STATE_DIR / f"{run_id}.json"


def to_plain_data(value):
    """Convert dictionaries, lists, and SDK-style objects to plain data."""
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, dict):
        return {
            key: to_plain_data(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [to_plain_data(item) for item in value]

    if hasattr(value, "model_dump"):
        return to_plain_data(value.model_dump())

    if hasattr(value, "to_dict"):
        return to_plain_data(value.to_dict())

    if hasattr(value, "__dict__"):
        return to_plain_data(vars(value))

    return str(value)


def read_field(value, field, default=None):
    """Read a field from a dictionary or an object."""
    if isinstance(value, dict):
        return value.get(field, default)

    return getattr(value, field, default)


def load_checkpoint(run_id):
    """Load a saved run checkpoint."""
    path = checkpoint_path(run_id)

    if not path.exists():
        raise FileNotFoundError(
            f"Checkpoint not found: {path}"
        )

    with path.open("r", encoding="utf-8") as file:
        checkpoint = json.load(file)

    if checkpoint.get("run_id") != run_id:
        raise ValueError("Checkpoint run ID does not match.")

    return checkpoint


def save_checkpoint(
    run_id,
    scenario_id,
    messages,
    tokens_used,
    step_number,
    tools_executed,
    llm_calls,
    steps,
    max_iterations,
    token_limit,
):
    """
    Save the complete agent state after a tool observation.

    The temporary file and os.replace reduce the risk of leaving
    a partially written checkpoint.
    """
    checkpoint = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "messages": messages,
        "tokens_used": tokens_used,
        "step_number": step_number,
        "tools_executed": tools_executed,
        "llm_calls": llm_calls,
        "steps": steps,
        "max_iterations": max_iterations,
        "token_limit": token_limit,
    }

    path = checkpoint_path(run_id)
    temporary_path = path.with_suffix(".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(
            checkpoint,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    os.replace(temporary_path, path)


# =========================================================
# 4. RESPONSE AND TOOL-CALL PARSING
# =========================================================

def get_message_from_response(response):
    """Extract the assistant message from the mock LLM response."""
    choices = read_field(response, "choices", [])

    if not choices:
        raise ValueError(
            f"Mock LLM response has no choices: "
            f"{to_plain_data(response)!r}"
        )

    return read_field(choices[0], "message")


def get_total_tokens(response):
    """Return reported token usage, or zero if unavailable."""
    usage = read_field(response, "usage", {})
    return int(read_field(usage, "total_tokens", 0) or 0)


def get_tool_calls(message):
    """Get tool calls from an assistant message."""
    return read_field(message, "tool_calls", None) or []


def get_tool_call_details(tool_call):
    """
    Support standard function-style calls and mock calls that
    store the tool name/arguments directly on the call object.
    """
    function = read_field(tool_call, "function", None)

    if function is None:
        # Direct mock format.
        tool_name = (
            read_field(tool_call, "name")
            or read_field(tool_call, "tool_name")
        )

        raw_arguments = read_field(tool_call, "arguments", None)

        if raw_arguments is None:
            raw_arguments = read_field(tool_call, "args", {})
    else:
        # Standard function-call format.
        tool_name = (
            read_field(function, "name")
            or read_field(function, "tool_name")
        )

        raw_arguments = read_field(
            function, "arguments", None
        )

        if raw_arguments is None:
            raw_arguments = read_field(function, "args", {})

    call_id = read_field(tool_call, "id", "tool_call")

    if isinstance(raw_arguments, str):
        arguments = json.loads(raw_arguments)
    else:
        arguments = raw_arguments or {}

    if not isinstance(arguments, dict):
        raise ValueError(
            f"Arguments for {tool_name!r} must be a dictionary."
        )

    if not tool_name:
        raise ValueError(
            "Could not determine the tool name. Actual tool call: "
            f"{to_plain_data(tool_call)!r}"
        )

    if tool_name not in TOOL_FUNCTIONS:
        raise ValueError(
            f"Unknown tool name {tool_name!r}. "
            f"Available tools: {list(TOOL_FUNCTIONS)}"
        )

    return call_id, tool_name, arguments


def message_to_dict(message):
    """Make an assistant message suitable for checkpoint JSON."""
    data = to_plain_data(message)

    if not isinstance(data, dict):
        raise ValueError(
            f"Assistant message is not a dictionary: {data!r}"
        )

    data.setdefault("role", "assistant")
    return data


def execute_tool(tool_name, arguments):
    """Execute a tool only if it is in the allowlist."""
    if tool_name not in TOOL_FUNCTIONS:
        return {"error": f"Tool not allowed: {tool_name}"}

    try:
        result = TOOL_FUNCTIONS[tool_name](**arguments)
        return to_plain_data(result)
    except Exception as exc:
        return {
            "error": f"{type(exc).__name__}: {exc}"
        }


# =========================================================
# 5. RESUMABLE AGENT
# =========================================================

def run_agent(
    user_message=None,
    scenario_id="S1",
    max_iterations=MAX_ITERATIONS,
    token_limit=TOKEN_LIMIT,
    time_limit_seconds=TIME_LIMIT_SECONDS,
    run_id=None,
    crash_after_tool_executions=None,
    _resume_state=None,
):
    """Run a new agent session or continue from a checkpoint."""

    if run_id is None:
        run_id = f"{scenario_id}-run"

    started_at = time.monotonic()

    if _resume_state is not None:
        # Restore the exact saved state.
        scenario_id = _resume_state["scenario_id"]
        messages = _resume_state["messages"]
        tokens_used = int(_resume_state["tokens_used"])
        tools_executed = list(
            _resume_state.get("tools_executed", [])
        )
        llm_calls = int(_resume_state.get("llm_calls", 0))
        steps = list(_resume_state.get("steps", []))
        start_iteration = int(
            _resume_state.get("step_number", 0)
        )
        max_iterations = int(
            _resume_state.get("max_iterations", max_iterations)
        )
        token_limit = int(
            _resume_state.get("token_limit", token_limit)
        )
    else:
        if user_message is None:
            user_message = get_scenario(scenario_id)["message"]

        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ]

        tokens_used = 0
        tools_executed = []
        llm_calls = 0
        steps = []
        start_iteration = 0

    def result(status, final_answer):
        return {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "status": status,
            "final_answer": final_answer,
            "tools_executed": list(tools_executed),
            "steps": list(steps),
            "llm_calls": llm_calls,
            "tokens_used": tokens_used,
        }

    for iteration in range(start_iteration, max_iterations):

        if time.monotonic() - started_at > time_limit_seconds:
            return result(
                "FALLBACK_TIMEOUT",
                "Human review required: time limit reached.",
            )

        try:
            response = mock_llm.chat(
                messages,
                tools=TOOLS_SPEC,
            )
        except Exception as exc:
            return result(
                "FALLBACK_ERROR",
                f"Human review required: LLM error ({exc}).",
            )

        llm_calls += 1
        tokens_used += get_total_tokens(response)

        # Do not execute tools if the response exceeds the budget.
        if tokens_used > token_limit:
            return result(
                "FALLBACK_TOKEN_LIMIT",
                "FALLBACK: token limit exceeded; human review required.",
            )

        assistant_message = get_message_from_response(response)
        tool_calls = get_tool_calls(assistant_message)

        if not tool_calls:
            final_answer = (
                read_field(assistant_message, "content", "")
                or "Human review required: empty final answer."
            )

            status = (
                str(final_answer).split(":", 1)[0].strip().upper()
            )

            return result(status, final_answer)

        # Append the assistant's tool-call message once.
        messages.append(message_to_dict(assistant_message))

        for tool_call in tool_calls:
            call_id, tool_name, arguments = get_tool_call_details(
                tool_call
            )

            print(f"Executing tool: {tool_name}", flush=True)

            observation = execute_tool(tool_name, arguments)

            # Append the tool observation first.
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": tool_name,
                "content": json.dumps(
                    observation,
                    ensure_ascii=False,
                    default=str,
                ),
            })

            # Record the actual tool name, never None.
            tools_executed.append(tool_name)

            steps.append({
                "iteration": iteration + 1,
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": observation,
            })

            # Checkpoint AFTER every observation is appended.
            save_checkpoint(
                run_id=run_id,
                scenario_id=scenario_id,
                messages=messages,
                tokens_used=tokens_used,
                step_number=iteration + 1,
                tools_executed=tools_executed,
                llm_calls=llm_calls,
                steps=steps,
                max_iterations=max_iterations,
                token_limit=token_limit,
            )

            print(
                f"Checkpoint saved after tool #{len(tools_executed)}",
                flush=True,
            )

            # Crash only after the checkpoint has been saved.
            if (
                crash_after_tool_executions is not None
                and len(tools_executed)
                == crash_after_tool_executions
            ):
                raise SimulatedCrash(
                    f"Simulated crash after tool #{len(tools_executed)}. "
                    f"Checkpoint: {checkpoint_path(run_id)}"
                )

    return result(
        "FALLBACK_MAX_ITERATIONS",
        "Human review required: maximum iterations reached.",
    )


# =========================================================
# 6. RESUME FROM CHECKPOINT
# =========================================================

def resume_agent(
    run_id,
    time_limit_seconds=TIME_LIMIT_SECONDS,
):
    """Restore a checkpoint and continue the agent run."""
    checkpoint = load_checkpoint(run_id)

    print(
        f"Loaded checkpoint for {run_id}; "
        f"completed tools: {checkpoint.get('tools_executed', [])}",
        flush=True,
    )

    return run_agent(
        scenario_id=checkpoint["scenario_id"],
        max_iterations=checkpoint.get(
            "max_iterations", MAX_ITERATIONS
        ),
        token_limit=checkpoint.get("token_limit", TOKEN_LIMIT),
        time_limit_seconds=time_limit_seconds,
        run_id=run_id,
        _resume_state=checkpoint,
    )


# =========================================================
# 7. TASK 8 DEMONSTRATION
# =========================================================

def main():
    scenario = get_scenario("S1")
    run_id = "S1-task8-resume-demo"
    path = checkpoint_path(run_id)

    # Remove only this demo's previous checkpoint so the test
    # always starts from the beginning.
    if path.exists():
        path.unlink()

    print("=" * 60)
    print("TASK 8: RESUMABLE AGENT DEMONSTRATION")
    print("=" * 60)
    print("Scenario: S1")
    print(f"Run ID: {run_id}")
    print()

    # Part 1: simulate a crash after tool execution #2.
    try:
        run_agent(
            user_message=scenario["message"],
            scenario_id="S1",
            max_iterations=MAX_ITERATIONS,
            token_limit=TOKEN_LIMIT,
            time_limit_seconds=TIME_LIMIT_SECONDS,
            run_id=run_id,
            crash_after_tool_executions=2,
        )
    except SimulatedCrash as exc:
        print()
        print("=== SIMULATED CRASH ===")
        print(exc)
        print()
    else:
        raise AssertionError(
            "The simulated crash did not occur. "
            "Check whether the mock LLM produced tool calls."
        )

    # Confirm that exactly two tools were checkpointed.
    checkpoint = load_checkpoint(run_id)
    saved_tools = checkpoint.get("tools_executed", [])

    print("Tools saved before crash:", saved_tools)
    print("Saved step number:", checkpoint.get("step_number"))

    assert len(saved_tools) == 2, (
        "Expected exactly two saved tool executions; "
        f"found {saved_tools!r}. Check tool-call parsing."
    )

    # Part 2: resume from the saved messages and state.
    print()
    print("=== RESUMING AGENT ===")

    final_result = resume_agent(run_id)

    print()
    print("=== FINAL RESULT ===")
    print("Status:", final_result["status"])
    print("Final answer:", final_result["final_answer"])
    print("LLM calls:", final_result["llm_calls"])
    print("Tokens used:", final_result["tokens_used"])
    print()
    print("Tools executed across crash and resume:")

    for number, name in enumerate(
        final_result["tools_executed"], start=1
    ):
        print(f"{number}. {name}")

    expected_tools = [
        "get_order",
        "search_policy",
        "calculate_refund",
        "issue_refund",
    ]

    assert final_result["tools_executed"] == expected_tools, (
        "Incorrect tool sequence.\n"
        f"Expected: {expected_tools}\n"
        f"Actual: {final_result['tools_executed']}"
    )

    assert final_result["status"] == "REFUND", (
        f"Expected REFUND; got {final_result['status']!r}"
    )

    assert "128.25" in str(final_result["final_answer"]), (
        "Expected INR 128.25 in the final answer; got "
        f"{final_result['final_answer']!r}"
    )

    result_path = STATE_DIR / f"{run_id}_result.json"

    with result_path.open("w", encoding="utf-8") as file:
        json.dump(
            final_result,
            file,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    print()
    print("Checkpoint file:", path)
    print("Final result file:", result_path)
    print("Task 8 resume test passed.")


if __name__ == "__main__":
    main()
