"""
Data preparation for "Did pay keep up with prices in Ireland, 2015-2025?"
COMP40610 Information Visualisation - interactive visualisation assignment.

Inputs (CSV downloads from the CSO PxStat API, unchanged):
  CPM23.csv  EU Harmonised Index of Consumer Prices by commodity group, COICOP 2018
             (High Value Dataset; primary data)
             https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/CPM23/CSV/1.0/en
  EHQ03.csv  Earnings and Labour Costs, quarterly (external data, used to measure prices against pay)
             https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/EHQ03/CSV/1.0/en

Outputs (written next to this script, read by dashboard.py):
  monthly.csv    t, name, annual_rate
                 annual rate of change of the HICP, Jan 2015 - Dec 2025, all items + 13 divisions
  quarterly.csv  t, group, name, price_idx, pay_idx, real, weekly_pay
                 Q1 2015 - Q4 2025, one row per quarter and spending category or sector:
                   price_idx   12-month moving-average HICP at the quarter's last month, 2015 Q1 = 100
                   pay_idx     4-quarter moving average of average weekly earnings, 2015 Q1 = 100
                   real        100 * pay_idx / price_idx: what a week's pay buys, 2015 Q1 = 100
                   weekly_pay  average weekly earnings in the quarter, euro (sectors only)
                 Category rows pair the category's prices with all-sector pay;
                 sector rows pair the sector's pay with all-items prices.

Method notes
  * The earnings series is not seasonally adjusted (the seasonally adjusted version of this
    measure is empty), so pay is smoothed with a 4-quarter moving average. Prices use the
    matching 12-month moving-average index, taken at March, June, September and December.
  * 2014 Q2 - Q4 earnings are read only so that the 4-quarter average exists from 2015 Q1.

Usage:  python prepare_data.py [folder containing CPM23.csv and EHQ03.csv]   (default: ./data)
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "data"

START, END = "2015-01-01", "2025-12-01"

CATEGORIES = {
    "CP00": "All items", "CP01": "Food & drinks", "CP02": "Alcohol & tobacco",
    "CP03": "Clothing & footwear", "CP04": "Housing & energy", "CP05": "Furnishings",
    "CP06": "Health", "CP07": "Transport", "CP08": "Information & comms",
    "CP09": "Recreation, sport & culture", "CP10": "Education",
    "CP11": "Restaurants & accommodation", "CP12": "Insurance & finance",
    "CP13": "Personal care & misc.",
}
SECTORS = {  # NACE Rev 2 label in EHQ03 -> short name
    "All NACE economic sectors": "All sectors",
    "Mining and quarrying (B)": "Mining & quarrying",
    "Manufacturing (C)": "Manufacturing",
    "Electricity, water supply and waste management (D,E)": "Electricity & water",
    "Construction (F)": "Construction",
    "Wholesale and retail trade; repair of motor vehicles and motorcycles (G)": "Wholesale & retail",
    "Transportation and storage (H)": "Transport & storage",
    "Accommodation and food service activities (I)": "Accommodation & food",
    "Information and communication (J)": "Information & comms",
    "Financial and insurance activities (K)": "Finance & insurance",
    "Real estate activities (L)": "Real estate",
    "Professional, scientific and technical activities (M)": "Professional & scientific",
    "Administrative and support service activities (N)": "Admin & support",
    "Public administration and defence; compulsory social security (O)": "Public administration",
    "Education (P)": "Education",
    "Human health and social work activities (Q)": "Health & social work",
    "Arts, entertainment and recreation (R)": "Arts & recreation",
    "Other service activities (S)": "Other services",
}


def rebase(values, keys):
    """Index each series in `values` (grouped by `keys`) to its first value = 100."""
    return values / values.groupby(keys).transform("first") * 100


# ------------------------------------------------------------------ prices (CPM23)
hicp = pd.read_csv(RAW / "CPM23.csv", encoding="utf-8-sig")
hicp = hicp[hicp["C04624V05409"].isin(CATEGORIES)].assign(
    name=lambda d: d["C04624V05409"].map(CATEGORIES),
    t=lambda d: pd.to_datetime(d["Month"], format="%Y %B"),
)
hicp = hicp[hicp.t.between(START, END)]

monthly = (hicp[hicp["Statistic Label"] == "Annual rate of change in HICP"]
           .rename(columns={"VALUE": "annual_rate"})[["t", "name", "annual_rate"]]
           .sort_values(["name", "t"]))

prices = hicp[(hicp["Statistic Label"] == "Moving 12 months average index in HICP")
              & hicp.t.dt.month.isin([3, 6, 9, 12])].copy()
prices["t"] = prices.t.dt.to_period("Q").dt.start_time            # label each quarter by its first day
prices = prices.sort_values(["name", "t"])
prices["price_idx"] = rebase(prices.VALUE, prices.name)

# ------------------------------------------------------------------ pay (EHQ03)
ehq = pd.read_csv(RAW / "EHQ03.csv", encoding="utf-8-sig")
pay = ehq[(ehq["Statistic Label"] == "Average weekly earnings excluding irregular earnings")
          & (ehq["Type of Employee"] == "All employees")
          & ehq["Economic Sector NACE Rev 2"].isin(SECTORS)
          & ehq.Quarter.between("2014Q2", "2025Q4")].assign(
    name=lambda d: d["Economic Sector NACE Rev 2"].map(SECTORS),
    t=lambda d: pd.PeriodIndex(d.Quarter, freq="Q").start_time,
).rename(columns={"VALUE": "weekly_pay"}).sort_values(["name", "t"])
pay["pay_4q"] = pay.groupby("name").weekly_pay.transform(lambda s: s.rolling(4).mean())
pay = pay[pay.t >= START].copy()
pay["pay_idx"] = rebase(pay.pay_4q, pay.name)

# ------------------------------------------------------------------ real pay
all_pay = pay.loc[pay.name == "All sectors", ["t", "pay_idx"]]
all_prices = prices.loc[prices.name == "All items", ["t", "price_idx"]]
categories = prices[["t", "name", "price_idx"]].merge(all_pay, on="t").assign(group="category")
sectors = pay[["t", "name", "pay_idx", "weekly_pay"]].merge(all_prices, on="t").assign(group="sector")
quarterly = pd.concat([categories, sectors], ignore_index=True)
quarterly["real"] = 100 * quarterly.pay_idx / quarterly.price_idx
quarterly = quarterly[["t", "group", "name", "price_idx", "pay_idx", "real", "weekly_pay"]]

# ------------------------------------------------------------------ checks and output
n_months, n_quarters = 132, 44
assert len(monthly) == len(CATEGORIES) * n_months and monthly.annual_rate.notna().all()
assert len(categories) == len(CATEGORIES) * n_quarters and len(sectors) == len(SECTORS) * n_quarters
assert quarterly[["price_idx", "pay_idx", "real"]].notna().all().all()

for df, file in ((monthly, "monthly.csv"), (quarterly, "quarterly.csv")):
    df.assign(t=df.t.dt.strftime("%Y-%m-%d")).round(3).to_csv(HERE / file, index=False)
print(f"monthly.csv {monthly.shape}, quarterly.csv {quarterly.shape}")
