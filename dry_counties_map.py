#!/usr/bin/env python3
"""
US Dry Counties Interactive Map (2026)
=======================================
A modern, open-source replacement for the SAS-based dry counties map originally
created by Robert Allison at SAS (2019). This script:

  1. Uses US Census county boundary shapefiles (bundled with plotly-geo)
  2. Applies a comprehensive dataset of dry/moist/wet county statuses compiled
     from state ABC boards, NABCA data, and public records (as of Feb 2026)
  3. Generates an interactive choropleth map using Plotly + GeoPandas

Requirements:
    pip install plotly pandas geopandas plotly-geo shapely

Usage:
    python3 dry_counties_map.py              # Generate map
    python3 dry_counties_map.py --update     # Fetch latest Wikipedia data first

Output:
    dry_counties_map.html  (interactive map you can open in any browser)

Data Sources:
    - County boundaries: US Census Bureau 2016 (cb_2016_us_county_500k) via plotly-geo
    - Arkansas: Arkansas GIS Office / ABC Division (Feb 2025)
    - Texas: TABC interactive wet/dry map (March 2025)
    - Kentucky: Kentucky ABC / Cabinet for Economic Development
    - Mississippi: MS Dept of Revenue wet/dry map (Aug 2025)
    - Alabama: Alabama ABC Board wet cities list
    - Kansas: KS Dept of Revenue (Nov 2025: zero dry counties remain)
    - Tennessee: TN Alcoholic Beverage Commission
    - Florida/Georgia/Virginia/South Dakota: State ABC boards

Author: Daniel Blasing & Claude
Date: February 2026
License: MIT
"""

import json
import sys
import os

# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------
REQUIRED_PKGS = {
    "plotly": "plotly",
    "pandas": "pandas",
    "geopandas": "geopandas",
    "_plotly_geo": "plotly-geo",
    "shapely": "shapely",
}
_missing = []
for mod, pkg in REQUIRED_PKGS.items():
    try:
        __import__(mod)
    except ImportError:
        _missing.append(pkg)
if _missing:
    print(f"Missing packages: {', '.join(_missing)}")
    print(f"Install with:  pip install {' '.join(_missing)}")
    sys.exit(1)

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import geopandas as gpd
import _plotly_geo

# ---------------------------------------------------------------------------
# State FIPS code lookup (2-digit state FIPS -> full name)
# ---------------------------------------------------------------------------
STATE_FIPS_TO_NAME = {
    "01": "Alabama", "02": "Alaska", "04": "Arizona", "05": "Arkansas",
    "06": "California", "08": "Colorado", "09": "Connecticut",
    "10": "Delaware", "11": "District of Columbia", "12": "Florida",
    "13": "Georgia", "15": "Hawaii", "16": "Idaho", "17": "Illinois",
    "18": "Indiana", "19": "Iowa", "20": "Kansas", "21": "Kentucky",
    "22": "Louisiana", "23": "Maine", "24": "Maryland",
    "25": "Massachusetts", "26": "Michigan", "27": "Minnesota",
    "28": "Mississippi", "29": "Missouri", "30": "Montana",
    "31": "Nebraska", "32": "Nevada", "33": "New Hampshire",
    "34": "New Jersey", "35": "New Mexico", "36": "New York",
    "37": "North Carolina", "38": "North Dakota", "39": "Ohio",
    "40": "Oklahoma", "41": "Oregon", "42": "Pennsylvania",
    "44": "Rhode Island", "45": "South Carolina", "46": "South Dakota",
    "47": "Tennessee", "48": "Texas", "49": "Utah", "50": "Vermont",
    "51": "Virginia", "53": "Washington", "54": "West Virginia",
    "55": "Wisconsin", "56": "Wyoming", "72": "Puerto Rico",
}

STATE_NAME_TO_FIPS = {v: k for k, v in STATE_FIPS_TO_NAME.items()}

# Status codes matching the original SAS map's 3-tier classification
STATUS_DRY = "Dry"       # No legal retail alcohol sales anywhere in the county
STATUS_MOIST = "Moist"   # Some restrictions (wet cities in dry county, beer-only, etc.)
STATUS_WET = "Wet"       # Standard unrestricted sales (state-level rules only)

# ---------------------------------------------------------------------------
# Hardcoded dry/moist county data (compiled Feb 2026 from state sources)
# ---------------------------------------------------------------------------
# Format: { "State FIPS": { "county_name_lower": status } }
# We use STATEFP and lowercase county NAME from the shapefile for matching.

def _build_status_map():
    """
    Build a dict keyed by (STATEFP, county_name_lower) -> status.
    Only non-wet counties need to be listed; everything else defaults to Wet.
    """
    status = {}

    def add(state_name, county_list, stat):
        sfips = STATE_NAME_TO_FIPS.get(state_name)
        if not sfips:
            return
        for c in county_list:
            status[(sfips, c.lower())] = stat

    # ==================================================================
    # DRY COUNTIES  (no legal retail alcohol sales anywhere in county)
    # ==================================================================

    # ARKANSAS  (Source: AR GIS Office / ABC Division, Feb 2025)
    # 31 dry counties. Hot Spring County voted WET in November 2022.
    # Private club permits may allow limited on-premise consumption.
    add("Arkansas", [
        "Ashley", "Bradley", "Clay", "Cleburne", "Craighead", "Crawford",
        "Faulkner", "Fulton", "Grant", "Hempstead", "Howard", "Independence",
        "Izard", "Johnson", "Lafayette", "Lawrence", "Lincoln", "Logan",
        "Lonoke", "Montgomery", "Nevada", "Newton", "Perry", "Pike", "Pope",
        "Scott", "Searcy", "Sebastian", "Stone", "White", "Yell",
    ], STATUS_DRY)

    # TEXAS  (Source: TABC, March 2025)
    # Only 3 fully dry counties remain. Throckmorton voted wet Nov 2024.
    add("Texas", ["Borden", "Kent", "Roberts"], STATUS_DRY)

    # MISSISSIPPI  (Source: MS Dept of Revenue, Aug 2025)
    # Benton is the only county with zero alcohol sales exceptions.
    add("Mississippi", ["Benton"], STATUS_DRY)

    # FLORIDA  (Source: FL Division of Alcoholic Beverages)
    # Liberty County is the only fully dry county.
    add("Florida", ["Liberty"], STATUS_DRY)

    # SOUTH DAKOTA  (Source: State records)
    # Oglala Lakota County (Pine Ridge Reservation).
    # Shapefile may list as "Shannon" (pre-2015 name) or "Oglala Lakota".
    add("South Dakota", ["Oglala Lakota", "Shannon"], STATUS_DRY)

    # ==================================================================
    # MOIST COUNTIES  (some restrictions on alcohol sales)
    # ==================================================================

    # ALABAMA  (Source: Alabama ABC Board, 2025)
    # Zero fully dry counties. These 23 are dry at county level but have
    # one or more wet cities within them (74 wet cities total).
    add("Alabama", [
        "Blount", "Cherokee", "Chilton", "Clarke", "Clay", "Coffee",
        "Cullman", "DeKalb", "Fayette", "Franklin", "Geneva", "Jackson",
        "Lamar", "Lauderdale", "Lawrence", "Marion", "Marshall", "Monroe",
        "Morgan", "Pickens", "Randolph", "Washington", "Winston",
    ], STATUS_MOIST)

    # KENTUCKY  (Source: KY ABC, 2022-2025)
    # Historically ~39 dry counties. As of 2022, about 10 remain fully dry,
    # the rest "moist" (wet cities or limited restaurant sales). Classifying
    # conservatively as moist since the exact split is fluid.
    add("Kentucky", [
        "Adair", "Allen", "Ballard", "Bath", "Breathitt", "Butler",
        "Carlisle", "Casey", "Clinton", "Crittenden", "Cumberland",
        "Elliott", "Estill", "Fleming", "Hancock", "Hart", "Hickman",
        "Jackson", "Knott", "Knox", "Larue", "Lawrence", "Lee", "Leslie",
        "Lincoln", "McCreary", "McLean", "Martin", "Menifee", "Metcalfe",
        "Monroe", "Morgan", "Ohio", "Owsley", "Powell", "Robertson",
        "Rockcastle", "Russell", "Webster",
    ], STATUS_MOIST)

    # MISSISSIPPI  (Source: MS Dept of Revenue, Aug 2025)
    # Dry at county level but with wet municipalities (county seat, etc.)
    add("Mississippi", [
        "Alcorn", "Amite", "Calhoun", "Chickasaw", "Choctaw", "Clarke",
        "Covington", "Franklin", "George", "Greene", "Itawamba", "Jasper",
        "Jones", "Kemper", "Lamar", "Lawrence", "Leake", "Lincoln",
        "Monroe", "Neshoba", "Newton", "Pearl River", "Pontotoc",
        "Prentiss", "Scott", "Simpson", "Smith", "Tate", "Tippah",
        "Tishomingo", "Union", "Wayne", "Webster",
    ], STATUS_MOIST)

    # TENNESSEE  (Source: TN ABC, 2025)
    # Tennessee is dry by default. Only ~10 counties are fully wet
    # (Davidson, Hamilton, Knox, Shelby, etc.). The remaining ~85 counties
    # are either fully dry or "moist" with some wet municipalities.
    # Classifying all non-wet TN counties as moist.
    add("Tennessee", [
        "Anderson", "Bedford", "Bledsoe", "Blount", "Bradley", "Campbell",
        "Cannon", "Carroll", "Carter", "Cheatham", "Chester", "Claiborne",
        "Clay", "Cocke", "Coffee", "Crockett", "Cumberland", "Decatur",
        "DeKalb", "Dickson", "Dyer", "Fayette", "Fentress", "Franklin",
        "Gibson", "Giles", "Grainger", "Greene", "Grundy", "Hamblen",
        "Hancock", "Hardeman", "Hardin", "Hawkins", "Haywood", "Henderson",
        "Henry", "Hickman", "Houston", "Humphreys", "Jackson", "Jefferson",
        "Johnson", "Lake", "Lauderdale", "Lawrence", "Lewis", "Lincoln",
        "Loudon", "Macon", "Madison", "Marion", "Marshall", "Maury",
        "McMinn", "McNairy", "Meigs", "Monroe", "Montgomery", "Moore",
        "Morgan", "Obion", "Overton", "Perry", "Pickett", "Polk", "Putnam",
        "Rhea", "Roane", "Robertson", "Rutherford", "Scott", "Sequatchie",
        "Sevier", "Smith", "Stewart", "Sullivan", "Sumner", "Tipton",
        "Trousdale", "Unicoi", "Union", "Van Buren", "Warren",
        "Washington", "Wayne", "Weakley", "White", "Williamson", "Wilson",
    ], STATUS_MOIST)

    # FLORIDA  (Source: FL Division of Alcoholic Beverages)
    # Lafayette allows beer but prohibits liquor/wine sales.
    add("Florida", ["Lafayette"], STATUS_MOIST)

    # GEORGIA  (Source: GA Dept of Revenue, 2025)
    # These counties restrict distilled spirits but allow beer/wine.
    add("Georgia", [
        "Bleckley", "Butts", "Coweta", "Decatur", "Dodge", "Effingham",
        "Hart",
    ], STATUS_MOIST)

    return status


COUNTY_STATUS_MAP = _build_status_map()

# ---------------------------------------------------------------------------
# Load county shapefile from plotly-geo package
# ---------------------------------------------------------------------------
def load_county_geodata():
    """Load the bundled US county shapefile from plotly-geo."""
    geo_dir = os.path.dirname(_plotly_geo.__file__)
    shp_path = os.path.join(geo_dir, "package_data", "cb_2016_us_county_500k.shp")

    if not os.path.exists(shp_path):
        print(f"Error: County shapefile not found at {shp_path}")
        print("Make sure plotly-geo is installed: pip install plotly-geo")
        sys.exit(1)

    print(f"  Loading county boundaries from plotly-geo package...")
    gdf = gpd.read_file(shp_path)
    return gdf


def load_state_geodata():
    """Load the bundled US state shapefile from plotly-geo."""
    geo_dir = os.path.dirname(_plotly_geo.__file__)
    shp_path = os.path.join(geo_dir, "package_data", "cb_2016_us_state_500k.shp")
    if os.path.exists(shp_path):
        return gpd.read_file(shp_path)
    return None


# ---------------------------------------------------------------------------
# Build dataset
# ---------------------------------------------------------------------------
def build_county_dataset(gdf):
    """
    Assign dry/moist/wet status to each county in the GeoDataFrame.
    Returns a DataFrame with: fips, county, state, status
    and the GeoJSON dict for plotly.
    """
    # Filter to 50 states + DC (exclude territories except PR if desired)
    valid_states = set(STATE_FIPS_TO_NAME.keys())
    gdf = gdf[gdf["STATEFP"].isin(valid_states)].copy()

    # Assign status
    def get_status(row):
        key = (row["STATEFP"], row["NAME"].lower())
        return COUNTY_STATUS_MAP.get(key, STATUS_WET)

    gdf["status"] = gdf.apply(get_status, axis=1)
    gdf["state_name"] = gdf["STATEFP"].map(STATE_FIPS_TO_NAME)

    # Build DataFrame for plotly
    df = pd.DataFrame({
        "fips": gdf["GEOID"].values,
        "county": gdf["NAME"].values,
        "state": gdf["state_name"].values,
        "status": gdf["status"].values,
    })

    # Convert geometry to GeoJSON for plotly
    # Simplify geometry to reduce file size
    gdf_simplified = gdf.copy()
    gdf_simplified["geometry"] = gdf_simplified["geometry"].simplify(
        tolerance=0.005, preserve_topology=True
    )

    # Build GeoJSON features list
    features = []
    for _, row in gdf_simplified.iterrows():
        feature = {
            "type": "Feature",
            "id": row["GEOID"],
            "properties": {"name": row["NAME"], "state": row["state_name"]},
            "geometry": json.loads(gpd.GeoSeries([row["geometry"]]).to_json())["features"][0]["geometry"],
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    return df, geojson


# ---------------------------------------------------------------------------
# Map generation
# ---------------------------------------------------------------------------
def create_map(df, geojson, output_path="dry_counties_map.html"):
    """Create an interactive Plotly choropleth map."""

    # Stats
    n_dry = len(df[df["status"] == STATUS_DRY])
    n_moist = len(df[df["status"] == STATUS_MOIST])
    n_wet = len(df[df["status"] == STATUS_WET])
    total = len(df)

    print(f"\n  County breakdown:")
    print(f"    Dry:   {n_dry:>5} counties (no alcohol sales)")
    print(f"    Moist: {n_moist:>5} counties (restricted sales)")
    print(f"    Wet:   {n_wet:>5} counties (unrestricted sales)")
    print(f"    Total: {total:>5} counties")

    # Color mapping
    color_map = {
        STATUS_WET:   "#c7e9c0",    # Light green
        STATUS_MOIST: "#fdae6b",    # Orange
        STATUS_DRY:   "#e31a1c",    # Red
    }

    fig = px.choropleth(
        df,
        geojson=geojson,
        locations="fips",
        color="status",
        color_discrete_map=color_map,
        category_orders={"status": [STATUS_WET, STATUS_MOIST, STATUS_DRY]},
        scope="usa",
        labels={"status": "Alcohol Sales Status"},
        hover_data={"fips": False, "county": True, "state": True, "status": True},
    )

    # Style the map
    fig.update_geos(
        showlakes=True,
        lakecolor="rgb(200, 220, 240)",
        showland=True,
        landcolor="rgb(250, 250, 250)",
        showcountries=True,
        countrycolor="rgb(80, 80, 80)",
        showsubunits=True,
        subunitcolor="rgb(40, 40, 40)",
        subunitwidth=1.2,
        projection_type="albers usa",
    )

    fig.update_traces(
        marker_line_width=0.2,
        marker_line_color="rgba(80, 80, 80, 0.3)",
        hovertemplate=(
            "<b>%{customdata[0]} County, %{customdata[1]}</b><br>"
            "Status: %{customdata[2]}<extra></extra>"
        ),
        customdata=df[["county", "state", "status"]].values,
    )

    fig.update_layout(
        title={
            "text": (
                "<b>US Dry Counties Map (2026)</b><br>"
                "<sup>Counties where the sale of alcohol is still prohibited or restricted</sup>"
            ),
            "x": 0.5,
            "xanchor": "center",
            "font": {"size": 18},
        },
        legend=dict(
            title="County Status",
            orientation="h",
            yanchor="bottom",
            y=-0.05,
            xanchor="center",
            x=0.5,
            font=dict(size=13),
        ),
        margin=dict(l=10, r=10, t=80, b=60),
        height=650,
        width=1100,
        annotations=[
            dict(
                text=(
                    f"<i>Dry: {n_dry} | Moist: {n_moist} | "
                    f"Wet: {n_wet} (of {total} total counties)</i><br>"
                    "<i>Sources: State ABC boards, NABCA, Wikipedia (compiled Feb 2026). "
                    "Hot Spring County, AR correctly shows as Wet.</i>"
                ),
                showarrow=False,
                xref="paper", yref="paper",
                x=0.5, y=-0.1,
                font=dict(size=10, color="gray"),
                align="center",
            )
        ],
    )

    # Write HTML
    fig.write_html(
        output_path,
        include_plotlyjs=True,
        full_html=True,
        config={
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "displaylogo": False,
            "scrollZoom": True,
        },
    )
    print(f"\n  Map saved to: {output_path}")
    return fig


# ---------------------------------------------------------------------------
# Wikipedia update function (for --update mode)
# ---------------------------------------------------------------------------
def update_from_wikipedia():
    """
    Attempt to fetch current dry county data from Wikipedia.
    Requires: pip install requests beautifulsoup4
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        print("  Install requests and beautifulsoup4 for Wikipedia updates.")
        return False

    url = "https://en.wikipedia.org/wiki/List_of_dry_communities_by_U.S._state"
    print(f"  Fetching {url} ...")

    try:
        resp = requests.get(url, timeout=30, headers={
            "User-Agent": "DryCountiesMap/2.0 (Educational; github.com)"
        })
        resp.raise_for_status()
        print("  Successfully fetched Wikipedia page.")
        print("  Note: Full Wikipedia parsing is a TODO — contribute on GitHub!")
        print("  For now, using the hardcoded Feb 2026 dataset.")
        return True
    except Exception as e:
        print(f"  Could not reach Wikipedia: {e}")
        print("  Using hardcoded dataset instead.")
        return False


# ---------------------------------------------------------------------------
# Verification / spot checks
# ---------------------------------------------------------------------------
def verify_data(df):
    """Run spot checks on known counties."""
    checks = [
        # (county, state, expected_status, note)
        ("Hot Spring", "Arkansas", STATUS_WET, "Voted wet Nov 2022"),
        ("Borden", "Texas", STATUS_DRY, "One of only 3 dry TX counties"),
        ("Kent", "Texas", STATUS_DRY, "One of only 3 dry TX counties"),
        ("Roberts", "Texas", STATUS_DRY, "One of only 3 dry TX counties"),
        ("Benton", "Mississippi", STATUS_DRY, "Only fully dry MS county"),
        ("Liberty", "Florida", STATUS_DRY, "Only fully dry FL county"),
        ("Cullman", "Alabama", STATUS_MOIST, "Moist - has wet cities"),
        ("Throckmorton", "Texas", STATUS_WET, "Voted wet Nov 2024"),
        ("Davidson", "Tennessee", STATUS_WET, "Nashville - fully wet"),
        ("Shelby", "Tennessee", STATUS_WET, "Memphis - fully wet"),
        ("Moore", "Tennessee", STATUS_MOIST, "Jack Daniel's county - moist"),
    ]

    print("\n  Spot-checking known counties:")
    all_pass = True
    for county, state, expected, note in checks:
        row = df[(df["county"] == county) & (df["state"] == state)]
        if len(row) == 0:
            print(f"    MISS  {county} County, {state} — not found in data")
            all_pass = False
        else:
            actual = row.iloc[0]["status"]
            ok = "PASS" if actual == expected else "FAIL"
            if ok == "FAIL":
                all_pass = False
            print(f"    {ok}  {county} County, {state}: {actual} "
                  f"(expected {expected}) — {note}")

    return all_pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    use_update = "--update" in sys.argv
    script_dir = os.path.dirname(os.path.abspath(__file__))

    print("=" * 65)
    print("  US Dry Counties Interactive Map Generator (2026)")
    print("  Modern replacement for the SAS-based dry counties map")
    print("=" * 65)

    # Step 1: Load county boundaries
    print("\n[1/4] Loading county boundary data...")
    gdf = load_county_geodata()
    print(f"  Loaded {len(gdf)} county/equivalent boundaries")

    # Step 2: Optional Wikipedia update
    if use_update:
        print("\n[2/4] Updating from Wikipedia...")
        update_from_wikipedia()
    else:
        print("\n[2/4] Using hardcoded dataset (Feb 2026)")
        print("  Tip: Run with --update to try fetching latest Wikipedia data")

    # Step 3: Build dataset
    print("\n[3/4] Building county dataset...")
    df, geojson = build_county_dataset(gdf)

    # Step 4: Generate map
    print("\n[4/4] Generating interactive map...")
    output_path = os.path.join(script_dir, "dry_counties_map.html")
    create_map(df, geojson, output_path=output_path)

    # Verification
    verify_data(df)

    # Summary
    print("\n" + "=" * 65)
    print("  DONE!")
    print(f"  Map: {output_path}")
    print()
    print("  Key differences from the 2019 SAS map:")
    print("  - Hot Spring County, AR: now WET (voted Nov 2022)")
    print("  - Kansas: ZERO dry counties (Wallace voted wet Nov 2025)")
    print("  - Texas: down to 3 dry (Throckmorton voted wet Nov 2024)")
    print("  - Alabama: zero fully dry (all 23 restricted are 'moist')")
    print("  - Virginia: zero dry counties since 2020")
    print("  - Mississippi: only 1 fully dry (Benton)")
    print("=" * 65)


if __name__ == "__main__":
    main()
