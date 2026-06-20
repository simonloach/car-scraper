"""Interactive car-tracker dashboard (Streamlit).

Standalone on purpose: reads the data/<model>/<model>.json files directly so the
container only needs streamlit + plotly + pandas, with no dependency on the
scraper package. Run locally with `docker compose up` (see docker-compose.yml)
or `streamlit run dashboard/app.py`.
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
TARGETS = Path(os.environ.get("TARGETS_FILE", "targets.json"))


@st.cache_data(ttl=300)
def load_labels() -> dict:
    """Return {key: label} from targets.json (empty if missing/invalid)."""
    if TARGETS.exists():
        try:
            t = json.loads(TARGETS.read_text(encoding="utf-8"))
            return {x["key"]: x.get("label", x["key"]) for x in t.get("targets", [])}
        except (json.JSONDecodeError, KeyError):
            pass
    return {}


@st.cache_data(ttl=300)
def load_model(key: str) -> pd.DataFrame:
    """Load one model's listings into a DataFrame (empty on read error)."""
    f = DATA_DIR / key / f"{key}.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Could not read data for {key}: {exc}")
        return pd.DataFrame()
    if isinstance(data, dict):
        listings = list(data.get("listings", {}).values())
    elif isinstance(data, list):
        listings = data
    else:
        listings = []
    return pd.DataFrame(listings)


def models() -> list:
    """List model keys that have a data file under DATA_DIR."""
    if not DATA_DIR.exists():
        return []
    return sorted(
        d.name
        for d in DATA_DIR.iterdir()
        if d.is_dir() and (d / f"{d.name}.json").exists() and not d.name.startswith(".")
    )


st.set_page_config(page_title="Car Tracker", page_icon="🚗", layout="wide")
st.title("🚗 Car Tracker")

labels = load_labels()
available = models()
if not available:
    st.warning(f"No data found in {DATA_DIR.resolve()}. Run the scraper first.")
    st.stop()

key = st.sidebar.selectbox("Model", available, format_func=lambda k: labels.get(k, k))
active_only = st.sidebar.checkbox("Active listings only", value=True)

df = load_model(key)
if "active" not in df.columns:
    df["active"] = True
if active_only:
    df = df[df["active"] != False]  # noqa: E712 - pandas truthiness

for col in ("year", "mileage", "current_price", "engine_power"):
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

if df.empty:
    st.info("No listings match the current filters.")
    st.stop()

# Optional year filter when the data spans multiple years.
if "year" in df.columns and df["year"].notna().any():
    ylo, yhi = int(df["year"].min()), int(df["year"].max())
    if yhi > ylo:
        lo, hi = st.sidebar.slider("Year", ylo, yhi, (ylo, yhi))
        df = df[df["year"].between(lo, hi)]

st.caption(labels.get(key, key))
c1, c2, c3, c4 = st.columns(4)
prices = df["current_price"].dropna()
c1.metric("Listings", len(df))
c2.metric("Avg price", f"{prices.mean():,.0f} zł" if len(prices) else "—")
c3.metric("Min price", f"{prices.min():,.0f} zł" if len(prices) else "—")
c4.metric("Max price", f"{prices.max():,.0f} zł" if len(prices) else "—")

# Price over time, one line per listing with history.
rows = []
for _, row in df.iterrows():
    for ts, price in row.get("price_readings") or []:
        if price and price > 0:
            rows.append(
                {
                    "id": f"#{row.get('internal_id')}",
                    "title": row.get("title"),
                    "date": datetime.fromtimestamp(ts),
                    "price": price,
                }
            )
left, right = st.columns(2)
if rows:
    hist = pd.DataFrame(rows)
    fig = px.line(
        hist,
        x="date",
        y="price",
        color="id",
        markers=True,
        hover_data=["title"],
        title="Price over time",
    )
    fig.update_layout(yaxis_title="PLN", xaxis_title="")
    left.plotly_chart(fig, use_container_width=True)

if "mileage" in df.columns and df["mileage"].notna().any():
    fig2 = px.scatter(
        df,
        x="mileage",
        y="current_price",
        color="year",
        hover_data=["title", "engine_power", "gearbox"],
        title="Price vs mileage",
        color_continuous_scale="Viridis",
    )
    fig2.update_layout(yaxis_title="PLN", xaxis_title="km")
    right.plotly_chart(fig2, use_container_width=True)

# Table, cheapest first, with clickable links.
cols = [
    c
    for c in [
        "internal_id",
        "title",
        "year",
        "mileage",
        "engine_power",
        "gearbox",
        "version",
        "current_price",
        "url",
    ]
    if c in df.columns
]
table = df[cols].sort_values("current_price", na_position="last")
st.dataframe(
    table,
    use_container_width=True,
    hide_index=True,
    column_config={"url": st.column_config.LinkColumn("link", display_text="open")},
)
