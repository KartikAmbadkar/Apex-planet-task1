# Task 1 - Data Immersion & Wrangling (ApexPlanet Sales Dataset)

Cleaning and preparing a 1,000-order retail sales dataset (12 columns) for analysis.

## Repository contents
| File | Purpose |
|---|---|
| `data/ApexPlanet_DataAnalytics_Dataset.xlsx` | Raw input |
| `data_dictionary.csv` | Meaning, type and business relevance of every column |
| `clean_data.py` | Reproducible cleaning script (Python / pandas) |
| `outputs/cleaned_sales_data.csv` | Final analysis-ready dataset (1,000 rows x 27 cols) |
| `outputs/issues_log.csv` | Every issue found and the action taken |
| `outputs/quality_report.csv` | Before / after metrics |

Run: `pip install pandas openpyxl && python clean_data.py`

## Data quality findings
| Issue | Rows | Action |
|---|---|---|
| Duplicate Order_ID (ORD100050 appeared 9 times with different orders) | 8 | IDs restored from the sequential pattern (rows 118, 238 ... 958 broke it); flagged in `Order_ID_Corrected` |
| Missing Age | 20 | Left null, not imputed; `Age_Missing` flag; Age_Group = Unknown |
| Missing City | 13 | Filled with `Unknown` |
| High-value orders (Total_Sales > ~438.7k, IQR rule) | 19 | Kept as valid bulk orders; flagged `Sales_Outlier` |
| Unit_Price < 1,000 for items like laptops/mobiles | 16 | Kept; flagged `Low_Price_Flag` for business review |
| Total_Sales vs Quantity x Unit_Price | 0 mismatches | Verified |
| Whitespace / casing / date format issues | 0 | Checked; script handles them defensively |
| Customer_ID linked to several names/ages | 52 / 50 IDs | Not changed (no master record) - documented limitation |

Before / after: missing cells 33 -> 20 (remaining are intentional Age nulls), duplicate IDs 8 -> 0, columns 12 -> 27.

## Transformations / feature engineering
Date parts (year, month, quarter, weekday, weekend), `Age_Group`, `State` and `Region` (from City), `Order_Size` (from Quantity), `Price_Band` (from Unit_Price), plus audit flags. The dataset has no date of birth, so Age_Group replaces a DOB-derived age.

## Assumptions and limitations
- The ID fix assumes IDs were meant to be sequential (ORD100002 onward); confirm with the data owner.
- Customer_ID/Name/Age are not consistent across orders, so customer-level analysis should use Customer_ID with caution.
- Prices look uniformly random across products (e.g. rice at 49k), which suggests synthetic data.
