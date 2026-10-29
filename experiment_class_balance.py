
from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score,
)

# --------------------------------------------------
# 1. Load the existing train/test split
# --------------------------------------------------
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs"

train_df = pd.read_csv(OUTPUT_DIR / "lapse_train_processed.csv")
test_df = pd.read_csv(OUTPUT_DIR / "lapse_test_processed.csv")

TARGET = "lapsed"
ID_COLUMN = "customer_id"

feature_columns = [
    col for col in train_df.columns
    if col not in [TARGET, ID_COLUMN]
]

X_train = train_df[feature_columns]
y_train = train_df[TARGET].astype(int)

X_test = test_df[feature_columns]
y_test = test_df[TARGET].astype(int)

# --------------------------------------------------
# 2. Report the original class balance
# --------------------------------------------------
print("=" * 60)
print("ORIGINAL TRAINING CLASS COUNTS")
print("=" * 60)

original_counts = y_train.value_counts().sort_index()
print("0 = not lapsed, 1 = lapsed")
print(original_counts)

# --------------------------------------------------
# 3. Oversample ONLY the training minority class
# --------------------------------------------------
training_data = X_train.copy()
training_data[TARGET] = y_train.to_numpy()

majority_count = int(original_counts.max())
minority_count = int(original_counts.min())

minority_class = int(original_counts.idxmin())

minority_rows = training_data[
    training_data[TARGET] == minority_class
]

number_to_add = majority_count - minority_count

# Draw duplicates with replacement, using random_state=42.
extra_rows = minority_rows.sample(
    n=number_to_add,
    replace=True,
    random_state=42,
)

# Keep all original rows and append the sampled duplicates.
balanced_train = pd.concat(
    [training_data, extra_rows],
    ignore_index=True,
)

balanced_counts = balanced_train[TARGET].value_counts().sort_index()

print("\n" + "=" * 60)
print("BALANCED TRAINING CLASS COUNTS")
print("=" * 60)
print(balanced_counts)
print(f"Duplicate rows added: {number_to_add}")

assert balanced_counts.nunique() == 1, (
    "Oversampling failed: classes are not balanced."
)

# Save the balanced training data for reproducibility.
balanced_train.to_csv(
    OUTPUT_DIR / "lapse_train_balanced.csv",
    index=False,
)

X_balanced = balanced_train[feature_columns]
y_balanced = balanced_train[TARGET].astype(int)

# --------------------------------------------------
# 4. Fit the original best Logistic Regression model
# --------------------------------------------------
# Use the best C found in Task 6.
# The original model is refitted on the original training rows,
# and the balanced model is fitted on the oversampled training rows.
original_model = LogisticRegression(
    C=100,
    max_iter=1000,
)
original_model.fit(X_train, y_train)

balanced_model = LogisticRegression(
    C=100,
    max_iter=1000,
)
balanced_model.fit(X_balanced, y_balanced)

# --------------------------------------------------
# 5. Evaluate BOTH models on the SAME unchanged test set
# --------------------------------------------------
def evaluate_model(name, model):
    predictions = model.predict(X_test)

    cm = confusion_matrix(
        y_test, predictions, labels=[0, 1]
    )

    precision = precision_score(
        y_test, predictions, pos_label=1, zero_division=0
    )
    recall = recall_score(
        y_test, predictions, pos_label=1, zero_division=0
    )
    f1 = f1_score(
        y_test, predictions, pos_label=1, zero_division=0
    )
    accuracy = accuracy_score(y_test, predictions)

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


original_results = evaluate_model(
    "Logistic Regression - Original Training Data",
    original_model,
)

balanced_results = evaluate_model(
    "Logistic Regression - Oversampled Training Data",
    balanced_model,
)

# --------------------------------------------------
# 6. Compare metric changes
# --------------------------------------------------
results = pd.DataFrame([
    original_results,
    balanced_results,
])

results.to_csv(
    OUTPUT_DIR / "lapse_class_balance_results.csv",
    index=False,
)

print("\n" + "=" * 60)
print("METRIC COMPARISON")
print("=" * 60)

metrics = [
    "lapsed_precision",
    "lapsed_recall",
    "lapsed_f1",
]

for metric in metrics:
    before = original_results[metric]
    after = balanced_results[metric]
    print(
        f"{metric}: {before:.4f} -> {after:.4f} "
        f"(change: {after - before:+.4f})"
    )

largest_change = max(
    metrics,
    key=lambda metric: abs(
        balanced_results[metric] - original_results[metric]
    ),
)

print(f"\nLargest absolute change: {largest_change}")
print("\nSaved:")
print(OUTPUT_DIR / "lapse_train_balanced.csv")
print(OUTPUT_DIR / "lapse_class_balance_results.csv")