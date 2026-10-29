
import csv
import json
import random
import re
import time
from pathlib import Path
from collections import Counter

import mock_llm
from mock_llm import TransientLLMError


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DELAY = 0.05
MAX_RETRIES = 3

ALLOWED_CATEGORIES = {
    "billing",
    "delivery",
    "technical",
    "fraud",
}

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"

REDACTED_FILE = OUTPUTS / "redacted_tickets.csv"
AUDIT_FILE = OUTPUTS / "task1_guardrail_audit.csv"
ORIGINAL_TICKETS_FILE = ROOT / "data" / "raw" / "tickets.csv"
RESULT_FILE = OUTPUTS / "task4_retry_results.csv"

SYSTEM_PROMPT = """
CLASSIFY each support ticket into exactly one allowed category:
billing, delivery, technical, fraud.
Return JSON only in this format:
{"category": "...", "reason": "..."}
"""


# --------------------------------------------------
# Task 4: Retry transient model errors
# --------------------------------------------------

def call_with_retry(ticket_id, messages):
    """Retry transient model errors up to 3 times after the first attempt."""

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = mock_llm.chat(messages)
            return response.choices[0].message.content

        except TransientLLMError:
            if attempt == MAX_RETRIES:
                raise

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


# --------------------------------------------------
# Task 5: Validate model responses
# --------------------------------------------------

def validate_response(text):
    """
    Validate JSON responses first.
    Use keyword fallback only for non-JSON responses.
    Invalid answers are routed to human review.
    """

    try:
        data = json.loads(text)

    except (json.JSONDecodeError, TypeError):
        # Fallback applies only when the response is not valid JSON.
        words = re.findall(r"[a-z]+", text.lower())

        matches = [
            word for word in words
            if word in ALLOWED_CATEGORIES
        ]

        if len(matches) == 1:
            return {
                "category": matches[0],
                "reason": "Extracted from a non-JSON response.",
                "classification_status": "classified_keyword",
                "route": "support_queue",
            }

        return {
            "category": "",
            "reason": "Invalid or ambiguous non-JSON response.",
            "classification_status": "flagged_invalid_output",
            "route": "human_review",
        }

    # Valid JSON is accepted only if its category is allowed.
    if (
        isinstance(data, dict)
        and data.get("category") in ALLOWED_CATEGORIES
    ):
        return {
            "category": data["category"],
            "reason": data.get("reason", ""),
            "classification_status": "classified_json",
            "route": "support_queue",
        }

    return {
        "category": "",
        "reason": "JSON category is missing or not allowed.",
        "classification_status": "flagged_invalid_output",
        "route": "human_review",
    }


# --------------------------------------------------
# Main batch process
# --------------------------------------------------

def main():
    OUTPUTS.mkdir(parents=True, exist_ok=True)

    # Check that all required input files exist.
    for file_path in (
        REDACTED_FILE,
        AUDIT_FILE,
        ORIGINAL_TICKETS_FILE,
    ):
        if not file_path.exists():
            raise FileNotFoundError(
                f"Required input file not found: {file_path}"
            )

    # Load original ticket labels.
    # The original CSV contains ticket_id and true_category.
    with open(
        ORIGINAL_TICKETS_FILE,
        newline="",
        encoding="utf-8-sig",
    ) as f:
        original_tickets = list(csv.DictReader(f))

    required_original_columns = {"ticket_id", "true_category"}

    if not original_tickets:
        raise ValueError(
            f"No tickets found in {ORIGINAL_TICKETS_FILE}"
        )

    if not required_original_columns.issubset(
        original_tickets[0].keys()
    ):
        raise ValueError(
            "Original tickets.csv must contain "
            "'ticket_id' and 'true_category' columns."
        )

    original_category_by_id = {
        row["ticket_id"]: row["true_category"]
        for row in original_tickets
    }

    print(
        f"Loaded original labels for "
        f"{len(original_category_by_id)} tickets."
    )

    # Load redacted tickets.
    with open(
        REDACTED_FILE,
        newline="",
        encoding="utf-8-sig",
    ) as f:
        tickets = list(csv.DictReader(f))

    # Load guardrail audit.
    with open(
        AUDIT_FILE,
        newline="",
        encoding="utf-8-sig",
    ) as f:
        audit = list(csv.DictReader(f))

    # Identify the guardrail status column.
    audit_fields = audit[0].keys() if audit else []

    status_field = next(
        (
            field
            for field in (
                "status",
                "guardrail_status",
                "guardrail_result",
            )
            if field in audit_fields
        ),
        None,
    )

    if not status_field:
        raise ValueError(
            "Could not find a status column "
            "in the guardrail audit CSV."
        )

    # Select only tickets marked eligible.
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
            f"Expected 156 eligible tickets, "
            f"found {len(eligible_tickets)}."
        )

    # Check that every eligible ticket has an original label.
    missing_labels = [
        row["ticket_id"]
        for row in eligible_tickets
        if not original_category_by_id.get(row["ticket_id"])
    ]

    if missing_labels:
        raise ValueError(
            "Missing original categories for ticket IDs: "
            + ", ".join(missing_labels)
        )

    results = []

    transient_errors = 0
    recovered_errors = 0
    permanent_errors = 0

    # Reset once immediately before the complete batch run.
    mock_llm.reset()

    for ticket in eligible_tickets:
        ticket_id = ticket["ticket_id"]

        # Get the original category using ticket_id.
        true_category = original_category_by_id[ticket_id]

        # Send only redacted ticket text to the model.
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": ticket["redacted_text"],
            },
        ]

        errors_before = transient_errors
        original_chat = mock_llm.chat

        def tracked_chat(msgs):
            nonlocal transient_errors

            try:
                return original_chat(msgs)

            except TransientLLMError:
                transient_errors += 1
                raise

        # Count transient errors without changing mock_llm.py.
        mock_llm.chat = tracked_chat

        try:
            # Task 4: call with retry handling.
            response_text = call_with_retry(ticket_id, messages)

            ticket_errors = transient_errors - errors_before
            recovered_errors += ticket_errors

            # Task 5: validate every successful response.
            validated = validate_response(response_text)

            results.append({
                "ticket_id": ticket_id,
                "true_category": true_category,
                "response": response_text,
                "category": validated["category"],
                "reason": validated["reason"],
                "classification_status": (
                    validated["classification_status"]
                ),
                "route": validated["route"],
                "transient_errors": ticket_errors,
                "status": "success",
            })

        except TransientLLMError as exc:
            # The request failed even after all retries.
            permanent_errors += 1

            results.append({
                "ticket_id": ticket_id,
                "true_category": true_category,
                "response": "",
                "category": "",
                "reason": str(exc),
                "classification_status": "flagged_invalid_output",
                "route": "human_review",
                "transient_errors": transient_errors - errors_before,
                "status": f"permanent_error: {exc}",
            })

        finally:
            # Restore the original mock function after each ticket.
            mock_llm.chat = original_chat

    # --------------------------------------------------
    # Save combined Task 4 and Task 5 results
    # --------------------------------------------------

    fieldnames = [
        "ticket_id",
        "true_category",
        "response",
        "category",
        "reason",
        "classification_status",
        "route",
        "transient_errors",
        "status",
    ]

    with open(
        RESULT_FILE,
        "w",
        newline="",
        encoding="utf-8",
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    successful = sum(
        row["status"] == "success"
        for row in results
    )

    classification_counts = Counter(
        row["classification_status"]
        for row in results
        if row["status"] == "success"
    )

    # --------------------------------------------------
    # Print Task 4 summary
    # --------------------------------------------------

    print("\n--- Task 4 Retry Summary ---")
    print(f"Eligible tickets: {len(eligible_tickets)}")
    print(f"Successful tickets: {successful}")
    print(f"Transient errors: {transient_errors}")
    print(f"Recovered errors: {recovered_errors}")
    print(f"Permanent errors: {permanent_errors}")

    # --------------------------------------------------
    # Print Task 5 summary
    # --------------------------------------------------

    print("\n--- Task 5 Validation Summary ---")

    for label in (
        "classified_json",
        "classified_keyword",
        "flagged_invalid_output",
    ):
        print(f"{label}: {classification_counts[label]}")

    print(f"\nResults saved to: {RESULT_FILE}")

    # --------------------------------------------------
    # Task 4 assertions
    # --------------------------------------------------

    assert len(eligible_tickets) == 156
    assert successful == 156
    assert transient_errors == 19
    assert recovered_errors == 19
    assert permanent_errors == 0

    # --------------------------------------------------
    # Task 5 assertions
    # --------------------------------------------------

    assert classification_counts["classified_json"] == 135
    assert classification_counts["classified_keyword"] == 12
    assert classification_counts["flagged_invalid_output"] == 9

    assert sum(classification_counts.values()) == 156

    # Check that the original labels were saved.
    assert all(
        row["true_category"] in ALLOWED_CATEGORIES
        for row in results
    )

    print("\nOriginal category labels matched successfully.")
    print("ALL TASK 4 AND TASK 5 CHECKS PASSED")


if __name__ == "__main__":
    main()