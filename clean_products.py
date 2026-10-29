
import pandas as pd
from pathlib import Path

RAW_DIR = Path("data") / "raw"
CLEAN_DIR = Path("data") / "clean"

CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# Load the raw product table
products = pd.read_csv(RAW_DIR / "products.csv")

print("Raw products shape:", products.shape)
print("Product columns:", products.columns.tolist())

# No product-cleaning rules have been provided yet,
# so preserve the data without changing its values.
products.to_csv(CLEAN_DIR / "products.csv", index=False)

print("Clean products shape:", products.shape)
print("Saved to:", CLEAN_DIR / "products.csv")