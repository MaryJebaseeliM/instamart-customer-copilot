
import csv
from pathlib import Path

from agent_runner_updated import run_agent

BASE_DIR = Path(__file__).resolve().parent
SCENARIOS_FILE = BASE_DIR / "data" / "raw" / "agent_scenarios.csv"

# Load scenario S1 directly from the CSV.
with open(SCENARIOS_FILE, newline="", encoding="utf-8") as file:
    scenarios = list(csv.DictReader(file))

s1 = next(
    row for row in scenarios
    if row["scenario_id"] == "S1"
)

# Demo 1: Stop when the token limit is exceeded.
token_result = run_agent(
    user_message=s1["message"],
    scenario_id="S1",
    max_iterations=6,
    token_limit=200,
    time_limit_seconds=10,
)

print("=== TOKEN-LIMIT DEMO ===")
print("Status:", token_result["status"])
print("LLM calls:", token_result["llm_calls"])
print("Tokens used:", token_result["tokens_used"])
print("Final answer:", token_result["final_answer"])
print("Completed steps:", len(token_result["steps"]))

assert token_result["status"] == "FALLBACK_TOKEN_LIMIT", (
    "Expected FALLBACK_TOKEN_LIMIT. Check token usage and agent_runner.py."
)

# Demo 2: A zero-second timeout stops before the first model call.
timeout_result = run_agent(
    user_message=s1["message"],
    scenario_id="S1",
    max_iterations=6,
    token_limit=6000,
    time_limit_seconds=0,
)

print("\n=== TIMEOUT DEMO ===")
print("Status:", timeout_result["status"])
print("LLM calls:", timeout_result["llm_calls"])
print("Tokens used:", timeout_result["tokens_used"])
print("Final answer:", timeout_result["final_answer"])
print("Completed steps:", len(timeout_result["steps"]))

assert timeout_result["status"] == "FALLBACK_TIMEOUT"
assert timeout_result["llm_calls"] == 0
assert timeout_result["tokens_used"] == 0
assert len(timeout_result["steps"]) == 0

print("\nBoth Task 7 demos passed.")
