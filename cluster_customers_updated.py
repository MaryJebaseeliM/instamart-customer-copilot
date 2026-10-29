
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
RFM_PATH = ROOT / "outputs" / "rfm_table.csv"
OUTPUT_DIR = ROOT / "outputs"

# Load RFM data
rfm = pd.read_csv(RFM_PATH)

features = ["recency", "frequency", "monetary"]
X = rfm[features].apply(pd.to_numeric, errors="coerce")
valid_rows = X.notna().all(axis=1)

rfm = rfm.loc[valid_rows].copy().reset_index(drop=True)
X = X.loc[valid_rows].reset_index(drop=True)

# Standardise all three RFM features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Evaluate K values from 2 to 8
metrics = []

for k in range(2, 9):
    model = KMeans(
        n_clusters=k,
        n_init=10,
        random_state=42
    )
    labels = model.fit_predict(X_scaled)

    metrics.append({
        "K": k,
        "inertia": model.inertia_,
        "silhouette": silhouette_score(X_scaled, labels)
    })

metrics_df = pd.DataFrame(metrics)
metrics_df.to_csv(OUTPUT_DIR / "kmeans_metrics.csv", index=False)

print("\nK-means evaluation:")
print(metrics_df.round(3).to_string(index=False))

# Fit final K=4 model
FINAL_K = 4

model = KMeans(
    n_clusters=FINAL_K,
    n_init=10,
    random_state=42
)

rfm["segment_id"] = model.fit_predict(X_scaled)

# Business names based on the existing K=4 cluster profiles
segment_names = {
    0: "Occasional, Lower-Spend Customers",
    1: "Premium - High-Value Customers",
    2: "Frequent, Recently Active Customers",
    3: "Lapsed or At-Risk Customers"
}

rfm["segment_name"] = rfm["segment_id"].map(segment_names)

# Premium is the segment with the highest mean monetary value
mean_spend = rfm.groupby("segment_id")["monetary"].mean()
premium_segment_id = int(mean_spend.idxmax())

rfm["is_premium"] = rfm["segment_id"].eq(premium_segment_id)

# Save only the columns required by the assignment
customer_segments = rfm[
    [
        "customer_id",
        "recency",
        "frequency",
        "monetary",
        "segment_id",
        "segment_name",
        "is_premium"
    ]
].copy()

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

customer_segments.to_csv(
    OUTPUT_DIR / "customer_segments.csv",
    index=False
)

# Calculate mean RFM values for the report
profiles = (
    customer_segments.groupby(
        ["segment_id", "segment_name", "is_premium"],
        as_index=False
    )
    .agg(
        customer_count=("customer_id", "nunique"),
        mean_recency=("recency", "mean"),
        mean_frequency=("frequency", "mean"),
        mean_monetary=("monetary", "mean")
    )
)

profiles[
    ["mean_recency", "mean_frequency", "mean_monetary"]
] = profiles[
    ["mean_recency", "mean_frequency", "mean_monetary"]
].round(2)

profiles.to_csv(OUTPUT_DIR / "cluster_profiles.csv", index=False)

print("\nSegment profiles (MEANS):")
print(profiles.to_string(index=False))

# PCA must use the standardised RFM matrix
pca = PCA(n_components=2)
pca.fit(X_scaled)

variance = pca.explained_variance_ratio_

print("\nPCA explained variance ratio:")
print("PC1:", round(variance[0], 3))
print("PC2:", round(variance[1], 3))
print("Total:", round(variance.sum(), 3))

# Basic output checks
expected_columns = [
    "customer_id", "recency", "frequency", "monetary",
    "segment_id", "segment_name", "is_premium"
]

assert list(customer_segments.columns) == expected_columns
assert customer_segments["segment_id"].nunique() == FINAL_K
assert customer_segments["is_premium"].sum() == (
    customer_segments["segment_id"] == premium_segment_id
).sum()

print("\nPremium segment ID:", premium_segment_id)
print("Premium mean monetary value:", round(mean_spend.max(), 2))
print("Saved outputs/customer_segments.csv")
print("Saved outputs/cluster_profiles.csv")
print("Saved outputs/kmeans_metrics.csv")