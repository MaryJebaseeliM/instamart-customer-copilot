
from pathlib import Path

import pandas as pd
from mock_llm import est_tokens

ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "data" / "raw" / "tickets.csv"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_INPUT_TOKENS = 400

tickets = pd.read_csv(INPUT_FILE, dtype=str, keep_default_na=False)

results = []

for _, ticket in tickets.iterrows():
    ticket_id = ticket["ticket_id"]
    text = ticket["text"]

    # Guardrail 1: empty or whitespace-only text
    if not text.strip():
        status = "skipped_empty"
        token_estimate = 0

    # Guardrail 2: reject text above the input-token limit
    else:
        token_estimate = est_tokens(text)

        if token_estimate > MAX_INPUT_TOKENS:
            status = "flagged_long"
        else:
            # Task 1 only: do not call the model yet.
            status = "eligible"

    results.append({
        "ticket_id": ticket_id,
        "status": status,
        "est_tokens": token_estimate,
    })

audit = pd.DataFrame(results)
audit.to_csv(OUTPUT_DIR / "task1_guardrail_audit.csv", index=False)

print("Tickets processed:", len(audit))
print("\nStatus counts:")
print(audit["status"].value_counts().to_string())
print("\nMaximum token estimate among flagged-long tickets:")
long_rows = audit[audit["status"] == "flagged_long"]
print(long_rows["est_tokens"].max() if not long_rows.empty else "None")
print("\nSaved:", OUTPUT_DIR / "task1_guardrail_audit.csv")

assert len(audit) == 164, "Expected 164 tickets."
assert (audit["status"] == "skipped_empty").sum() == 4
assert (audit["status"] == "flagged_long").sum() == 4
assert (audit.loc[audit["status"] == "flagged_long", "est_tokens"] == 734).all()

print("\nTask 1 guardrail checks passed.")