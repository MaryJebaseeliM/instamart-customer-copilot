from pathlib import Path
import sqlite3
from itertools import combinations

import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "instamart.db"
OUTPUT_DIR = ROOT / "outputs" / "pandas"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if not DB_PATH.exists():
    raise FileNotFoundError(
        f"Database not found: {DB_PATH}\n"
        "Run store_validate.py first, from the project root."
    )

with sqlite3.connect(DB_PATH) as conn:
    # Q2 cross-check: revenue by city and product category, completed orders only.
    # q2 = pd.read_sql_query(
      # """
       #FROM orders AS o
       #JOIN customers AS c ON c.customer_id = o.customer_id
       #JOIN products AS p ON p.product_id = o.product_id
       #WHERE LOWER(o.status) = 'completed'
       #GROUP BY c.city, p.category
       #""",
     #conn,
    #)
   #"""
    q2_data = pd.read_sql_query(
    """
    SELECT c.city, p.category, o.order_amount
    FROM orders AS o
    JOIN customers AS c ON c.customer_id = o.customer_id
    JOIN products AS p ON p.product_id = o.product_id
    WHERE LOWER(o.status) = 'completed'
    """,
    conn,
)
    sql_total = pd.read_sql_query(
        """
        SELECT SUM(order_amount) AS total
        FROM orders
        WHERE LOWER(status) = 'completed'
        """,
        conn,
    ).loc[0, "total"]

    # Completed-order observations for city summaries, descriptive statistics,
    # outlier checks, and correlation.
    completed = pd.read_sql_query(
        """
        SELECT c.city, o.order_amount, o.discount_pct, o.quantity,
               o.delivery_minutes
        FROM orders AS o
        JOIN customers AS c ON c.customer_id = o.customer_id
        WHERE LOWER(o.status) = 'completed'
        """,
        conn,
    )

# Pivot Q2 in the same shape as the SQL city/category aggregation.
#pivot = pd.pivot_table(
    #q2,
    #index="city",
    #columns="category",
    #values="revenue",
    #aggfunc="sum",
    #fill_value=0,
    #margins=True,
    #margins_name="All",
#)
pivot = pd.pivot_table(
    q2_data,
    index="city",
    columns="category",
    values="order_amount",
    aggfunc="sum",
    fill_value=0,
    margins=True,
    margins_name="All",
)
pivot.to_csv(OUTPUT_DIR / "q2_pivot_with_margins.csv")
pivot_total = float(pivot.loc["All", "All"])

print("\n=== Q2 pivot_table cross-check ===")
print(pivot.to_string())
print(f"\nSQL completed revenue total:   INR {sql_total:,.2f}")
print(f"Pivot grand total (All/All):   INR {pivot_total:,.2f}")
print(f"Totals match (within 1 paisa): {abs(float(sql_total) - pivot_total) < 0.01}")

# Per-city named aggregation: total spend, average order amount, and order count.
city_summary = (
    completed.groupby("city", dropna=False)
    .agg(
        total_order_amount=("order_amount", "sum"),
        mean_order_amount=("order_amount", "mean"),
        order_count=("order_amount", "count"),
    )
    .sort_index()
)
city_summary.to_csv(OUTPUT_DIR / "completed_order_summary_by_city.csv")

print("\n=== Completed order_amount by city ===")
print(city_summary.round({"total_order_amount": 2, "mean_order_amount": 2}).to_string())

amount = pd.to_numeric(completed["order_amount"], errors="coerce").dropna()
mean_value = amount.mean()
median_value = amount.median()
skew_value = amount.skew()
q1 = amount.quantile(0.25)
q2_median = amount.quantile(0.50)
q3 = amount.quantile(0.75)
iqr = q3 - q1
lower_fence = q1 - 1.5 * iqr
upper_fence = q3 + 1.5 * iqr
below_count = int((amount < lower_fence).sum())
above_count = int((amount > upper_fence).sum())

stats = pd.DataFrame(
    [
        ("count", int(amount.count())),
        ("mean", mean_value),
        ("median", median_value),
        ("skewness", skew_value),
        ("Q1 (25%)", q1),
        ("Q2 / median (50%)", q2_median),
        ("Q3 (75%)", q3),
        ("IQR (Q3 - Q1)", iqr),
        ("lower 1.5xIQR fence", lower_fence),
        ("upper 1.5xIQR fence", upper_fence),
        ("outliers below lower fence", below_count),
        ("outliers above upper fence", above_count),
    ],
    columns=["statistic", "value"],
)
stats.to_csv(OUTPUT_DIR / "completed_order_amount_statistics.csv", index=False)

print("\n=== Completed order_amount statistics ===")
for _, row in stats.iterrows():
    name, value = row["statistic"], row["value"]
    if name == "count" or name.startswith("outliers"):
        print(f"{name}: {int(value):,}")
    elif name == "skewness":
        print(f"{name}: {value:.4f}")
    else:
        print(f"{name}: INR {value:,.2f}")

# Pearson correlation matrix. Use numeric columns and complete observations for
# these four variables so every coefficient uses the same set of rows.
corr_columns = ["order_amount", "discount_pct", "quantity", "delivery_minutes"]
corr_data = completed[corr_columns].apply(pd.to_numeric, errors="coerce").dropna()
corr = corr_data.corr(method="pearson")
corr.to_csv(OUTPUT_DIR / "completed_orders_correlation_matrix.csv")

pairs = []
for left, right in combinations(corr_columns, 2):
    pairs.append((left, right, float(corr.loc[left, right])))
largest_pair = max(pairs, key=lambda item: abs(item[2]))

print("\n=== Completed-order correlation matrix (Pearson) ===")
print(corr.round(4).to_string())
print(
    "\nLargest absolute correlation: "
    f"{largest_pair[0]} vs {largest_pair[1]} = {largest_pair[2]:+.4f}"
)
print(f"Rows used in correlation matrix: {len(corr_data):,}")

# A concise, data-driven interpretation for the assignment (under 200 words).
skew_description = "right-skewed" if skew_value > 0.5 else (
    "left-skewed" if skew_value < -0.5 else "roughly symmetric"
)
if below_count == 0:
    lower_outlier_text = "none below the lower fence"
else:
    lower_outlier_text = f"{below_count:,} below the lower fence"

interpretation = (
    f"The data describes completed Instamart orders and their amounts, discounts, "
    f"quantities, delivery times, cities and product categories. Completed order "
    f"amounts have mean INR {mean_value:,.2f}, median INR {median_value:,.2f}, "
    f"and skewness {skew_value:.2f}, indicating a {skew_description} distribution. "
    f"Q1 is INR {q1:,.2f} and Q3 is INR {q3:,.2f}; the 1.5×IQR fences are "
    f"INR {lower_fence:,.2f} and INR {upper_fence:,.2f}. There are "
    f"{below_count:,} low outliers ({lower_outlier_text}) and {above_count:,} "
    f"high outliers above the upper fence. These may reflect unusually large "
    f"orders and should be checked, not automatically removed. The strongest "
    f"pairwise Pearson correlation by absolute value is {largest_pair[0]} with "
    f"{largest_pair[1]} (r = {largest_pair[2]:+.3f}); order amount with quantity "
    f"has r = {corr.loc['order_amount', 'quantity']:+.3f}. These correlations are "
    f"weak, and a correlation of this size does not establish causation."
)
word_count = len(interpretation.split())
print(f"\n=== Interpretation ({word_count} words; maximum 200) ===")
print(interpretation)

print(f"\nCSV outputs saved in: {OUTPUT_DIR}")
