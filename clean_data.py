"""
Data cleaning & transformation of the ApexPlanet Sales dataset.

Usage: python clean_data.py [input.xlsx] [output.csv]

Output: cleaned CSV, a before/after quality report (outputs/quality_report.csv) and an issues log (outputs/issues_log.csv).
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

IN_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/ApexPlanet_DataAnalytics_Dataset.xlsx")
OUT_PATH = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("outputs/cleaned_sales_data.csv")
OUT_DIR = OUT_PATH.parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

CITY_INFO = {  # city -> (state, region)
    "Patna": ("Bihar", "East"), "Gaya": ("Bihar", "East"),
    "Kolkata": ("West Bengal", "East"),
    "Mumbai": ("Maharashtra", "West"), "Pune": ("Maharashtra", "West"),
    "Delhi": ("Delhi", "North"),
    "Hyderabad": ("Telangana", "South"), "Bengaluru": ("Karnataka", "South"),
}
issues = []  # (issue, column, rows_affected, action)


def log(issue, col, n, action):
    issues.append({"issue": issue, "column": col, "rows_affected": int(n), "action_taken": action})


raw = pd.read_excel(IN_PATH)
df = raw.copy()
n_raw = len(df)

# 1. text standardisation
for c in ["Customer_Name", "Gender", "City", "Product", "Category", "Order_ID", "Customer_ID"]:
    before = df[c].copy()
    df[c] = df[c].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    changed = (before.fillna("") != df[c].fillna("")).sum()
    if changed:
        log("Stray whitespace", c, changed, "Trimmed / collapsed spaces")
for c in ["Gender", "City", "Product", "Category"]:
    df[c] = df[c].str.title()
df["Order_ID"] = df["Order_ID"].str.upper()
df["Customer_ID"] = df["Customer_ID"].str.upper()

# 2. dates
parsed = pd.to_datetime(df["Order_Date"], errors="coerce", format="mixed")
bad_dates = parsed.isna().sum()
if bad_dates:
    log("Unparseable dates", "Order_Date", bad_dates, "Set to NaT, row kept for review")
df["Order_Date"] = parsed.dt.normalize()

# 3. duplicates
full_dups = df.duplicated().sum()
if full_dups:
    df = df.drop_duplicates()
    log("Fully duplicated rows", "ALL", full_dups, "Dropped")

# Order_ID collisions: same ID, different order content.
# sequentially (ORD100002 + row position), and the 8 colliding rows are exactly the places where the sequence breaks, so the sequential ID is restored.

df = df.reset_index(drop=True)
dup_mask = df["Order_ID"].duplicated(keep=False)
expected = pd.Series([f"ORD{100002 + i}" for i in range(len(df))], index=df.index)
fix = dup_mask & (df["Order_ID"] != expected) & ~expected.isin(df["Order_ID"])
df["Order_ID_Corrected"] = fix
df.loc[fix, "Order_ID"] = expected[fix]
log("Order_ID collisions (same ID, different orders)", "Order_ID", fix.sum(),
    "Restored sequential ID from row sequence; flagged in Order_ID_Corrected")
assert df["Order_ID"].is_unique

# 4. missing values
n_age = df["Age"].isna().sum()
df["Age_Missing"] = df["Age"].isna()
log("Missing values", "Age", n_age, "Left null (not imputed, avoids inventing data); flagged Age_Missing; Age_Group='Unknown'")
n_city = df["City"].isna().sum()
df["City"] = df["City"].fillna("Unknown")
log("Missing values", "City", n_city, "Filled with 'Unknown'")

#  5. consistency / validation
calc = (df["Quantity"] * df["Unit_Price"]).round(2)
mismatch = ((calc - df["Total_Sales"]).abs() > 0.05).sum()
log("Total_Sales != Quantity x Unit_Price", "Total_Sales", mismatch,
    "Checked: no mismatches" if mismatch == 0 else "Recomputed from Quantity x Unit_Price")
if mismatch:
    df["Total_Sales"] = calc
cat_map = df.groupby("Product")["Category"].nunique()
assert (cat_map == 1).all(), "Product maps to >1 category"

# Customer_ID attributes are not stable (same ID, different name/age): documented only.
g = df.groupby("Customer_ID").agg(names=("Customer_Name", "nunique"), ages=("Age", "nunique"))
log("Customer_ID maps to multiple names", "Customer_ID", (g["names"] > 1).sum(),
    "Not changed - no reliable master record; documented as limitation (analyse by Customer_ID)")
log("Customer_ID maps to multiple ages", "Age", (g["ages"] > 1).sum(),
    "Not changed - documented as limitation")

#  6. outliers (flag, don't drop)
q1, q3 = df["Total_Sales"].quantile([.25, .75])
iqr = q3 - q1
hi = q3 + 1.5 * iqr
df["Sales_Outlier"] = df["Total_Sales"] > hi
log("High-value orders (IQR rule, > Q3+1.5*IQR = %.0f)" % hi, "Total_Sales", df["Sales_Outlier"].sum(),
    "Kept (valid bulk orders: high price x high quantity); flagged Sales_Outlier")
low_price = (df["Unit_Price"] < 1000).sum()
log("Very low unit prices (< 1,000 for Laptop/Mobile/Chair etc.)", "Unit_Price", low_price,
    "Kept; prices are spread evenly across products so no reliable per-product price to compare to - flagged for review")
df["Low_Price_Flag"] = df["Unit_Price"] < 1000

# 7. feature engineering
d = df["Order_Date"]
df["Order_Year"] = d.dt.year
df["Order_Month"] = d.dt.month
df["Order_Month_Name"] = d.dt.month_name()
df["Order_Quarter"] = "Q" + d.dt.quarter.astype("Int64").astype("string")
df["Order_Weekday"] = d.dt.day_name()
df["Is_Weekend"] = d.dt.dayofweek >= 5
df["Age_Group"] = pd.cut(df["Age"], [17, 24, 34, 44, 54, 65],
                         labels=["18-24", "25-34", "35-44", "45-54", "55-65"]).astype("string").fillna("Unknown")
df["State"] = df["City"].map(lambda c: CITY_INFO.get(c, ("Unknown", "Unknown"))[0])
df["Region"] = df["City"].map(lambda c: CITY_INFO.get(c, ("Unknown", "Unknown"))[1])
df["Order_Size"] = pd.cut(df["Quantity"], [0, 3, 7, 10], labels=["Small (1-3)", "Medium (4-7)", "Large (8-10)"]).astype("string")
df["Price_Band"] = pd.cut(df["Unit_Price"], [0, 10000, 25000, 40000, np.inf],
                          labels=["Budget (<10k)", "Mid (10-25k)", "Premium (25-40k)", "Luxury (40k+)"]).astype("string")
log("Derived features", "-", len(df), "Added date parts, Age_Group, State, Region, Order_Size, Price_Band")

# output
df = df.sort_values("Order_ID").reset_index(drop=True)
df.to_csv(OUT_PATH, index=False, date_format="%Y-%m-%d")
pd.DataFrame(issues).to_csv(OUT_DIR / "issues_log.csv", index=False)

report = pd.DataFrame({
    "metric": ["rows", "columns", "missing cells", "duplicate Order_IDs", "fully duplicated rows"],
    "before": [n_raw, raw.shape[1], int(raw.isna().sum().sum()), int(raw["Order_ID"].duplicated().sum()), int(raw.duplicated().sum())],
    "after": [len(df), df.shape[1], int(df.isna().sum().sum()), int(df["Order_ID"].duplicated().sum()), int(df.duplicated().sum())],
})
report.to_csv(OUT_DIR / "quality_report.csv", index=False)
print(pd.DataFrame(issues).to_string(index=False))
print(report.to_string(index=False))
print(f"\nSaved {OUT_PATH} ({len(df)} rows x {df.shape[1]} cols)")
