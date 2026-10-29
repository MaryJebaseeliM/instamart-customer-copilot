
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
ORDERS_PATH = ROOT / "data" / "clean" / "orders.csv"
OUTPUT_PATH = ROOT / "outputs" / "rfm_table.csv"

SNAPSHOT = pd.Timestamp("2025-10-01 00:00:00")

# Load cleaned order data
orders = pd.read_csv(ORDERS_PATH)

# Convert timestamps and keep completed orders only
orders["order_ts"] = pd.to_datetime(orders["order_ts"], errors="coerce")
orders["status"] = orders["status"].astype(str).str.strip().str.lower()

completed = orders.loc[
    orders["status"].eq("completed")
].copy()

# Exclude rows without the fields required for RFM
completed = completed.dropna(
    subset=["customer_id", "order_id", "order_ts", "order_amount"]
)

# Calculate the most recent completed order for each customer
last_order = completed.groupby("customer_id")["order_ts"].max()

# Count distinct completed orders for each customer
frequency = completed.groupby("customer_id")["order_id"].nunique()

# Sum completed-order spending for each customer
monetary = completed.groupby("customer_id")["order_amount"].sum()

# Combine the metrics into one RFM table
rfm = pd.DataFrame({
    "last_order_ts": last_order,
    "frequency": frequency,
    "monetary": monetary,
})

# Recency in whole days as of the required snapshot
rfm["recency"] = (SNAPSHOT - rfm["last_order_ts"]).dt.days

# Arrange columns for readability
rfm = rfm[
    ["last_order_ts", "recency", "frequency", "monetary"]
].reset_index()

# Save the output
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
rfm.to_csv(OUTPUT_PATH, index=False)

# Display summary statistics for validation
print(f"RFM customers: {len(rfm)}")
print("\nRFM summary:")
print(rfm[["recency", "frequency", "monetary"]].describe())

print("\nReference checks:")
print("Recency median:", rfm["recency"].median())
print("Minimum recency:", rfm["recency"].min())
print("Maximum recency:", rfm["recency"].max())
print("Mean frequency:", round(rfm["frequency"].mean(), 2))
print("Maximum frequency:", rfm["frequency"].max())
print("Mean monetary:", round(rfm["monetary"].mean(), 2))
print("Maximum monetary:", round(rfm["monetary"].max(), 2))

print(f"\nSaved RFM table to: {OUTPUT_PATH}")