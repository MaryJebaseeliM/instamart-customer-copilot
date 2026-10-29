"""Task 6: ReAct agent loop and seven-scenario evaluation."""

from pathlib import Path
from datetime import datetime, timezone
import csv
import json
import time

import mock_llm
from refund_tools import call_tool, TOOLS_SPEC


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------
ROOT = Path(__file__).resolve().parent
SCENARIOS_FILE = ROOT / "data" / "raw" / "agent_scenarios.csv"
OUTPUT_FILE = ROOT / "outputs" / "agent_runs.jsonl"

SYSTEM_PROMPT = """AGENT
You are an Instamart refund support agent.
Use the available tools to look up orders and follow refund policy.
Only completed orders can receive refunds.
Delivery taking more than 45 minutes qualifies for a full refund.
Refunds above INR 1000 must be escalated to a human.
Never claim an action succeeded unless the tool confirms it.
"""


# --------------------------------------------------
# HELPER: SAFE JSON SERIALIZATION
# --------------------------------------------------
def json_string(value):
    """Convert a value into a JSON string for tool messages."""
    return json.dumps(value, ensure_ascii=False, default=str)


# --------------------------------------------------
# HELPER: EXTRACT TOOL CALL FIELDS
# --------------------------------------------------
def extract_tool_call(tool_call):
    """Support the SimpleNamespace objects returned by mock_llm."""

    name = tool_call.name
    arguments = tool_call.arguments

    # Support arguments returned as either a dict or JSON string.
    if isinstance(arguments, str):
        arguments = json.loads(arguments)

    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a dictionary.")

    return {
        "id": tool_call.id,
        "name": name,
        "arguments": arguments,
    }


# --------------------------------------------------
# TASK 6: REACT LOOP
# --------------------------------------------------
def run_agent(
    user_message,
    scenario_id,
    max_iterations=6,
    token_limit=6000,
    time_limit_seconds=10,
):
    """
    Run the ReAct agent.

    Returns:
        status
        final_answer
        steps
        llm_calls
        tokens_used
    """

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    steps = []
    llm_calls = 0
    tokens_used = 0
    final_answer = None
    started = time.monotonic()

    for iteration in range(max_iterations):

        # Stop safely if the time limit has already been reached.
        if time.monotonic() - started >= time_limit_seconds:
            final_answer = (
                "FALLBACK: time limit reached; human review required."
            )
            break

        try:
            response = mock_llm.chat(messages, tools=TOOLS_SPEC)
        except mock_llm.TransientLLMError as exc:
            final_answer = (
                f"FALLBACK: model call failed ({exc}); "
                "human review required."
            )
            break
        except Exception as exc:
            final_answer = (
                f"FALLBACK: unexpected model error ({exc}); "
                "human review required."
            )
            break

        llm_calls += 1

        # Use the token estimator provided by the supplied mock LLM.
        call_tokens = response.usage.total_tokens
        tokens_used += call_tokens

        # Respect the configured token budget.
        if tokens_used > token_limit:
            final_answer = (
                "FALLBACK: token limit exceeded; "
                "human review required."
            )
            break

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        # No tool calls means the model has produced its final answer.
        if not tool_calls:
            final_answer = message.content or (
                "FALLBACK: model returned an empty answer."
            )
            break

        # Append the assistant's tool-call message.
        serialized_calls = []

        for tool_call in tool_calls:
            call = extract_tool_call(tool_call)

            serialized_calls.append({
                "id": call["id"],
                "name": call["name"],
                "arguments": call["arguments"],
            })

        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": serialized_calls,
        })

        # Execute each requested tool and append its observation.
        for call in serialized_calls:
            if time.monotonic() - started >= time_limit_seconds:
                final_answer = (
                    "FALLBACK: time limit reached; "
                    "human review required."
                )
                break

            tool_name = call["name"]
            arguments = call["arguments"]

            try:
                observation = call_tool(tool_name, arguments)
            except Exception as exc:
                observation = {"error": str(exc)}

            steps.append({
                "tool_name": tool_name,
                "arguments": arguments,
                "observation": observation,
            })

            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "name": tool_name,
                "content": json_string(observation),
            })

        if final_answer is not None:
            break

    # If all allowed iterations were used without a final answer,
    # return a safe fallback.
    if final_answer is None:
        final_answer = (
            "FALLBACK: maximum iterations reached; "
            "human review required."
        )

    # The status is the word before the first colon.
    status = final_answer.split(":", 1)[0].strip().upper()

    return {
        "status": status,
        "final_answer": final_answer,
        "steps": steps,
        "llm_calls": llm_calls,
        "tokens_used": tokens_used,
    }


# --------------------------------------------------
# RUN ALL SEVEN SCENARIOS
# --------------------------------------------------
def run_all_scenarios():
    if not SCENARIOS_FILE.exists():
        raise FileNotFoundError(
            f"Scenario file not found: {SCENARIOS_FILE}"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(
        SCENARIOS_FILE, "r", newline="", encoding="utf-8"
    ) as file:
        scenarios = list(csv.DictReader(file))

    if len(scenarios) != 7:
        raise ValueError(
            f"Expected 7 scenarios, found {len(scenarios)}."
        )

    # Append one JSONL record per scenario.
    with open(OUTPUT_FILE, "a", encoding="utf-8") as output:
        for scenario in scenarios:
            scenario_id = scenario["scenario_id"]
            user_message = scenario["message"]

            result = run_agent(
                user_message=user_message,
                scenario_id=scenario_id,
                max_iterations=6,
                token_limit=6000,
                time_limit_seconds=10,
            )

            record = {
                "scenario_id": scenario_id,
                "status": result["status"],
                "final_answer": result["final_answer"],
                "llm_calls": result["llm_calls"],
                "tokens_used": result["tokens_used"],
                "steps": result["steps"],
            }

            output.write(json_string(record) + "\n")
            output.flush()

            print(
                f"{scenario_id}: "
                f"status={result['status']}, "
                f"calls={result['llm_calls']}, "
                f"tokens={result['tokens_used']}"
            )
            print("  ", result["final_answer"])

    print(f"\nResults appended to: {OUTPUT_FILE}")


if __name__ == "__main__":
    run_all_scenarios()
