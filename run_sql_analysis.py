from pathlib import Path
import re
import sqlite3
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "instamart.db"
SQL_PATH = ROOT / "sql" / "queries.sql"
OUTPUT_DIR = ROOT / "outputs" / "sql"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def load_queries(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    chunks = re.split(r"(?m)^--\s*(Q[1-7])\s*[—-].*$", text)
    queries = {}
    for i in range(1, len(chunks), 2):
        label = chunks[i].strip()
        query = chunks[i + 1].strip()
        if query:
            queries[label] = query
    if set(queries) != {f"Q{i}" for i in range(1, 8)}:
        raise ValueError(f"Expected Q1–Q7; found: {sorted(queries)}")
    return queries

def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}\n"
            "Run the data-cleaning/storage scripts from the project root first."
        )

    queries = load_queries(SQL_PATH)
    with sqlite3.connect(DB_PATH) as conn:
        # Print table names to help diagnose a wrong database/schema.
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
            conn
        )["name"].tolist()
        print("Database tables:", ", ".join(tables))

        results = {}
        for label in [f"Q{i}" for i in range(1, 8)]:
            df = pd.read_sql_query(queries[label], conn)
            results[label] = df
            df.to_csv(OUTPUT_DIR / f"{label.lower()}_results.csv", index=False)
            print(f"\n{label}: {len(df)} rows")
            print(df.head(10).to_string(index=False))

    # Reference checks. These are diagnostics: a failed check raises an error
    # so schema/data problems are not silently reported as a successful run.
    checks = {
        "Q1 row count": len(results["Q1"]) == 30,
        "Q2 row count": len(results["Q2"]) == 30,
        "Q3 row count": len(results["Q3"]) == 11,
        "Q4 row count": len(results["Q4"]) == 25,
        "Q5 row count": len(results["Q5"]) == 550,
        "Q6 top customer per city": True,
        "Q6 rank vs row-number ties": True,
        "Q7 daily row count": len(results["Q7"]) == 183,
    }

    q2 = results["Q2"]
    if {"city", "category", "revenue"}.issubset(q2.columns):
        checks["Q2 revenue total"] = abs(q2["revenue"].sum() - 2998668.80) < 0.02
        row = q2[(q2["city"] == "Bengaluru") & (q2["category"] == "Electronics")]
        checks["Q2 Bengaluru Electronics"] = (
            len(row) == 1 and abs(float(row.iloc[0]["revenue"]) - 233909.45) < 0.02
        )

    q5 = results["Q5"]
    if "average_spend" in q5.columns and not q5.empty:
        checks["Q5 average spend"] = abs(float(q5["average_spend"].iloc[0]) - 2552.06) < 0.02

    q6 = results["Q6"]
    if {"city", "customer_id", "total_spend", "spend_rank", "spend_row_number"}.issubset(q6.columns):
        expected_top = {
            "Bengaluru": ("C0082", 12856.20),
            "Chennai": ("C0930", 10151.40),
            "Delhi": ("C0291", 13742.60),
            "Hyderabad": ("C0743", 12730.05),
            "Mumbai": ("C0693", 14766.55),
            "Pune": ("C0426", 10377.10),
        }
        actual_top = {}
        for city, group in q6.groupby("city"):
            first = group.sort_values(["spend_rank", "customer_id"]).iloc[0]
            actual_top[city] = (first["customer_id"], float(first["total_spend"]))
        checks["Q6 top customer per city"] = all(
            city in actual_top
            and actual_top[city][0] == customer
            and abs(actual_top[city][1] - spend) < 0.02
            for city, (customer, spend) in expected_top.items()
        )
        checks["Q6 rank vs row-number ties"] = int(
            (q6["spend_rank"] != q6["spend_row_number"]).sum()
        ) == 8

    q7 = results["Q7"]
    if {"cumulative_revenue"}.issubset(q7.columns) and not q7.empty:
        checks["Q7 final cumulative revenue"] = (
            abs(float(q7.iloc[-1]["cumulative_revenue"]) - 2998668.80) < 0.02
        )

    print("\nREFERENCE CHECKS")
    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} — {name}")
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError("Reference checks failed: " + ", ".join(failed))

    print(f"\nSaved seven result CSVs to: {OUTPUT_DIR}")
    print("ALL SQL REFERENCE CHECKS PASSED")

if __name__ == "__main__":
    main()
