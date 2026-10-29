
from pathlib import Path
import csv

ROOT = Path(__file__).resolve().parent
POLICY_DIR = ROOT / "data" / "policies"
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_FILE = OUTPUT_DIR / "policy_chunks.csv"

CHUNK_SIZE = 40
OVERLAP = 10
STEP = CHUNK_SIZE - OVERLAP


def main():
    policy_files = sorted(POLICY_DIR.glob("*.txt"))

    if len(policy_files) != 5:
        raise ValueError(
            f"Expected 5 policy files, found {len(policy_files)}"
        )

    rows = []

    for file in policy_files:
        words = file.read_text(encoding="utf-8").split()
        start = 0
        chunk_number = 1

        while start < len(words):
            end = min(start + CHUNK_SIZE, len(words))

            rows.append({
                "chunk_id": f"{file.stem}_{chunk_number:02d}",
                "source_file": file.name,
                "start_word": start,
                "end_word_exclusive": end,
                "word_count": end - start,
                "chunk_text": " ".join(words[start:end]),
            })

            # Stop when this chunk reaches the document's end.
            if end >= len(words):
                break

            start += STEP
            chunk_number += 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "chunk_id",
                "source_file",
                "start_word",
                "end_word_exclusive",
                "word_count",
                "chunk_text",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print("Chunks by policy:")
    for file in policy_files:
        count = sum(
            row["source_file"] == file.name for row in rows
        )
        print(f"{file.name}: {count}")

    print(f"\nTotal chunks: {len(rows)}")
    print(f"Saved to: {OUTPUT_FILE}")

    assert len(rows) == 15, (
        f"Expected 15 chunks, but got {len(rows)}. "
        "Check the policy file contents."
    )


if __name__ == "__main__":
    main()
