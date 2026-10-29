
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "clean"
OUTPUT_DIR = ROOT / "outputs"

CUTOFF = pd.Timestamp("2025-09-01")
LABEL_END = pd.Timestamp("2025-10-01")

# Load cleaned datasets
orders = pd.read_csv(DATA_DIR / "orders.csv")
customers = pd.read_csv(DATA_DIR / "customers.csv")
products = pd.read_csv(DATA_DIR / "products.csv")

# Standardise relevant fields
orders["order_ts"] = pd.to_datetime(orders["order_ts"], errors="coerce")
orders["status"] = orders["status"].astype(str).str.strip().str.lower()
customers["signup_date"] = pd.to_datetime(
    customers["signup_date"], errors="coerce"
)

orders["order_amount"] = pd.to_numeric(
    orders["order_amount"], errors="coerce"
)
orders["discount_pct"] = pd.to_numeric(
    orders["discount_pct"], errors="coerce"
)
orders["delivery_minutes"] = pd.to_numeric(
    orders["delivery_minutes"], errors="coerce"
)

# Cohort feature data: STRICTLY before the cutoff
pre_cutoff = orders.loc[orders["order_ts"] < CUTOFF].copy()

# Completed orders used for customer behaviour features
completed_pre = pre_cutoff.loc[
    pre_cutoff["status"].eq("completed")
].copy()

# Cohort = customers with at least one completed order before cutoff
cohort_ids = completed_pre["customer_id"].dropna().unique()

# Label window: September 1 through September 30, 2025
september = orders.loc[
    (orders["order_ts"] >= CUTOFF)
    & (orders["order_ts"] < LABEL_END)
    & (orders["status"] == "completed")
]

september_ordered_ids = set(september["customer_id"].dropna().unique())

# Create one row per cohort customer
dataset = customers.loc[
    customers["customer_id"].isin(cohort_ids)
].copy()

dataset = dataset.drop_duplicates("customer_id")

# Target label: 1 if no completed order during September
dataset["lapsed"] = (
    ~dataset["customer_id"].isin(september_ordered_ids)
).astype(int)

# 1. Recency, frequency and monetary from completed pre-cutoff orders
rfm = completed_pre.groupby("customer_id").agg(
    last_order_ts=("order_ts", "max"),
    frequency=("order_id", "nunique"),
    monetary=("order_amount", "sum"),
).reset_index()

rfm["recency"] = (CUTOFF - rfm["last_order_ts"]).dt.days
rfm = rfm.drop(columns=["last_order_ts"])

# 2. Average discount on completed pre-cutoff orders
discount = completed_pre.groupby("customer_id").agg(
    avg_discount_pct=("discount_pct", "mean")
).reset_index()

# 3. Average delivery time on completed pre-cutoff orders
delivery = completed_pre.groupby("customer_id").agg(
    avg_delivery_minutes=("delivery_minutes", "mean")
).reset_index()

# 4. Cancellation rate from orders with a final status before cutoff.
# Pending orders are not included in the denominator.
final_orders = pre_cutoff.loc[
    pre_cutoff["status"].isin(["completed", "cancelled"])
].copy()

final_orders["is_cancelled"] = (
    final_orders["status"] == "cancelled"
).astype(int)

cancellation = final_orders.groupby("customer_id").agg(
    cancelled_count=("is_cancelled", "sum"),
    final_order_count=("order_id", "nunique"),
).reset_index()

cancellation["cancellation_rate"] = (
    cancellation["cancelled_count"]
    / cancellation["final_order_count"]
)

cancellation = cancellation[
    ["customer_id", "cancellation_rate"]
]

# 5. Most frequent product category from completed pre-cutoff orders
category_orders = completed_pre.merge(
    products[["product_id", "category"]],
    on="product_id",
    how="left",
)

category_counts = (
    category_orders.groupby(["customer_id", "category"])
    .size()
    .reset_index(name="category_order_count")
    .sort_values(
        ["customer_id", "category_order_count", "category"],
        ascending=[True, False, True],
    )
)

# Deterministic tie-break: alphabetically first category
most_frequent_category = (
    category_counts.drop_duplicates("customer_id")
    [["customer_id", "category"]]
    .rename(columns={"category": "most_frequent_category"})
)

# Combine the historical features
for feature_df in [
    rfm,
    discount,
    delivery,
    cancellation,
    most_frequent_category,
]:
    dataset = dataset.merge(
        feature_df,
        on="customer_id",
        how="left",
        validate="one_to_one",
    )

# Tenure in days as of the cutoff
dataset["tenure_days"] = (
    CUTOFF - dataset["signup_date"]
).dt.days

# Keep required feature fields and label
feature_columns = [
    "customer_id",
    "recency",
    "frequency",
    "monetary",
    "avg_discount_pct",
    "cancellation_rate",
    "avg_delivery_minutes",
    "most_frequent_category",
    "city",
    "age",
    "gender",
    "tenure_days",
]

model_data = dataset[feature_columns + ["lapsed"]].copy()

# Save the complete modelling dataset
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
model_data.to_csv(OUTPUT_DIR / "lapse_dataset.csv", index=False)

# Train/test split: target is not a feature
X = model_data[feature_columns].drop(columns=["customer_id"])
y = model_data["lapsed"]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    stratify=y,
    random_state=42,
)

# Baseline: always predict "not lapsed" (class 0)
baseline_predictions = [0] * len(y_test)

print("Cohort customers:", len(model_data))
print("Lapsed customers:", int(y.sum()))
print("Lapse rate (%):", round(y.mean() * 100, 2))
print("Training rows:", len(X_train))
print("Test rows:", len(X_test))
print(
    "Baseline accuracy:",
    round(accuracy_score(y_test, baseline_predictions), 3),
)
print(
    "Baseline lapsed-class F1:",
    round(
        f1_score(
            y_test,
            baseline_predictions,
            pos_label=1,
            zero_division=0,
        ),
        3,
    ),
)

print("\nFeature columns:")
print(X.columns.tolist())

print("\nSaved:", OUTPUT_DIR / "lapse_dataset.csv")