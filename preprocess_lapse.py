
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from scipy.sparse import issparse
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent
INPUT_PATH = ROOT / "outputs" / "lapse_dataset.csv"
OUTPUT_DIR = ROOT / "outputs"

# Load the lapse dataset from Task 4
df = pd.read_csv(INPUT_PATH)

# Identify target, ID and feature columns
target_column = "lapsed"
id_column = "customer_id"

categorical_features = [
    "city",
    "gender",
    "most_frequent_category",
]

numeric_features = [
    "recency",
    "frequency",
    "monetary",
    "avg_discount_pct",
    "cancellation_rate",
    "avg_delivery_minutes",
    "age",
    "tenure_days",
]

# Do not use customer_id or segment labels as model features
X = df[numeric_features + categorical_features].copy()
y = df[target_column].astype(int)

# Verify that every feature is complete before preprocessing
missing_counts = X.isna().sum()

print("Missing values per feature:")
print(missing_counts.to_string())

assert not X.isna().any().any(), (
    "Missing feature values found. Fix them before preprocessing."
)

print("\nMissing-value check passed: all feature columns are complete.")

# Split before fitting any encoder or scaler
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    stratify=y,
    random_state=42,
)

print("\nTraining rows:", len(X_train))
print("Test rows:", len(X_test))

# Numerical features: standardise using training data only
numeric_pipeline = Pipeline([
    ("scaler", StandardScaler()),
])

# Categorical features: k-1 one-hot columns, learned from training only
categorical_pipeline = Pipeline([
    (
        "encoder",
        OneHotEncoder(
            drop="first",
            handle_unknown="ignore",
        ),
    ),
])

# Combine both preprocessing pipelines
preprocessor = ColumnTransformer(
    transformers=[
        ("numeric", numeric_pipeline, numeric_features),
        ("categorical", categorical_pipeline, categorical_features),
    ],
    remainder="drop",
)

# IMPORTANT: fit_transform only on training data
X_train_processed = preprocessor.fit_transform(X_train)

# Test data is transformed using training-learned settings only
X_test_processed = preprocessor.transform(X_test)

# Confirm no missing values after transformation
def contains_missing(matrix):
    if issparse(matrix):
        return bool(np.isnan(matrix.data).any())
    return bool(np.isnan(matrix).any())

assert not contains_missing(X_train_processed), (
    "Training matrix contains missing values."
)
assert not contains_missing(X_test_processed), (
    "Test matrix contains missing values."
)

print("Transformed training matrix has no missing values.")
print("Transformed test matrix has no missing values.")

# Compare frequency means
fitted_scaler = (
    preprocessor
    .named_transformers_["numeric"]
    .named_steps["scaler"]
)

frequency_index = numeric_features.index("frequency")
training_scaler_mean = fitted_scaler.mean_[frequency_index]
full_cohort_mean = X["frequency"].mean()

print("\nFrequency mean comparison:")
print("Training-only scaler mean:", round(training_scaler_mean, 4))
print("Full-cohort frequency mean:", round(full_cohort_mean, 4))

# Print transformed feature names
feature_names = preprocessor.get_feature_names_out()
print("\nNumber of transformed features:", len(feature_names))
print("Transformed feature names:")
print(feature_names.tolist())

# Save transformed data and fitted preprocessor
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

train_output = pd.DataFrame(
    X_train_processed.toarray()
    if issparse(X_train_processed)
    else X_train_processed,
    columns=feature_names,
    index=X_train.index,
)
train_output.insert(
    0, "customer_id", df.loc[X_train.index, id_column]
)
train_output["lapsed"] = y_train

test_output = pd.DataFrame(
    X_test_processed.toarray()
    if issparse(X_test_processed)
    else X_test_processed,
    columns=feature_names,
    index=X_test.index,
)
test_output.insert(
    0, "customer_id", df.loc[X_test.index, id_column]
)
test_output["lapsed"] = y_test

train_output.to_csv(
    OUTPUT_DIR / "lapse_train_processed.csv", index=False
)
test_output.to_csv(
    OUTPUT_DIR / "lapse_test_processed.csv", index=False
)

joblib.dump(
    preprocessor,
    OUTPUT_DIR / "lapse_preprocessor.joblib",
)

print("\nSaved:")
print(OUTPUT_DIR / "lapse_train_processed.csv")
print(OUTPUT_DIR / "lapse_test_processed.csv")
print(OUTPUT_DIR / "lapse_preprocessor.joblib")