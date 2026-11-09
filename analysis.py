"""Morningside Heights street trees, NYC 2015 Street Tree Census (uvpi-gqnh).

Run: python3 analysis.py   (downloads to ./data on first run, writes the chart next to this file)
"""
import os
import urllib.parse
import urllib.request

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
RAW_CSV = os.path.join(DATA_DIR, "morningside_heights_raw.csv")
CHART_PNG = os.path.join(HERE, "morningside_top_species.png")
API = "https://data.cityofnewyork.us/resource/uvpi-gqnh.csv"
NTA_CODE = "MN09"  # NTA "Morningside Heights"
SOUTH_OF_110TH_LAT = 40.800  # conservative: below this is south of W 110th St at every longitude


def load_raw():
    if not os.path.exists(RAW_CSV):
        os.makedirs(DATA_DIR, exist_ok=True)
        query = urllib.parse.urlencode(
            {"$where": f"nta='{NTA_CODE}'", "$limit": 50000, "$order": "tree_id"}
        )
        urllib.request.urlretrieve(f"{API}?{query}", RAW_CSV)
    # "None" is a real category in steward/guards, so don't let pandas turn it into NaN.
    return pd.read_csv(RAW_CSV, keep_default_na=False, na_values=[""], low_memory=False)


def quality_report(df):
    alive = df["status"] == "Alive"
    print(f"Rows (NTA {NTA_CODE} Morningside Heights): {len(df):,}")
    print(f"Status: {df['status'].value_counts().to_dict()}")
    print(f"Missing health/species: {df['health'].isna().sum()} rows "
          f"(all non-living: {(~alive & df['health'].isna()).sum()}; "
          f"living with missing health: {(alive & df['health'].isna()).sum()})")
    print(f"Duplicate tree_id: {df['tree_id'].duplicated().sum()}; "
          f"duplicate lat/lon pairs: {df.duplicated(['latitude', 'longitude']).sum()}")
    print(f"Stumps recorded with dbh=0: {((df['status'] == 'Stump') & (df['tree_dbh'] == 0)).sum()}")
    print(f"Max dbh: {df['tree_dbh'].max()} in")
    cp = df["zip_city"] == "Central Park"
    print(f"Rows with zipcode 83 / zip_city 'Central Park': {cp.sum()} "
          f"(all on {', '.join(sorted(df.loc[cp, 'address'].str.extract(r'(CENTRAL PARK WEST)')[0].dropna().unique()))})")
    south = df["latitude"] < SOUTH_OF_110TH_LAT
    print(f"Rows south of ~110th St (lat < {SOUTH_OF_110TH_LAT}): {south.sum()} "
          f"(min lat {df['latitude'].min():.4f}, i.e. W 96th-97th St)")
    return cp, south


def species_and_health(df):
    alive = df[df["status"] == "Alive"]
    top = alive["spc_common"].value_counts().head(5)
    good_share = (alive["health"] == "Good").mean()
    return alive, top, good_share


def make_chart(alive, top, path):
    surface, ink, ink2, muted, grid, bar = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#2a78d6"
    plt.rcParams["font.family"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

    names = list(top.index)[::-1]
    counts = list(top.values)[::-1]
    good = [(alive.loc[alive["spc_common"] == n, "health"] == "Good").mean() for n in names]

    fig, ax = plt.subplots(figsize=(8.5, 4.2), dpi=200)
    fig.patch.set_facecolor(surface)
    ax.set_facecolor(surface)

    h, xmax = 0.5, 580
    ax.barh(range(len(counts)), counts, height=h, color=bar, zorder=3)

    for y, (c, g) in enumerate(zip(counts, good)):
        ax.text(c + 6, y, f"{c}", va="center", ha="left", fontsize=11, color=ink, fontweight="bold")
        ax.text(c + 6 + 36, y, f"{g:.0%} in Good health", va="center", ha="left", fontsize=9.5, color=ink2)

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels([n[0].upper() + n[1:] for n in names], fontsize=11, color=ink)
    ax.set_xlim(0, xmax)
    ax.set_xticks([0, 100, 200, 300, 400])
    ax.tick_params(axis="x", colors=muted, labelsize=9, length=0)
    ax.tick_params(axis="y", length=0, pad=8)
    ax.xaxis.grid(True, color=grid, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.set_xlabel("Living street trees", fontsize=9.5, color=ink2, labelpad=8)

    total = len(alive)
    share = top.sum() / total
    fig.text(0.04, 0.95, "Honeylocust and ginkgo lead Morningside Heights' street trees",
             fontsize=14, fontweight="bold", color=ink, ha="left", va="top")
    fig.text(0.04, 0.885, f"Top 5 species = {share:.0%} of {total:,} living trees. NYC 2015 Street Tree Census, NTA Morningside Heights.",
             fontsize=9.5, color=ink2, ha="left", va="top")
    fig.subplots_adjust(left=0.2, right=0.97, top=0.78, bottom=0.16)
    fig.savefig(path, facecolor=surface)
    plt.close(fig)


def main():
    df = load_raw()
    cp, south = quality_report(df)

    alive, top, good_share = species_and_health(df)
    print("\nTop 5 species (living trees):")
    for name, n in top.items():
        print(f"  {name}: {n} ({n / len(alive):.1%})")
    print(f"Good health: {good_share:.1%} of living trees "
          f"({(alive['health'] == 'Good').sum():,} of {len(alive):,}); "
          f"{(df['health'] == 'Good').mean():.1%} of all {len(df):,} rows")
    print("Health mix (living):", alive["health"].value_counts(normalize=True).round(3).to_dict())

    print("\nSensitivity (drop Central Park-zip rows / rows south of ~110th St):")
    for label, keep in (("drop CPW-zip", ~cp), ("drop south of 110th", ~south)):
        a, t, g = species_and_health(df[keep])
        print(f"  {label}: n={len(df[keep]):,}, top5={list(t.index)}, Good={g:.1%}")

    make_chart(alive, top, CHART_PNG)
    print(f"\nSaved {CHART_PNG}")


if __name__ == "__main__":
    main()
