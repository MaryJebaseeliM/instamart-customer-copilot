
import csv
import json
import random
import re
import time
from pathlib import Path

import mock_llm
from mock_llm import TransientLLMError
from two_prompts import ZERO_SHOT_PROMPT, FEW_SHOT_PROMPT


# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"

RAW_FILE = ROOT / "data" / "raw" / "tickets.csv"
REDACTED_FILE = OUTPUT_DIR / "redacted_tickets.csv"
AUDIT_FILE = OUTPUT_DIR / "task1_guardrail_audit.csv"
SEGMENTS_FILE = OUTPUT_DIR / "customer_segments.csv"

BUDGET_DEMO = 6000
FINAL_BUDGET = 100000

MAX_RETRIES = 3
BASE_DELAY = 0.05

CATEGORIES = {"billing", "delivery", "technical", "fraud"}

REVIEW_STATUSES = {
    "skipped_empty",
    "flagged_long",
    "flagged_invalid_output",
    "budget_exhausted",
}

OUTPUT_COLUMNS = [
    "ticket_id",
    "customer_id",
    "status",
    "category",
    "segment_name",
    "priority",
    "route",
    "tokens_used",
]


# --------------------------------------------------
# File helpers
# --------------------------------------------------

def read_csv(path):
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def normalize_guardrail_status(value):
    value = (value or "").strip().lower()

    if "empty" in value:
        return "skipped_empty"
    if "long" in value:
        return "flagged_long"
    if "invalid" in value:
        return "flagged_invalid_output"
    if value == "eligible":
        return "eligible"

    return value


def is_true(value):
    return str(value or "").strip().lower() in {
        "true", "1", "yes", "y"
    }


# --------------------------------------------------
# Model response helpers
# --------------------------------------------------

def response_text(response):
    if isinstance(response, str):
        return response

    if isinstance(response, dict):
        if "choices" in response:
            return response["choices"][0]["message"]["content"]

        if "content" in response:
            return str(response["content"])

        return json.dumps(response)

    if hasattr(response, "choices"):
        return response.choices[0].message.content

    raise TypeError(
        f"Unsupported response type: {type(response).__name__}"
    )


def response_tokens(response):
    """Read actual usage.total_tokens; do not estimate."""
    usage = None

    if isinstance(response, dict):
        usage = response.get("usage")
    elif hasattr(response, "usage"):
        usage = response.usage

    if isinstance(usage, dict):
        tokens = usage.get("total_tokens")
    elif usage is not None:
        tokens = getattr(usage, "total_tokens", None)
    else:
        tokens = None

    if tokens is None:
        raise ValueError(
            "Model response did not provide usage.total_tokens."
        )

    return int(tokens)


def validate_response(text):
    """Use Task 5's JSON validation and keyword fallback."""
    try:
        data = json.loads(text)

        if not isinstance(data, dict):
            return "", "flagged_invalid_output"

        category = str(data.get("category", "")).strip().lower()

        if category in CATEGORIES:
            return category, "classified_json"

        return "", "flagged_invalid_output"

    except (json.JSONDecodeError, TypeError, AttributeError):
        words = re.findall(r"[a-z]+", text.lower())
        found = {word for word in words if word in CATEGORIES}

        if len(found) == 1:
            return found.pop(), "classified_keyword"

        return "", "flagged_invalid_output"


# --------------------------------------------------
# Budget-aware model call
# --------------------------------------------------

def call_with_budget(messages, token_budget, running_total):
    """
    Check the cumulative budget before every model call,
    including retries.

    Returns:
        response, tokens_used_for_ticket, status
    """
    ticket_tokens = 0

    for attempt in range(MAX_RETRIES + 1):

        # Mandatory budget check before EVERY model call.
        if running_total[0] >= token_budget:
            return None, ticket_tokens, "budget_exhausted"

        try:
            response = mock_llm.chat(messages)

            tokens = response_tokens(response)

            # Count actual usage for this successful response.
            running_total[0] += tokens
            ticket_tokens += tokens

            return response, ticket_tokens, "success"

        except TransientLLMError:
            if attempt == MAX_RETRIES:
                return None, ticket_tokens, "call_failed"

            wait = (
                BASE_DELAY
                * (2 ** attempt)
                * random.uniform(0.9, 1.15)
            )
            time.sleep(wait)

    return None, ticket_tokens, "call_failed"


# --------------------------------------------------
# Routing rules
# --------------------------------------------------

def apply_routing(status, category, is_premium):
    if status in REVIEW_STATUSES or status == "call_failed":
        return "NORMAL", "human_review"

    if category == "fraud":
        return "HIGH", "security_team"

    if is_premium:
        return "HIGH", "premium_desk"

    return "NORMAL", "support_queue"


# --------------------------------------------------
# Run one complete pipeline
# --------------------------------------------------

def run_pipeline(prompt_name, system_prompt, token_budget, output_name):
    original_tickets = read_csv(RAW_FILE)
    redacted_tickets = read_csv(REDACTED_FILE)
    audit_rows = read_csv(AUDIT_FILE)
    segment_rows = read_csv(SEGMENTS_FILE)

    # Map ticket ID to redacted text.
    redacted_by_id = {
        row["ticket_id"]: row.get("redacted_text", "")
        for row in redacted_tickets
    }

    # Find the guardrail status column.
    status_column = next(
        (
            col for col in
            ("status", "guardrail_status", "guardrail_result")
            if audit_rows and col in audit_rows[0]
        ),
        None,
    )

    if status_column is None:
        raise ValueError(
            "Could not find a status column in the guardrail audit."
        )

    audit_by_id = {
        row["ticket_id"]: normalize_guardrail_status(
            row.get(status_column, "")
        )
        for row in audit_rows
    }

    # Map customer IDs to segment details.
    segments_by_customer = {
        row["customer_id"].strip(): row
        for row in segment_rows
        if row.get("customer_id", "").strip()
    }

    # Reset the deterministic mock once per complete experiment.
    mock_llm.reset()

    # running_total[0] is the cumulative actual token count.
    running_total = [0]
    results = []

    for ticket in original_tickets:
        ticket_id = ticket["ticket_id"]
        customer_id = ticket.get("customer_id", "").strip()

        guardrail_status = audit_by_id.get(
            ticket_id, "flagged_invalid_output"
        )

        category = ""
        tokens_used = 0

        # Look up customer segment, if available.
        segment = segments_by_customer.get(customer_id, {})
        segment_name = segment.get("segment_name", "").strip()
        premium = is_true(segment.get("is_premium", ""))

        # Do not call the model for tickets rejected by guardrails.
        if guardrail_status != "eligible":
            status = guardrail_status

        elif ticket_id not in redacted_by_id:
            status = "flagged_invalid_output"

        else:
            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": redacted_by_id[ticket_id],
                },
            ]

            response, tokens_used, call_status = call_with_budget(
                messages,
                token_budget,
                running_total,
            )

            if call_status == "budget_exhausted":
                status = "budget_exhausted"

            elif call_status == "call_failed":
                status = "call_failed"

            else:
                category, status = validate_response(
                    response_text(response)
                )

        priority, route = apply_routing(
            status, category, premium
        )

        # Leave unavailable category/segment values blank.
        results.append({
            "ticket_id": ticket_id,
            "customer_id": customer_id,
            "status": status,
            "category": category,
            "segment_name": segment_name,
            "priority": priority,
            "route": route,
            "tokens_used": tokens_used,
        })

    output_path = OUTPUT_DIR / output_name
    write_csv(output_path, results)

    exhausted = sum(
        row["status"] == "budget_exhausted"
        for row in results
    )
    human_review = sum(
        row["route"] == "human_review"
        for row in results
    )
    classified = sum(
        row["status"] in {
            "classified_json", "classified_keyword"
        }
        for row in results
    )

    print(f"\n--- {prompt_name.upper()} PIPELINE ---")
    print(f"Eligible input tickets: {len(original_tickets)}")
    print(f"Tickets classified: {classified}")
    print(f"Total actual tokens used: {running_total[0]}")
    print(f"Token budget: {token_budget}")
    print(f"Budget-exhausted tickets: {exhausted}")
    print(f"Human-review tickets: {human_review}")
    print(f"Saved: {output_path}")

    return results, running_total[0], exhausted


# --------------------------------------------------
# Task 7
# --------------------------------------------------

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Part A: zero-shot budget demonstration.
    _, demo_tokens, demo_exhausted = run_pipeline(
        prompt_name="zero-shot budget demo",
        system_prompt=ZERO_SHOT_PROMPT,
        token_budget=BUDGET_DEMO,
        output_name="triage_budget_demo.csv",
    )

    # Part B: few-shot final triage output.
    _, final_tokens, final_exhausted = run_pipeline(
        prompt_name="few-shot final triage",
        system_prompt=FEW_SHOT_PROMPT,
        token_budget=FINAL_BUDGET,
        output_name="triage_results.csv",
    )

    print("\n--- TASK 7 SUMMARY ---")
    print(f"Budget demo tokens used: {demo_tokens}")
    print(f"Budget demo exhausted tickets: {demo_exhausted}")
    print(f"Final run tokens used: {final_tokens}")
    print(f"Final run exhausted tickets: {final_exhausted}")

    if demo_exhausted == 0:
        print(
            "WARNING: No tickets were budget-exhausted. "
            "Lower BUDGET_DEMO (for example, to 5000), "
            "then rerun the script."
        )


if __name__ == "__main__":
    main()