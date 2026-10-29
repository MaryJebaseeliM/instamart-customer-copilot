
from pathlib import Path
import re
import pandas as pd

ROOT = Path(__file__).resolve().parent
INPUT_FILE = ROOT / "data" / "raw" / "tickets.csv"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Apply patterns in the exact order specified.
PATTERNS = [
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
    ("phone", re.compile(r"\b[6-9]\d{9}\b"), "[PHONE]"),
    ("order_id", re.compile(r"ORD-\d{6}"), "[ORDER_ID]"),
]

tickets = pd.read_csv(
    INPUT_FILE,
    dtype=str,
    keep_default_na=False
)

redacted_rows = []
totals = {"email": 0, "phone": 0, "order_id": 0}

for _, ticket in tickets.iterrows():
    text = ticket["text"]
    redacted_text = text
    row_counts = {}

    # Sequential redaction in the required order.
    for name, pattern, placeholder in PATTERNS:
        redacted_text, count = pattern.subn(placeholder, redacted_text)
        row_counts[name] = count
        totals[name] += count

    redacted_rows.append({
        "ticket_id": ticket["ticket_id"],
        "redacted_text": redacted_text,
        "email_substitutions": row_counts["email"],
        "phone_substitutions": row_counts["phone"],
        "order_id_substitutions": row_counts["order_id"],
    })

redacted_df = pd.DataFrame(redacted_rows)

# Verify that all three patterns find zero matches after redaction.
remaining = {"email": 0, "phone": 0, "order_id": 0}

for text in redacted_df["redacted_text"]:
    for name, pattern, _ in PATTERNS:
        remaining[name] += len(pattern.findall(text))

total_substitutions = sum(totals.values())

print("Tickets processed:", len(redacted_df))
print("\nSubstitution counts:")
for name in ["email", "phone", "order_id"]:
    print(f"{name}: {totals[name]}")

print("Total substitutions:", total_substitutions)
print("\nRemaining matches after redaction:")
for name, count in remaining.items():
    print(f"{name}: {count}")

# Save only the redacted text and safe audit counts, not original ticket text.
output_file = OUTPUT_DIR / "redacted_tickets.csv"
redacted_df.to_csv(output_file, index=False)

# Acceptance checks
assert len(redacted_df) == 164
assert totals == {"email": 55, "phone": 91, "order_id": 132}
assert total_substitutions == 278
assert remaining == {"email": 0, "phone": 0, "order_id": 0}

print("\nSaved:", output_file)
print("All Task 2 privacy checks passed.")