
import csv
import json
import re
import time
import random
from pathlib import Path
from collections import Counter

from mock_llm import chat, reset, est_tokens, TransientLLMError
from two_prompts import ZERO_SHOT_PROMPT, FEW_SHOT_PROMPT

ROOT = Path(__file__).resolve().parent
RAW_FILE = ROOT / "data" / "raw" / "tickets.csv"
REDACTED_FILE = ROOT / "outputs" / "redacted_tickets.csv"
AUDIT_FILE = ROOT / "outputs" / "task1_guardrail_audit.csv"
OUTPUT_DIR = ROOT / "outputs"

CATEGORIES = ["billing", "delivery", "technical", "fraud"]
MAX_RETRIES = 3
BASE_DELAY = 0.05


def read_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_response_text(response):
    """Support either a plain string or an OpenAI-style response object."""
    if isinstance(response, str):
        return response

    if isinstance(response, dict):
        if "choices" in response:
            return response["choices"][0]["message"]["content"]
        return json.dumps(response)

    if hasattr(response, "choices"):
        return response.choices[0].message.content

    return str(response)


def get_usage_tokens(response, messages, response_text):
    """Use actual usage when supplied; otherwise estimate for a string mock."""
    usage = None

    if isinstance(response, dict):
        usage = response.get("usage")
    elif hasattr(response, "usage"):
        usage = response.usage

    if isinstance(usage, dict) and usage.get("total_tokens") is not None:
        return int(usage["total_tokens"]), "actual_usage"

    if usage is not None and getattr(usage, "total_tokens", None) is not None:
        return int(usage.total_tokens), "actual_usage"

    prompt_text = " ".join(m["content"] for m in messages)
    return est_tokens(prompt_text + " " + response_text), "estimated"


def validate(text):
    """Apply Task 5's JSON validation and keyword fallback."""
    try:
        data = json.loads(text)
        category = str(data.get("category", "")).strip().lower()

        if category in CATEGORIES:
            return category, "classified_json"

        return None, "flagged_invalid_output"

    except (json.JSONDecodeError, TypeError, AttributeError):
        words = re.findall(r"[a-z]+", text.lower())
        found = [word for word in words if word in CATEGORIES]

        if len(set(found)) == 1:
            return found[0], "classified_keyword"

        return None, "flagged_invalid_output"


def call_with_retry(messages):
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = chat(messages)
            return response
        except TransientLLMError:
            if attempt == MAX_RETRIES:
                raise

            wait = BASE_DELAY * (2 ** attempt) * random.uniform(0.9, 1.15)
            time.sleep(wait)


def run_experiment(prompt_name, system_prompt, tickets, redacted_by_id):
    reset()

    rows = []
    total_tokens = 0
    token_sources = set()
    failures = 0

    for ticket in tickets:
        ticket_id = ticket["ticket_id"]
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": redacted_by_id[ticket_id],
            },
        ]

        try:
            response = call_with_retry(messages)
            response_text = get_response_text(response)
            tokens, token_source = get_usage_tokens(
                response, messages, response_text
            )
            total_tokens += tokens
            token_sources.add(token_source)

            predicted, status = validate(response_text)

        except Exception as exc:
            response_text = f"ERROR: {type(exc).__name__}"
            predicted = None
            status = "call_failed"
            failures += 1

        rows.append({
            "ticket_id": ticket_id,
            "true_category": ticket["true_category"].strip().lower(),
            "response": response_text,
            "category": predicted or "",
            "classification_status": status,
        })

    classified = [
        row for row in rows
        if row["classification_status"]
        in ("classified_json", "classified_keyword")
    ]

    correct = sum(
        row["category"] == row["true_category"]
        for row in classified
    )

    accuracy = correct / len(classified) if classified else 0
    tokens_per_ticket = (
        total_tokens / len(classified) if classified else 0
    )

    OUTPUT_DIR.mkdir(exist_ok=True)

    output_file = OUTPUT_DIR / f"task6_{prompt_name}_results.csv"
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ticket_id", "true_category", "response",
            "category", "classification_status"
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n--- {prompt_name.upper()} RESULTS ---")
    print(f"Eligible tickets: {len(rows)}")
    print(f"Tickets classified: {len(classified)}")
    print(f"Correct predictions: {correct}")
    print(f"Accuracy: {accuracy:.1%} ({correct}/{len(classified)})")
    print(f"Invalid/failed tickets: {len(rows) - len(classified)}")
    print(f"Total tokens: {total_tokens}")
    print(f"Tokens per classified ticket: {tokens_per_ticket:.2f}")
    print(f"Token measurement: {', '.join(sorted(token_sources)) or 'no responses'}")
    print(f"Call failures: {failures}")
    print(f"Saved: {output_file}")

    return rows, {
        "name": prompt_name,
        "eligible": len(rows),
        "classified": len(classified),
        "correct": correct,
        "accuracy": accuracy,
        "total_tokens": total_tokens,
        "tokens_per_ticket": tokens_per_ticket,
        "token_sources": sorted(token_sources),
        "failures": failures,
    }


def print_confusion_matrix(rows):
    classified = [
        row for row in rows
        if row["classification_status"]
        in ("classified_json", "classified_keyword")
    ]

    print("\nZERO-SHOT CONFUSION MATRIX")
    print("Rows = true category; columns = predicted category")
    print(f"{'True / Predicted':<18}" +
          "".join(f"{c:>12}" for c in CATEGORIES))

    for true_cat in CATEGORIES:
        print(f"{true_cat:<18}", end="")
        for predicted_cat in CATEGORIES:
            count = sum(
                row["true_category"] == true_cat
                and row["category"] == predicted_cat
                for row in classified
            )
            print(f"{count:>12}", end="")
        print()


def main():
    original = read_csv(RAW_FILE)
    redacted_rows = read_csv(REDACTED_FILE)
    audit_rows = read_csv(AUDIT_FILE)

    labels = {row["ticket_id"]: row for row in original}
    redacted_by_id = {
        row["ticket_id"]: row["redacted_text"]
        for row in redacted_rows
    }

    status_column = next(
        (column for column in
         ("status", "guardrail_status", "guardrail_result")
         if audit_rows and column in audit_rows[0]),
        None
    )

    if status_column is None:
        raise ValueError(
            "Could not find the guardrail status column in the audit CSV."
        )

    eligible_ids = {
        row["ticket_id"]
        for row in audit_rows
        if row[status_column].strip().lower() == "eligible"
    }

    tickets = [
        row for row in original
        if row["ticket_id"] in eligible_ids
        and row["ticket_id"] in redacted_by_id
    ]

    if len(tickets) != 156:
        raise ValueError(
            f"Expected 156 eligible tickets, found {len(tickets)}. "
            "Check the guardrail audit and input files."
        )

    # Run both prompts on the same tickets, with no token budget.
    zero_rows, zero = run_experiment(
        "zero_shot", ZERO_SHOT_PROMPT, tickets, redacted_by_id
    )
    few_rows, few = run_experiment(
        "few_shot", FEW_SHOT_PROMPT, tickets, redacted_by_id
    )

    print_confusion_matrix(zero_rows)

    print("\n--- COMPARISON ---")
    for result in (zero, few):
        print(
            f"{result['name']}: "
            f"classified={result['classified']}, "
            f"accuracy={result['accuracy']:.1%}, "
            f"total_tokens={result['total_tokens']}, "
            f"tokens/classified={result['tokens_per_ticket']:.2f}"
        )

    if zero["token_sources"] != ["actual_usage"] or \
       few["token_sources"] != ["actual_usage"]:
        print(
            "\nWARNING: mock_llm did not provide actual "
            "response.usage.total_tokens for every run. "
            "Estimated token totals must not be reported as actual usage."
        )


if __name__ == "__main__":
    main()