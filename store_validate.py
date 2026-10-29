
import sqlite3
from pathlib import Path

import pandas as pd

# --------------------------------------------------
# File locations
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CLEAN_DIR = BASE_DIR / "data" / "clean"
DB_PATH = BASE_DIR / "data" / "instamart.db"

CLEAN_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Ensure all three cleaned CSV files exist
required_files = [
    CLEAN_DIR / "customers.csv",
    CLEAN_DIR / "products.csv",
    CLEAN_DIR / "orders.csv",
]

for file_path in required_files:
    if not file_path.exists():
        raise FileNotFoundError(
            f"Required cleaned file not found: {file_path}\n"
            "Run the relevant cleaning script first."
        )

# --------------------------------------------------
# Load the cleaned tables
# --------------------------------------------------
customers = pd.read_csv(CLEAN_DIR / "customers.csv")
products = pd.read_csv(CLEAN_DIR / "products.csv")
orders = pd.read_csv(CLEAN_DIR / "orders.csv")

# Format order_ts as YYYY-MM-DD HH:MM:SS text
orders["order_ts"] = pd.to_datetime(
    orders["order_ts"], errors="raise"
).dt.strftime("%Y-%m-%d %H:%M:%S")

# Ensure numeric columns are numeric for validation/storage
customers["age"] = pd.to_numeric(
    customers["age"], errors="raise"
)

orders["order_amount"] = pd.to_numeric(
    orders["order_amount"], errors="raise"
)

orders["delivery_minutes"] = pd.to_numeric(
    orders["delivery_minutes"], errors="coerce"
)

# Save the clean CSV files
customers.to_csv(CLEAN_DIR / "customers.csv", index=False)
products.to_csv(CLEAN_DIR / "products.csv", index=False)
orders.to_csv(CLEAN_DIR / "orders.csv", index=False)

# --------------------------------------------------
# Store all three tables in SQLite
# --------------------------------------------------
with sqlite3.connect(DB_PATH) as connection:
    customers.to_sql(
        "customers", connection, if_exists="replace", index=False
    )
    products.to_sql(
        "products", connection, if_exists="replace", index=False
    )
    orders.to_sql(
        "orders", connection, if_exists="replace", index=False
    )

    # Check the tables were created
    table_names = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }

    assert {"customers", "products", "orders"}.issubset(table_names)

    # Confirm order_ts is stored as text in the required format
    timestamp_type = connection.execute(
        "SELECT typeof(order_ts) FROM orders LIMIT 1"
    ).fetchone()[0]

    assert timestamp_type == "text"

# --------------------------------------------------
# Validate customer reference checkpoints
# --------------------------------------------------

# 1. Exactly 1,200 customers
assert len(customers) == 1200, "Customer row count mismatch"

# 2. Exactly six standardised cities with expected counts
expected_cities = {
    "Pune": 227,
    "Delhi": 210,
    "Bengaluru": 197,
    "Chennai": 191,
    "Hyderabad": 191,
    "Mumbai": 184,
}
assert customers["city"].value_counts().to_dict() == expected_cities, (
    "City counts mismatch"
)

# 3. Expected gender counts
expected_genders = {
    "female": 610,
    "male": 560,
    "unknown": 30,
}
assert customers["gender"].value_counts().to_dict() == expected_genders, (
    "Gender counts mismatch"
)

# 4. No missing ages
assert customers["age"].isna().sum() == 0, "Missing customer ages found"

# 5. Every age is between 18 and 60
assert customers["age"].between(18, 60).all(), "Age range mismatch"

# 6. signup_date was converted and saved as a date-like value
assert pd.to_datetime(
    customers["signup_date"], errors="coerce"
).notna().all(), "Invalid signup_date values found"

# --------------------------------------------------
# Validate order reference checkpoints
# --------------------------------------------------

# 7. Exactly 12,309 cleaned orders
assert len(orders) == 12309, "Cleaned order row count mismatch"

# 8. Exactly one row per order_id
assert orders["order_id"].nunique() == 12309, (
    "Duplicate order_id values remain"
)

# 9. Expected final status counts
expected_statuses = {
    "completed": 11110,
    "cancelled": 1199,
}
assert orders["status"].value_counts().to_dict() == expected_statuses, (
    "Order status counts mismatch"
)

# 10. No missing order amounts
assert orders["order_amount"].isna().sum() == 0, (
    "Missing order_amount values found"
)

completed = orders["status"].eq("completed")
cancelled = orders["status"].eq("cancelled")

# 11. No missing delivery times for completed orders
assert orders.loc[completed, "delivery_minutes"].isna().sum() == 0, (
    "Completed orders have missing delivery times"
)

# 12. All cancelled orders have missing delivery times
assert orders.loc[cancelled, "delivery_minutes"].isna().sum() == 1199, (
    "Cancelled order delivery-time rule failed"
)

# 13. Completed order total matches the reference
completed_total = orders.loc[completed, "order_amount"].sum()
assert abs(completed_total - 2998668.80) < 0.01, (
    f"Completed order total mismatch: {completed_total:.2f}"
)

# 14. Every order timestamp follows the required text format
assert orders["order_ts"].str.fullmatch(
    r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
).all(), "order_ts format mismatch"

# Print only this message when every assertion succeeds
print("ALL CHECKPOINTS PASSED")