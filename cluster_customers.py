
from pathlib import Path

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
RFM_PATH = ROOT / "outputs" / "rfm_table.csv"
OUTPUT_DIR = ROOT / "outputs"

# Read the RFM table from Task 1
rfm = pd.read_csv(RFM_PATH)

features = ["recency", "frequency", "monetary"]
X = rfm[features].copy()

# Ensure the features are numeric and complete
X = X.apply(pd.to_numeric, errors="coerce")
valid_rows = X.notna().all(axis=1)

rfm_valid = rfm.loc[valid_rows].copy()
X = X.loc[valid_rows]

# Standardise RFM features before clustering
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Evaluate K from 2 through 8
results = []

for k in range(2, 9):
    model = KMeans(
        n_clusters=k,
        n_init=10,
        random_state=42
    )

    labels = model.fit_predict(X_scaled)

    results.append({
        "K": k,
        "inertia": model.inertia_,
        "silhouette": silhouette_score(X_scaled, labels)
    })

metrics = pd.DataFrame(results)
metrics["inertia"] = metrics["inertia"].round(1)
metrics["silhouette"] = metrics["silhouette"].round(3)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
metrics.to_csv(OUTPUT_DIR / "kmeans_metrics.csv", index=False)

print("K-means evaluation:")
print(metrics.to_string(index=False))

# Fit the selected final model
FINAL_K = 4

final_model = KMeans(
    n_clusters=FINAL_K,
    n_init=10,
    random_state=42
)

rfm_valid["cluster"] = final_model.fit_predict(X_scaled)

# Save customer assignments for downstream tasks
rfm_valid.to_csv(
    OUTPUT_DIR / "customer_segments.csv",
    index=False
)

# Summarise each cluster for business interpretation
profile = (
    rfm_valid.groupby("cluster")
    .agg(
        customer_count=("customer_id", "nunique"),
        median_recency=("recency", "median"),
        mean_frequency=("frequency", "mean"),
        mean_monetary=("monetary", "mean"),
        median_monetary=("monetary", "median")
    )
    .round(2)
)

profile.to_csv(OUTPUT_DIR / "cluster_profiles.csv")

print("\nCluster profiles:")
print(profile.to_string())

print("\nSaved:")
print(OUTPUT_DIR / "kmeans_metrics.csv")
print(OUTPUT_DIR / "customer_segments.csv")
print(OUTPUT_DIR / "cluster_profiles.csv")