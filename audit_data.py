
import pandas as pd
from pathlib import Path

# Locate the raw data folder
DATA_DIR = Path("data") / "raw"

# Load the three raw tables
customers = pd.read_csv(DATA_DIR / "customers.csv")
products = pd.read_csv(DATA_DIR / "products.csv")
orders = pd.read_csv(DATA_DIR / "orders.csv")

# Preserve empty ticket text as an empty string for later tasks
tickets = pd.read_csv(
    DATA_DIR / "tickets.csv",
    keep_default_na=False
)

tables = {
    "customers": customers,
    "products": products,
    "orders": orders,
}

# --------------------------------------------------
# 1. Print shape, data types, and missing values
# --------------------------------------------------
for name, df in tables.items():
    print(f"\n{'=' * 60}")
    print(f"TABLE: {name.upper()}")
    print("=" * 60)

    print("\nShape (rows, columns):")
    print(df.shape)

    print("\nData types:")
    print(df.dtypes)

    # Count missing values in every column
    missing_count = df.isna().sum()

    # Calculate missing percentage for every column
    missing_percentage = (missing_count / len(df) * 100).round(2)

    missing_report = pd.DataFrame({
        "missing_count": missing_count,
        "missing_percentage": missing_percentage
    })

    print("\nMissing values by column:")
    print(missing_report.to_string())


# --------------------------------------------------
# 2. Audit raw orders
# --------------------------------------------------

# Convert amounts for checking, without changing the raw data
amount_numeric = pd.to_numeric(
    orders["order_amount"], errors="coerce"
)

# Count non-empty values that cannot be converted
amount_text = orders["order_amount"].astype("string").str.strip()
invalid_amounts = (
    amount_text.notna()
    & amount_text.ne("")
    & amount_numeric.isna()
).sum()

# Convert delivery times to numeric for validation
delivery_numeric = pd.to_numeric(
    orders["delivery_minutes"], errors="coerce"
)

delivery_text = orders["delivery_minutes"].astype("string").str.strip()

negative_delivery = (delivery_numeric < 0).sum()

blank_delivery = (
    orders["delivery_minutes"].isna()
    | delivery_text.eq("").fillna(False)
).sum()

# --------------------------------------------------
# 3. Audit raw customers
# --------------------------------------------------

age_numeric = pd.to_numeric(customers["age"], errors="coerce")
age_text = customers["age"].astype("string").str.strip()

blank_age = (
    customers["age"].isna()
    | age_text.eq("").fillna(False)
).sum()

age_outside_range = (
    age_numeric.notna()
    & ~age_numeric.between(10, 100)
).sum()

city_text = customers["city"].astype("string").str.strip()
distinct_cities = city_text[
    city_text.notna() & city_text.ne("")
].nunique()

gender_text = customers["gender"].astype("string").str.strip()
nonblank_gender = gender_text[
    gender_text.notna() & gender_text.ne("")
]

distinct_genders = nonblank_gender.nunique()

blank_gender = (
    customers["gender"].isna()
    | gender_text.eq("").fillna(False)
).sum()

# --------------------------------------------------
# 4. Create the required audit figures
# --------------------------------------------------

audit_results = pd.DataFrame([
    {
        "Audit check": "Raw orders rows",
        "Actual": len(orders),
        "Reference": 13084
    },
    {
        "Audit check": "Exact duplicate order rows",
        "Actual": orders.duplicated().sum(),
        "Reference": 119
    },
    {
        "Audit check": "Pending order rows",
        "Actual": orders["status"].astype("string").str.strip()
        .str.lower().eq("pending").sum(),
        "Reference": 656
    },
    {
        "Audit check": "Distinct order_id values",
        "Actual": orders["order_id"].nunique(),
        "Reference": 12309
    },
    {
        "Audit check": "Non-numeric order_amount entries",
        "Actual": invalid_amounts,
        "Reference": 120
    },
    {
        "Audit check": "Negative delivery_minutes",
        "Actual": negative_delivery,
        "Reference": 106
    },
    {
        "Audit check": "Blank delivery_minutes",
        "Actual": blank_delivery,
        "Reference": 2541
    },
    {
        "Audit check": "Blank customer ages",
        "Actual": blank_age,
        "Reference": 61
    },
    {
        "Audit check": "Ages outside 10–100",
        "Actual": age_outside_range,
        "Reference": 6
    },
    {
        "Audit check": "Distinct raw city spellings",
        "Actual": distinct_cities,
        "Reference": 24
    },
    {
        "Audit check": "Distinct non-blank gender spellings",
        "Actual": distinct_genders,
        "Reference": 10
    },
    {
        "Audit check": "Blank gender values",
        "Actual": blank_gender,
        "Reference": 30
    }
])

print("\n" + "=" * 70)
print("REQUIRED AUDIT FIGURES")
print("=" * 70)
print(audit_results.to_string(index=False))

# Save the audit figures for your project evidence
Path("outputs").mkdir(exist_ok=True)
audit_results.to_csv("outputs/raw_audit_results.csv", index=False)

print("\nAudit figures saved to outputs/raw_audit_results.csv")
