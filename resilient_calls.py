
import csv
import json
import random
import time
from pathlib import Path

import mock_llm
from mock_llm import TransientLLMError


BASE_DELAY = 0.05
MAX_RETRIES = 3

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"

REDACTED_FILE = OUTPUTS / "redacted_tickets.csv"
AUDIT_FILE = OUTPUTS / "task1_guardrail_audit.csv"
RESULT_FILE = OUTPUTS / "task4_retry_results.csv"

SYSTEM_PROMPT = """
CLASSIFY each support ticket into exactly one allowed category:
billing, delivery, technical, fraud.
Return JSON only in this format:
{"category": "...", "reason": "..."}
"""


def call_with_retry(ticket_id, messages):
    """Call the mock LLM, retrying transient errors at most 3 times."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = mock_llm.chat(messages)
            return response.choices[0].message.content

        except TransientLLMError:
            if attempt == MAX_RETRIES:
                raise

            # attempt = 0, 1, 2 gives exponents 0, 1, 2
            wait = (
                BASE_DELAY
                * (2 ** attempt)
                * random.uniform(0.9, 1.15)
            )

            print(
                f"Retry: ticket_id={ticket_id}, "
                f"retry_number={attempt + 1}, "
                f"wait={wait:.4f}s"
            )
            time.sleep(wait)


def main():
    with open(REDACTED_FILE, newline="", encoding="utf-8-sig") as f:
        tickets = list(csv.DictReader(f))

    with open(AUDIT_FILE, newline="", encoding="utf-8-sig") as f:
        audit = list(csv.DictReader(f))

    # Find the status column in the guardrail audit.
    audit_fields = audit[0].keys() if audit else []
    status_field = next(
        (
            field for field in
            ("status", "guardrail_status", "guardrail_result")
            if field in audit_fields
        ),
        None,
    )

    if not status_field:
        raise ValueError(
            "Could not find a status column in the guardrail audit. "
            "Check the column names in task1_guardrail_audit.csv."
        )

    eligible_ids = {
        row["ticket_id"]
        for row in audit
        if row[status_field] == "eligible"
    }

    eligible_tickets = [
        row for row in tickets
        if row["ticket_id"] in eligible_ids
    ]

    if len(eligible_tickets) != 156:
        raise ValueError(
            f"Expected 156 eligible tickets, found {len(eligible_tickets)}. "
            "Check the input CSVs and guardrail status values."
        )

    results = []
    transient_errors = 0
    recovered_errors = 0
    permanent_errors = 0

    # Reset immediately before this complete batch run.
    mock_llm.reset()

    for ticket in eligible_tickets:
        ticket_id = ticket["ticket_id"]

        # Send only the redacted ticket text as the user message.
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": ticket["redacted_text"]},
        ]

        errors_before = transient_errors

        # Count transient failures while preserving the retry function.
        original_chat = mock_llm.chat

        def tracked_chat(msgs):
            nonlocal transient_errors
            try:
                return original_chat(msgs)
            except TransientLLMError:
                transient_errors += 1
                raise

        mock_llm.chat = tracked_chat

        try:
            response_text = call_with_retry(ticket_id, messages)
            ticket_errors = transient_errors - errors_before
            recovered_errors += ticket_errors

            results.append({
                "ticket_id": ticket_id,
                "true_category": ticket.get("true_category", ""),
                "response": response_text,
                "transient_errors": ticket_errors,
                "status": "success",
            })

        except TransientLLMError as exc:
            permanent_errors += 1
            results.append({
                "ticket_id": ticket_id,
                "true_category": ticket.get("true_category", ""),
                "response": "",
                "transient_errors": transient_errors - errors_before,
                "status": f"permanent_error: {exc}",
            })

        finally:
            mock_llm.chat = original_chat

    OUTPUTS.mkdir(parents=True, exist_ok=True)

    with open(RESULT_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ticket_id",
                "true_category",
                "response",
                "transient_errors",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    successful = sum(r["status"] == "success" for r in results)

    print("\n--- Task 4 Retry Summary ---")
    print(f"Eligible tickets: {len(eligible_tickets)}")
    print(f"Successful tickets: {successful}")
    print(f"Transient errors: {transient_errors}")
    print(f"Recovered errors: {recovered_errors}")
    print(f"Permanent errors: {permanent_errors}")
    print(f"Results saved to: {RESULT_FILE}")

    assert len(eligible_tickets) == 156
    assert successful == 156
    assert transient_errors == 19, (
        f"Expected 19 transient errors, got {transient_errors}"
    )
    assert recovered_errors == 19
    assert permanent_errors == 0

    print("ALL TASK 4 CHECKS PASSED")


if __name__ == "__main__":
    main()