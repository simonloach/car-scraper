"""Reporting: static HTML dashboard + alert message formatting.

Pure-stdlib (json/pathlib/datetime/html) so it has no heavy dependencies and
can run anywhere the data files live. Two public helpers:

- ``build_static_report`` writes a self-contained ``index.html`` (Plotly via
  CDN, data baked inline) that the daily pipeline commits and GitHub Pages
  serves. It pre-computes the insightful bits in Python: a per-listing "deal
  score" (price vs an expected price from mileage + year), a reconstructed
  median-asking-price-over-time series, and per-model KPIs.
- ``format_alert_markdown`` turns a scrape run summary into a GitHub issue body.
"""

import html
import json
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


def _md_escape(s: str) -> str:
    """Escape characters that would break out of a markdown link/text."""
    return (s or "").replace("[", "\\[").replace("]", "\\]").replace("`", "\\`")


def _money(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ") + " zł"
    except (TypeError, ValueError):
        return "—"


def load_targets(targets_file: str = "targets.json") -> Dict[str, str]:
    """Return ``{key: label}`` from targets.json (empty if missing)."""
    path = Path(targets_file)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {t["key"]: t.get("label", t["key"]) for t in data.get("targets", [])}
    except (json.JSONDecodeError, KeyError):
        return {}


def load_models(data_dir: str, targets_file: str = "targets.json") -> List[Dict]:
    """Load every model's listings from ``data_dir``.

    Each item: ``{"key", "label", "listings": [listing, ...]}``.
    """
    labels = load_targets(targets_file)
    base = Path(data_dir)
    models = []
    if not base.exists():
        return models
    for model_dir in sorted(base.iterdir()):
        if (
            not model_dir.is_dir()
            or model_dir.name.startswith(".")
            or model_dir.name == "plots"
        ):
            continue
        data_file = model_dir / f"{model_dir.name}.json"
        if not data_file.exists():
            continue
        try:
            data = json.loads(data_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "listings" in data:
            listings = list(data["listings"].values())
        elif isinstance(data, list):
            listings = data
        else:
            continue
        models.append(
            {
                "key": model_dir.name,
                "label": labels.get(model_dir.name, model_dir.name),
                "listings": listings,
            }
        )
    return models


def _active(listing: Dict) -> bool:
    return listing.get("active", True)


# --- analytics -------------------------------------------------------------


def _solve(matrix: List[List[float]], rhs: List[float]) -> Optional[List[float]]:
    """Solve a small linear system by Gaussian elimination. None if singular."""
    n = len(matrix)
    a = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-9:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        for r in range(n):
            if r == col:
                continue
            factor = a[r][col] / a[col][col]
            for c in range(col, n + 1):
                a[r][c] -= factor * a[col][c]
    return [a[i][n] / a[i][i] for i in range(n)]


def _ols(features: List[List[float]], ys: List[float]) -> Optional[List[float]]:
    """Ordinary least squares with intercept. Returns coefficients or None.

    ``features`` is a list of feature-rows (no intercept column). Solves the
    normal equations (X'X)b = X'y.
    """
    rows = [[1.0] + f for f in features]
    k = len(rows[0])
    if len(rows) < k + 1:  # need more points than parameters
        return None
    xtx = [
        [sum(rows[r][i] * rows[r][j] for r in range(len(rows))) for j in range(k)]
        for i in range(k)
    ]
    xty = [sum(rows[r][i] * ys[r] for r in range(len(rows))) for i in range(k)]
    return _solve(xtx, xty)


def _deal_scores(active: List[Dict]) -> None:
    """Annotate each active listing with predicted_price + deal_pct in place.

    Expected price is modelled from mileage and (when there is enough spread)
    production year. ``deal_pct`` < 0 means cheaper than expected (a deal).
    """
    pts = [
        car
        for car in active
        if isinstance(car.get("current_price"), (int, float))
        and car["current_price"] > 0
        and isinstance(car.get("mileage"), (int, float))
    ]
    if len(pts) < 4:
        return
    years = {car.get("year") for car in pts if car.get("year")}
    use_year = len(years) >= 2 and all(car.get("year") for car in pts)
    feats = [
        [float(car["mileage"]) / 1000.0] + ([float(car["year"])] if use_year else [])
        for car in pts
    ]
    ys = [float(car["current_price"]) for car in pts]
    coef = _ols(feats, ys)
    if not coef:
        return
    for car, f in zip(pts, feats):
        pred = coef[0] + sum(c * x for c, x in zip(coef[1:], f))
        if pred > 0:
            car["predicted_price"] = round(pred)
            car["deal_pct"] = round((car["current_price"] - pred) / pred * 100, 1)


def _readings(listing: Dict) -> List[List]:
    out = []
    for r in listing.get("price_readings") or []:
        if (
            isinstance(r, (list, tuple))
            and len(r) == 2
            and isinstance(r[1], (int, float))
            and r[1] > 0
        ):
            out.append([r[0], r[1]])
    return out


def _market_trend(listings: List[Dict]) -> List[Dict]:
    """Reconstruct median asking price per day across listings while active.

    For each day a listing was live (first_seen..last_seen) its price is the
    most recent reading up to that day. The daily median of those prices is a
    clean "what did the market ask" signal that grows as the pipeline runs.
    """
    spans = []
    overall_lo = overall_hi = None
    for car in listings:
        readings = sorted(_readings(car), key=lambda r: r[0])
        if not readings:
            continue
        try:
            lo = datetime.strptime(car.get("first_seen", ""), "%Y-%m-%d").date()
            hi = datetime.strptime(car.get("last_seen", ""), "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if hi < lo:
            lo, hi = hi, lo
        daily = [(datetime.fromtimestamp(ts).date(), p) for ts, p in readings]
        spans.append((lo, hi, daily))
        overall_lo = lo if overall_lo is None else min(overall_lo, lo)
        overall_hi = hi if overall_hi is None else max(overall_hi, hi)
    if not spans or overall_lo is None:
        return []
    span_days = (overall_hi - overall_lo).days
    step = 7 if span_days > 180 else 1  # weekly buckets for long histories
    series = []
    day = overall_lo
    while day <= overall_hi:
        prices = []
        for lo, hi, daily in spans:
            if lo <= day <= hi:
                price = None
                for d, p in daily:
                    if d <= day:
                        price = p
                    else:
                        break
                if price is None and daily:
                    price = daily[0][1]
                if price:
                    prices.append(price)
        if prices:
            series.append(
                {
                    "date": day.isoformat(),
                    "median": int(statistics.median(prices)),
                    "count": len(prices),
                }
            )
        day += timedelta(days=step)
    return series


def _has_drop(listing: Dict) -> bool:
    r = _readings(listing)
    return len(r) >= 2 and r[-1][1] < r[-2][1]


def _kpis(active: List[Dict]) -> Dict:
    prices = [
        car["current_price"]
        for car in active
        if isinstance(car.get("current_price"), (int, float))
    ]
    cheapest = min(active, key=lambda c: c.get("current_price") or 1e18, default=None)
    miled = [car for car in active if isinstance(car.get("mileage"), (int, float))]
    low_km = min(miled, key=lambda c: c["mileage"], default=None)
    deals = [car for car in active if isinstance(car.get("deal_pct"), (int, float))]
    best_deal = min(deals, key=lambda c: c["deal_pct"], default=None)
    return {
        "count": len(active),
        "median": int(statistics.median(prices)) if prices else 0,
        "cheapest": cheapest,
        "low_km": low_km,
        "best_deal": best_deal
        if best_deal and best_deal.get("deal_pct", 0) < 0
        else None,
        "drops": sum(1 for car in active if _has_drop(car)),
    }


_KEEP = (
    "internal_id",
    "title",
    "version",
    "year",
    "mileage",
    "current_price",
    "engine_power",
    "engine_capacity",
    "fuel_type",
    "gearbox",
    "url",
    "price_readings",
    "predicted_price",
    "deal_pct",
)


def _prep_model(model: Dict) -> Dict:
    """Build the slim, analytics-enriched payload for one model."""
    active = [car for car in model["listings"] if _active(car)]
    _deal_scores(active)
    kpis = _kpis(active)

    def slim(listing):
        return {k: listing.get(k) for k in _KEEP}

    def ref(listing):
        if not listing:
            return None
        return {
            "internal_id": listing.get("internal_id"),
            "title": listing.get("title"),
            "url": listing.get("url"),
            "price": listing.get("current_price"),
            "deal_pct": listing.get("deal_pct"),
            "mileage": listing.get("mileage"),
        }

    return {
        "key": model["key"],
        "label": model["label"],
        "listings": [slim(car) for car in active],
        "trend": _market_trend(model["listings"]),
        "kpis": {
            "count": kpis["count"],
            "median": kpis["median"],
            "drops": kpis["drops"],
            "cheapest": ref(kpis["cheapest"]),
            "low_km": ref(kpis["low_km"]),
            "best_deal": ref(kpis["best_deal"]),
        },
    }


# --- markdown alerts -------------------------------------------------------


def format_alert_markdown(new: List[Dict], drops: List[Dict], date: str) -> str:
    """Format new listings + price drops as a markdown alert body."""
    lines = [f"## 🚗 Car alerts — {date}", ""]
    if new:
        lines.append(f"### 🆕 {len(new)} new listing(s)")
        for item in new:
            label = item.get("_model_label", item.get("model", ""))
            title = _md_escape(item.get("title", "Listing"))
            url = item.get("url", "")
            bits = []
            if item.get("year"):
                bits.append(str(item["year"]))
            if item.get("mileage") is not None:
                bits.append(f"{int(item['mileage']):,} km".replace(",", " "))
            if item.get("engine_power"):
                bits.append(f"{item['engine_power']} KM")
            if item.get("gearbox"):
                bits.append(item["gearbox"])
            meta = " · ".join(bits)
            price = _money(item.get("current_price") or item.get("price"))
            lines.append(f"- **{label}** — [{title}]({url}) — {meta} — **{price}**")
        lines.append("")
    if drops:
        lines.append(f"### 📉 {len(drops)} price drop(s)")
        for d in drops:
            item = d["listing"]
            label = item.get("_model_label", item.get("model", ""))
            title = _md_escape(item.get("title", "Listing"))
            url = item.get("url", "")
            old, new_p = d["old_price"], d["new_price"]
            pct = (new_p - old) / old * 100 if old else 0
            lines.append(
                f"- **{label}** — [{title}]({url}) — "
                f"{_money(old)} → **{_money(new_p)}** ({pct:+.1f}%)"
            )
        lines.append("")
    if not new and not drops:
        lines.append("_No new listings or price drops._")
    return "\n".join(lines)


# --- static HTML -----------------------------------------------------------

_TEMPLATE_PATH = Path(__file__).with_name("report_template.html")


def build_static_report(
    data_dir: str = "data",
    out_path: str = "plots/index.html",
    targets_file: str = "targets.json",
    generated: str = "",
) -> str:
    """Write a self-contained HTML dashboard. Returns the output path."""
    models = [_prep_model(m) for m in load_models(data_dir, targets_file)]
    total_active = sum(m["kpis"]["count"] for m in models)
    total_drops = sum(m["kpis"]["drops"] for m in models)
    global_data = {
        "generated": generated or "now",
        "models": len(models),
        "active": total_active,
        "drops": total_drops,
    }
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    out_html = (
        template.replace("__GENERATED__", html.escape(generated or "now"))
        .replace("__GLOBAL_JSON__", json.dumps(global_data, ensure_ascii=False))
        .replace("__MODELS_JSON__", json.dumps(models, ensure_ascii=False, default=str))
    )
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(out_html, encoding="utf-8")
    return str(out)


def _selfcheck() -> None:
    """Assert-based check of the alert + analytics logic."""
    md = format_alert_markdown(
        new=[
            {
                "_model_label": "Supra",
                "title": "Toyota Supra",
                "url": "http://x",
                "year": 2022,
                "mileage": 9200,
                "engine_power": 340,
                "gearbox": "manual",
                "current_price": 240000,
            }
        ],
        drops=[
            {
                "listing": {
                    "_model_label": "LC",
                    "title": "Lexus LC",
                    "url": "http://y",
                },
                "old_price": 400000,
                "new_price": 380000,
            }
        ],
        date="2026-06-19",
    )
    assert "1 new listing" in md and "240 000 zł" in md and "-5.0%" in md, md
    assert _md_escape("Car](evil)") == "Car\\](evil)"

    # OLS recovers a known linear relation: price = 100000 - 2*mileage(k) + ...
    coef = _ols([[10.0], [20.0], [30.0], [40.0]], [80.0, 60.0, 40.0, 20.0])
    assert coef and abs(coef[1] - (-2.0)) < 1e-6, coef

    # Deal scoring flags the underpriced car as the best deal.
    active = [
        {"current_price": 300000, "mileage": 20000, "year": 2019},
        {"current_price": 280000, "mileage": 40000, "year": 2019},
        {"current_price": 260000, "mileage": 60000, "year": 2019},
        {"current_price": 200000, "mileage": 25000, "year": 2019},  # clearly cheap
        {"current_price": 240000, "mileage": 80000, "year": 2019},
    ]
    _deal_scores(active)
    assert active[3]["deal_pct"] < 0, active[3]
    print("reporting self-check OK")


if __name__ == "__main__":
    _selfcheck()
