
import pandas as pd
from pathlib import Path

# File locations
RAW_DIR = Path("data") / "raw"
CLEAN_DIR = Path("data") / "clean"
CLEAN_DIR.mkdir(parents=True, exist_ok=True)

# Load raw customer data
customers = pd.read_csv(RAW_DIR / "customers.csv")

print("Before cleaning:", customers.shape)

# (a) Standardise city names
customers["city"] = (
    customers["city"]
    .astype("string")
    .str.strip()
    .str.title()
)

# (b) Standardise gender values
# First clean whitespace and case, then map variations
gender_normalised = (
    customers["gender"]
    .astype("string")
    .str.strip()
    .str.lower()
)

gender_mapping = {
    "m": "male",
    "male": "male",
    "man": "male",
    "f": "female",
    "female": "female",
    "woman": "female",
    "": "unknown",
    "unknown": "unknown",
    "nan": "unknown",
    "<na>": "unknown",
    "none": "unknown",
    "null": "unknown",
}

customers["gender"] = gender_normalised.map(gender_mapping).fillna("unknown")

# (c) Convert age to numeric and mark invalid ages as missing
customers["age"] = pd.to_numeric(customers["age"], errors="coerce")

customers.loc[
    ~customers["age"].between(10, 100),
    "age"
] = pd.NA

# Fill missing ages with the median of each city.
# transform returns a city median for each individual row.
city_medians = customers.groupby("city")["age"].transform("median")
customers["age"] = customers["age"].fillna(city_medians)

# Fallback only if a city has no usable ages at all
customers["age"] = customers["age"].fillna(customers["age"].median())

# Store age as integer after filling
customers["age"] = customers["age"].round().astype("int64")

# (d) Convert signup_date to datetime
customers["signup_date"] = pd.to_datetime(
    customers["signup_date"],
    errors="coerce"
)

# Save cleaned customer data
output_path = CLEAN_DIR / "customers.csv"
customers.to_csv(output_path, index=False)

# --------------------------------------------------
# Validate the results
# --------------------------------------------------
print("\nCleaned city counts:")
print(customers["city"].value_counts().sort_index())

print("\nCleaned gender counts:")
print(customers["gender"].value_counts())

print("\nAge validation:")
print("Missing ages:", customers["age"].isna().sum())
print("Minimum age:", customers["age"].min())
print("Maximum age:", customers["age"].max())

print("\nSignup date data type:")
print(customers["signup_date"].dtype)

print("\nSaved cleaned data to:", output_path)
