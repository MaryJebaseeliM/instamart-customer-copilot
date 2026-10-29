
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data") / "raw"
CLEAN_DIR = Path("data") / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# Load raw orders and products
orders = pd.read_csv(RAW_DIR / "orders.csv")
products = pd.read_csv(RAW_DIR / "products.csv")

print("Raw order rows:", len(orders))

# --------------------------------------------------
# Rule 1: Convert order_ts to datetime
# --------------------------------------------------
orders["order_ts"] = pd.to_datetime(
    orders["order_ts"], errors="coerce"
)

# --------------------------------------------------
# Rule 2: Remove exact duplicate rows
# --------------------------------------------------
before = len(orders)
orders = orders.drop_duplicates().copy()
print("Exact duplicates removed:", before - len(orders))

# --------------------------------------------------
# Rule 3: Keep the latest record for each order_id
# --------------------------------------------------
orders = orders.sort_values(
    ["order_id", "order_ts"],
    kind="stable"
)

orders = orders.drop_duplicates(
    subset=["order_id"],
    keep="last"
).copy()

# --------------------------------------------------
# Prepare product lookup for amount calculation
# --------------------------------------------------
# Use product_id as the lookup key
product_prices = products[["product_id", "price_inr"]].drop_duplicates(
    subset=["product_id"]
)

orders = orders.merge(
    product_prices,
    on="product_id",
    how="left",
    validate="many_to_one"
)

# --------------------------------------------------
# Rule 4: Convert amount to numeric and fill missing
# --------------------------------------------------
orders["order_amount"] = pd.to_numeric(
    orders["order_amount"], errors="coerce"
)

amount_missing_before_fill = orders["order_amount"].isna().sum()

calculated_amount = (
    orders["price_inr"]
    * orders["quantity"]
    * (1 - orders["discount_pct"] / 100)
).round(2)

orders["order_amount"] = orders["order_amount"].fillna(
    calculated_amount
)

# --------------------------------------------------
# Rule 5: Clean and impute delivery time
# --------------------------------------------------
orders["delivery_minutes"] = pd.to_numeric(
    orders["delivery_minutes"], errors="coerce"
)

# Negative delivery times are invalid
orders.loc[
    orders["delivery_minutes"] < 0,
    "delivery_minutes"
] = pd.NA

# Determine the product category for each order
# The product table must have product_id and category columns
if "category" not in products.columns:
    raise ValueError(
        "The products.csv file has no 'category' column. "
        "Check its actual column names before continuing."
    )

product_categories = products[
    ["product_id", "category"]
].drop_duplicates(subset=["product_id"])

orders = orders.merge(
    product_categories,
    on="product_id",
    how="left",
    validate="many_to_one"
)

# Calculate category medians using completed orders only.
# transform aligns the median with every order row.
completed_mask = orders["status"].astype(str).str.lower().eq("completed")

category_medians = (
    orders.loc[completed_mask]
    .groupby("category")["delivery_minutes"]
    .transform("median")
)

# Build a category -> median mapping for all completed orders
category_median_map = (
    orders.loc[completed_mask]
    .groupby("category")["delivery_minutes"]
    .median()
)

completed_missing = (
    completed_mask & orders["delivery_minutes"].isna()
)

orders.loc[completed_missing, "delivery_minutes"] = (
    orders.loc[completed_missing, "category"]
    .map(category_median_map)
)

# Cancelled orders must not receive invented delivery times
cancelled_mask = orders["status"].astype(str).str.lower().eq("cancelled")
orders.loc[cancelled_mask, "delivery_minutes"] = pd.NA

# --------------------------------------------------
# Save cleaned orders
# --------------------------------------------------
# Drop lookup-only columns before saving
orders = orders.drop(columns=["price_inr", "category"])

# Use nullable integer for delivery minutes if values are whole minutes
orders["delivery_minutes"] = pd.to_numeric(
    orders["delivery_minutes"], errors="coerce"
).round().astype("Int64")

output_path = CLEAN_DIR / "orders.csv"
orders.to_csv(output_path, index=False)

# --------------------------------------------------
# Validate against assignment references
# --------------------------------------------------
print("\nCLEANED ORDERS VALIDATION")
print("-------------------------")
print("Rows:", len(orders))
print("Distinct order_id:", orders["order_id"].nunique())
print("\nStatus counts:")
print(orders["status"].value_counts(dropna=False))

print("\nMissing order_amount:", orders["order_amount"].isna().sum())
print(
    "Missing delivery_minutes among completed:",
    orders.loc[completed_mask, "delivery_minutes"].isna().sum()
)
print(
    "Missing delivery_minutes among cancelled:",
    orders.loc[cancelled_mask, "delivery_minutes"].isna().sum()
)

completed_total = orders.loc[
    completed_mask, "order_amount"
].sum()

print("Completed order amount total (INR):", round(completed_total, 2))
print("Saved to:", output_path)
