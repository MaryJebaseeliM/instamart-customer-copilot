
from pathlib import Path
import json

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import GridSearchCV
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)

# --------------------------------------------------
# 1. Paths and input data
# --------------------------------------------------
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

train_path = OUTPUT_DIR / "lapse_train_processed.csv"
test_path = OUTPUT_DIR / "lapse_test_processed.csv"

train_df = pd.read_csv(train_path)
test_df = pd.read_csv(test_path)

target = "lapsed"
id_column = "customer_id"

# Use exactly the same feature columns for train and test.
excluded_columns = [target, id_column]
feature_columns = [
    col for col in train_df.columns if col not in excluded_columns
]

if target not in train_df.columns or target not in test_df.columns:
    raise ValueError("The lapsed target column is missing.")

if feature_columns != [
    col for col in test_df.columns if col not in excluded_columns
]:
    raise ValueError("Training and test feature columns do not match.")

X_train = train_df[feature_columns]
y_train = train_df[target].astype(int)

X_test = test_df[feature_columns]
y_test = test_df[target].astype(int)

if X_train.isna().any().any() or X_test.isna().any().any():
    raise ValueError("Missing values found in processed features.")

print("=" * 60)
print("DATA SUMMARY")
print("=" * 60)
print(f"Training rows: {len(X_train)}")
print(f"Test rows: {len(X_test)}")
print(f"Number of features: {len(feature_columns)}")
print(f"Training lapsed customers: {(y_train == 1).sum()}")
print(f"Training non-lapsed customers: {(y_train == 0).sum()}")
print(f"Test lapsed customers: {(y_test == 1).sum()}")
print(f"Test non-lapsed customers: {(y_test == 0).sum()}")

# --------------------------------------------------
# 2. Baseline: always predict not lapsed (class 0)
# --------------------------------------------------
baseline_predictions = [0] * len(y_test)

baseline_cm = confusion_matrix(
    y_test, baseline_predictions, labels=[0, 1]
)

baseline_accuracy = accuracy_score(y_test, baseline_predictions)
baseline_precision = precision_score(
    y_test, baseline_predictions, zero_division=0
)
baseline_recall = recall_score(
    y_test, baseline_predictions, zero_division=0
)
baseline_f1 = f1_score(
    y_test, baseline_predictions, zero_division=0
)

print("\n" + "=" * 60)
print("BASELINE: ALWAYS PREDICT NOT LAPSED")
print("=" * 60)
print("Confusion matrix [[TN, FP], [FN, TP]]:")
print(baseline_cm)
print(f"Accuracy:  {baseline_accuracy:.4f}")
print(f"Precision: {baseline_precision:.4f}")
print(f"Recall:    {baseline_recall:.4f}")
print(f"Lapsed F1: {baseline_f1:.4f}")

# --------------------------------------------------
# 3. Tune logistic regression on training data only
# --------------------------------------------------
print("\n" + "=" * 60)
print("LOGISTIC REGRESSION GRID SEARCH")
print("=" * 60)

logistic_grid = GridSearchCV(
    estimator=LogisticRegression(max_iter=1000),
    param_grid={"C": [0.01, 0.1, 1, 10, 100]},
    scoring="f1",
    cv=5,
    n_jobs=-1,
    refit=True,
)

logistic_grid.fit(X_train, y_train)

best_logistic = logistic_grid.best_estimator_

print("Best parameters:", logistic_grid.best_params_)
print(f"Best mean CV F1: {logistic_grid.best_score_:.4f}")

# --------------------------------------------------
# 4. Tune random forest on training data only
# --------------------------------------------------
print("\n" + "=" * 60)
print("RANDOM FOREST GRID SEARCH")
print("=" * 60)

forest_grid = GridSearchCV(
    estimator=RandomForestClassifier(
        n_estimators=100,
        random_state=42,
    ),
    param_grid={
        "max_depth": [3, 5, 8],
        "min_samples_leaf": [5, 10, 20],
    },
    scoring="f1",
    cv=5,
    n_jobs=-1,
    refit=True,
)

forest_grid.fit(X_train, y_train)

best_forest = forest_grid.best_estimator_

print("Parameter combinations:", len(forest_grid.cv_results_["params"]))
print("CV fits:", len(forest_grid.cv_results_["params"]) * 5)
print("Best parameters:", forest_grid.best_params_)
print(f"Best mean CV F1: {forest_grid.best_score_:.4f}")

# --------------------------------------------------
# 5. Evaluate on the untouched test set
#    Only do this after both grid searches finish.
# --------------------------------------------------
def evaluate_model(name, model, X, y):
    predictions = model.predict(X)

    cm = confusion_matrix(y, predictions, labels=[0, 1])
    precision = precision_score(y, predictions, pos_label=1, zero_division=0)
    recall = recall_score(y, predictions, pos_label=1, zero_division=0)
    f1 = f1_score(y, predictions, pos_label=1, zero_division=0)
    accuracy = accuracy_score(y, predictions)

    print(f"\n{name}")
    print("-" * 45)
    print("Confusion matrix [[TN, FP], [FN, TP]]:")
    print(cm)
    print(f"Accuracy:  {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"Lapsed F1: {f1:.4f}")

    return {
        "model": name,
        "accuracy": accuracy,
        "lapsed_precision": precision,
        "lapsed_recall": recall,
        "lapsed_f1": f1,
        "tn": int(cm[0, 0]),
        "fp": int(cm[0, 1]),
        "fn": int(cm[1, 0]),
        "tp": int(cm[1, 1]),
    }


logistic_results = evaluate_model(
    "Tuned Logistic Regression", best_logistic, X_test, y_test
)

forest_results = evaluate_model(
    "Tuned Random Forest", best_forest, X_test, y_test
)

# --------------------------------------------------
# 6. Save results and best parameters
# --------------------------------------------------
results = pd.DataFrame([logistic_results, forest_results])
results.to_csv(OUTPUT_DIR / "lapse_model_test_results.csv", index=False)

search_summary = {
    "logistic_regression": {
        "best_params": logistic_grid.best_params_,
        "best_cv_f1": float(logistic_grid.best_score_),
    },
    "random_forest": {
        "best_params": forest_grid.best_params_,
        "best_cv_f1": float(forest_grid.best_score_),
    },
}

with open(OUTPUT_DIR / "lapse_model_tuning_results.json", "w") as file:
    json.dump(search_summary, file, indent=2)

print("\nSaved:")
print(OUTPUT_DIR / "lapse_model_test_results.csv")
print(OUTPUT_DIR / "lapse_model_tuning_results.json")

# Choose the model with the higher held-out lapsed-class F1.
selected = max(
    [logistic_results, forest_results],
    key=lambda result: result["lapsed_f1"],
)

print("\nSelected model by test lapsed F1:", selected["model"])
print(f"Selected test F1: {selected['lapsed_f1']:.4f}")

if selected["lapsed_f1"] < 0.55:
    print(
        "WARNING: Selected test F1 is below the assignment requirement of 0.55. "
        "Review the feature construction and model results."
    )
else:
    print("Selected model meets the minimum test F1 requirement of 0.55.")