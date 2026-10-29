# agent_runner.py updated for task 7
# Task 6: ReAct Agent Loop
# Task 7: Safe stopping, token limits, timeout, and human handoff

import csv
import json
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


BASE_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = BASE_DIR / "data" / "raw" / "agent_scenarios.csv"
OUTPUT_FILE = BASE_DIR / "outputs" / "agent_runs.jsonl"

SYSTEM_PROMPT = """
You are the Instamart refund support agent.

Use the available tools to verify orders and policies before deciding.
Follow the refund policy:
- Only completed orders can be refunded.
- A full refund is allowed only when delivery took more than 45 minutes.
- Refunds above INR 1000 must be escalated to a human.
- Never invent order details or claim a tool succeeded when it did not.
- If a request cannot be safely completed, explain why.
- Provide a concise final answer with a status such as REFUND, ESCALATE,
  DENIED, or NOT_FOUND.
"""


TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": "Retrieve an order by its order ID.",
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string"}},
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "Search refund policy documents.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_refund",
            "description": "Calculate refund eligibility and amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_amount": {"type": "number"},
                    "delivery_minutes": {"type": "number"},
                },
                "required": ["order_amount", "delivery_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "issue_refund",
            "description": "Issue an eligible simulated refund.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "refund_inr": {"type": "number"},
                },
                "required": ["order_id", "refund_inr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_to_human",
            "description": "Escalate a refund request to a human reviewer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "refund_inr": {"type": "number"},
                },
                "required": ["order_id", "refund_inr"],
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


def call_tool(tool_name, arguments):
    """Execute an approved tool and return its result."""

    if tool_name not in TOOL_FUNCTIONS:
        return {
            "success": False,
            "error": f"Unknown or disallowed tool: {tool_name}",
        }

    try:
        if isinstance(arguments, str):
            arguments = json.loads(arguments)

        if not isinstance(arguments, dict):
            return {
                "success": False,
                "error": "Tool arguments must be a JSON object.",
            }

        result = TOOL_FUNCTIONS[tool_name](**arguments)

        if isinstance(result, dict):
            return result

        if hasattr(result, "model_dump"):
            return result.model_dump()

        if hasattr(result, "__dict__"):
            return vars(result)

        return {"result": result}

    except Exception as exc:
        return {"success": False, "error": str(exc)}


def get_tool_call_details(tool_call):
    """Read a tool call from the model response."""

    tool_id = getattr(tool_call, "id", None)
    function = getattr(tool_call, "function", None)

    if function is not None:
        tool_name = getattr(function, "name", None)
        arguments = getattr(function, "arguments", "{}")
    else:
        tool_name = getattr(tool_call, "name", None)
        arguments = getattr(tool_call, "arguments", "{}")

    if isinstance(arguments, str):
        arguments = json.loads(arguments)

    return tool_id, tool_name, arguments


def run_agent(
    user_message,
    scenario_id,
    max_iterations=6,
    token_limit=6000,
    time_limit_seconds=10,
):
    """Run the ReAct agent with safe stopping rules."""

    start_time = time.monotonic()
    tokens_used = 0
    llm_calls = 0
    steps = []

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT + "\nAGENT",
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    def fallback(status, summary):
        return {
            "status": status,
            "final_answer": summary,
            "steps": steps,
            "llm_calls": llm_calls,
            "tokens_used": tokens_used,
        }

    for iteration in range(max_iterations):

        # Task 7(c): Check elapsed time before each model call.
        elapsed = time.monotonic() - start_time

        if elapsed >= time_limit_seconds:
            return fallback(
                "FALLBACK_TIMEOUT",
                "Human review required: time limit reached.",
            )

        # Make one model call.
        response = mock_llm.chat(messages, tools=TOOLS_SPEC)
        llm_calls += 1

        # Add this call's token usage immediately.
        usage = getattr(response, "usage", None)
        call_tokens = getattr(usage, "total_tokens", 0) or 0
        tokens_used += call_tokens

        # Task 7(b): Check tokens BEFORE reading or executing tool calls.
        # IMPORTANT: The status must be FALLBACK_TOKEN_LIMIT.
        if tokens_used > token_limit:
            return fallback(
                "FALLBACK_TOKEN_LIMIT",
                "FALLBACK: token limit exceeded; human review required.",
            )

        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)

        # No tool calls means the model has provided its final answer.
        if not tool_calls:
            content = getattr(message, "content", None)
            final_answer = (
                content.strip()
                if isinstance(content, str)
                else str(content or "")
            )

            if not final_answer:
                return fallback(
                    "FALLBACK_EMPTY_RESPONSE",
                    "Human review required: the model returned an empty answer.",
                )

            status = final_answer.split(":", 1)[0].strip().upper()

            return {
                "status": status,
                "final_answer": final_answer,
                "steps": steps,
                "llm_calls": llm_calls,
                "tokens_used": tokens_used,
            }

        # Add the assistant's tool-call message to the conversation.
        assistant_tool_calls = []

        for tool_call in tool_calls:
            tool_id, tool_name, arguments = get_tool_call_details(tool_call)

            assistant_tool_calls.append(
                {
                    "id": tool_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(arguments),
                    },
                }
            )

        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": assistant_tool_calls,
            }
        )

        # Execute tools only after the token-limit check has passed.
        for tool_call in tool_calls:
            tool_id, tool_name, arguments = get_tool_call_details(tool_call)

            observation = call_tool(tool_name, arguments)

            steps.append(
                {
                    "iteration": iteration + 1,
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "observation": observation,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": tool_name,
                    "content": json.dumps(
                        observation,
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            )

    # Task 7(a): The permitted model calls finished without a final answer.
    return fallback(
        "FALLBACK_MAX_ITERATIONS",
        "Human review required: maximum iterations reached.",
    )


def load_scenarios():
    """Load the assignment scenarios from the CSV file."""

    with open(SCENARIOS_FILE, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def save_run(scenario_id, result):
    """Append a run and its completed tool steps to the JSONL log."""

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "scenario_id": scenario_id,
        "status": result["status"],
        "final_answer": result["final_answer"],
        "llm_calls": result["llm_calls"],
        "tokens_used": result["tokens_used"],
        "steps": result["steps"],
    }

    with open(OUTPUT_FILE, "a", encoding="utf-8") as file:
        file.write(
            json.dumps(record, ensure_ascii=False, default=str) + "\n"
        )


def main():
    for scenario in load_scenarios():
        scenario_id = scenario["scenario_id"]

        result = run_agent(
            user_message=scenario["message"],
            scenario_id=scenario_id,
            max_iterations=6,
            token_limit=6000,
            time_limit_seconds=10,
        )

        save_run(scenario_id, result)

        print(
            f"{scenario_id}: status={result['status']}, "
            f"calls={result['llm_calls']}, "
            f"tokens={result['tokens_used']}"
        )
        print(f"   {result['final_answer']}")

    print(f"\nResults appended to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
