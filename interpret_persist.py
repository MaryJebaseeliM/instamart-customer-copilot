
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

# --------------------------------------------------
# Paths
# --------------------------------------------------
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)

train_path = OUT / "lapse_train_processed.csv"
test_path = OUT / "lapse_test_processed.csv"
segments_path = OUT / "customer_segments.csv"

# --------------------------------------------------
# 1. Load the already-preprocessed data
# --------------------------------------------------
train_df = pd.read_csv(train_path)
test_df = pd.read_csv(test_path)
segments_df = pd.read_csv(segments_path)

target = "lapsed"
id_col = "customer_id"

# Use the same transformed features for both models.
feature_cols = [
    col for col in train_df.columns
    if col not in [id_col, target]
]

X_train = train_df[feature_cols]
y_train = train_df[target].astype(int)

X_test = test_df[feature_cols]
y_test = test_df[target].astype(int)

print("Training rows:", len(X_train))
print("Test rows:", len(X_test))
print("Transformed features:", len(feature_cols))

# --------------------------------------------------
# 2. Fit the best Random Forest from Task 6
# --------------------------------------------------
rf_model = RandomForestClassifier(
    n_estimators=100,
    max_depth=8,
    min_samples_leaf=10,
    random_state=42
)
rf_model.fit(X_train, y_train)

# Five most important features
importance_df = pd.DataFrame({
    "feature": feature_cols,
    "importance": rf_model.feature_importances_
}).sort_values("importance", ascending=False)

top5 = importance_df.head(5).copy()
top5.to_csv(OUT / "task8_rf_top5_importance.csv", index=False)

print("\n(a) TOP 5 RANDOM FOREST FEATURES")
print(top5.to_string(index=False))

# --------------------------------------------------
# 3. Fit the best Logistic Regression from Task 6
# --------------------------------------------------
lr_model = LogisticRegression(
    C=100,
    max_iter=1000
)
lr_model.fit(X_train, y_train)

coef_df = pd.DataFrame({
    "feature": feature_cols,
    "coefficient": lr_model.coef_[0]
})
coef_df["sign"] = np.where(
    coef_df["coefficient"] > 0, "positive",
    np.where(coef_df["coefficient"] < 0, "negative", "zero")
)

# Report the three coefficients with the largest absolute magnitude.
top3_coef = (
    coef_df.assign(abs_coefficient=coef_df["coefficient"].abs())
    .sort_values("abs_coefficient", ascending=False)
    .head(3)
    .drop(columns="abs_coefficient")
)
top3_coef.to_csv(OUT / "task8_lr_top3_coefficients.csv", index=False)

print("\n(a) THREE LOGISTIC REGRESSION COEFFICIENTS")
print(top3_coef.to_string(index=False))

# --------------------------------------------------
# 4. Save and reload the selected Random Forest
# --------------------------------------------------
model_path = OUT / "lapse_model.joblib"
joblib.dump(rf_model, model_path)

original_predictions = rf_model.predict(X_test)

reloaded_model = joblib.load(model_path)
reloaded_predictions = reloaded_model.predict(X_test)

predictions_match = np.array_equal(
    original_predictions, reloaded_predictions
)

print("\n(b) MODEL PERSISTENCE CHECK")
print("Saved model:", model_path)
print("Reloaded predictions exactly match:", predictions_match)
print(
    "Number of differing predictions:",
    int(np.sum(original_predictions != reloaded_predictions))
)

assert predictions_match, "Reloaded model predictions do not match!"

# --------------------------------------------------
# 5. Premium test customers ranked by lapse probability
# --------------------------------------------------
required_segment_cols = [id_col, "is_premium"]
missing_cols = [
    col for col in required_segment_cols
    if col not in segments_df.columns
]
if missing_cols:
    raise ValueError(
        f"Missing columns in customer_segments.csv: {missing_cols}"
    )

premium_ids = set(
    segments_df.loc[
        segments_df["is_premium"].astype(str).str.lower().isin(
            ["true", "1", "yes"]
        ),
        id_col
    ].astype(str)
)

# Preserve the test-set IDs and actual labels.
test_customers = test_df[[id_col, target]].copy()
test_customers[id_col] = test_customers[id_col].astype(str)
test_customers["actually_lapsed"] = test_customers[target].astype(int)

premium_test = test_customers[
    test_customers[id_col].isin(premium_ids)
].copy()

# Use the selected Random Forest's probability for class 1 (lapsed).
lapsed_class_index = list(reloaded_model.classes_).index(1)
premium_test["lapse_probability"] = reloaded_model.predict_proba(
    X_test.loc[premium_test.index]
)[:, lapsed_class_index]

retention_list = (
    premium_test.sort_values("lapse_probability", ascending=False)
    .head(10)[[id_col, "lapse_probability", "actually_lapsed"]]
    .rename(columns={id_col: "customer_id"})
)

retention_list["lapse_probability"] = retention_list[
    "lapse_probability"
].round(6)

retention_path = OUT / "retention_list.csv"
retention_list.to_csv(retention_path, index=False)

true_lapsed_count = int(retention_list["actually_lapsed"].sum())

print("\n(c) PREMIUM CUSTOMER RETENTION LIST")
print("Premium customers in test set:", len(premium_test))
print("Rows written to retention list:", len(retention_list))
print("Truly lapsed customers in retention list:", true_lapsed_count)
print(retention_list.to_string(index=False))
print("\nSaved:", retention_path)
print("\nTask 8 completed.")