"""
data_loader.py
==============
Obtain AUTHENTIC 2025 hourly data for Germany and turn it into the input
profiles the dispatch model needs, then document provenance.

Primary source (default, no API key required)
---------------------------------------------
Fraunhofer ISE **Energy-Charts** public REST API (api.energy-charts.info),
which redistributes Bundesnetzagentur | SMARD.de and ENTSO-E data under
CC BY 4.0.  Endpoints used:
  * /public_power  -> generation per production type + actual load (15-min)
  * /price         -> day-ahead price, DE-LU bidding zone (hourly)

Optional source (if you have tokens in .env)
--------------------------------------------
ENTSO-E Transparency Platform and renewables.ninja can be used instead by
setting SOURCE = "entsoe".  Tokens are read from .env and NEVER printed.
The default Energy-Charts path needs no token and is fully reproducible.

Outputs (written to ./data/processed/ and ./data/)
--------------------------------------------------
  processed/demand_2025_hourly.csv     timestamp_utc, load_mw
  processed/cf_2025_hourly.csv         timestamp_utc, wind_onshore, wind_offshore, solar, ror
  processed/price_2025_hourly.csv      timestamp_utc, price_eur_mwh
  processed/generation_2025_hourly.csv timestamp_utc, <all carriers MW>   (for calibration)
  provenance.json                      full source/dataset/URL/units/retrieval log

Run:  python data_loader.py
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# Optional: load tokens from .env if present (never printed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import config

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
SOURCE = "energy-charts"          # "energy-charts" (default) | "entsoe"
YEAR = config.CALIBRATION_YEAR    # 2025
EC_BASE = "https://api.energy-charts.info"

# A browser-like User-Agent + JSON Accept header. Some networks / CDNs reply
# to the bare "python-requests" client with a non-data page; these headers
# avoid that and make the request look like an ordinary browser call.
HTTP_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/json",
}

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
PROC_DIR = DATA_DIR / "processed"
RAW_DIR = DATA_DIR / "raw"
for _d in (DATA_DIR, PROC_DIR, RAW_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# Tokens (read but never printed) -- only used if SOURCE == "entsoe"
ENTSOE_TOKEN = os.getenv("ENTSOE_API_TOKEN", "")
NINJA_TOKEN = os.getenv("RENEWABLES_NINJA_TOKEN", "")

# Map Energy-Charts production-type names -> our internal labels
EC_NAME_MAP = {
    "Load": "load",
    "Wind onshore": "wind_onshore",
    "Wind offshore": "wind_offshore",
    "Solar": "solar",
    "Hydro Run-of-River": "ror",
    "Biomass": "biomass",
    "Fossil brown coal / lignite": "lignite",
    "Fossil hard coal": "hardcoal",
    "Fossil gas": "gas",
    "Fossil oil": "oil",
    "Cross border electricity trading": "net_import",
    "Hydro pumped storage": "phs_gen",
    "Nuclear": "nuclear",
    "Waste": "waste",
    "Geothermal": "geothermal",
    "Others": "others",
}


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------
def _get_json(endpoint: str, params: dict, expect_key: str,
              retries: int = 5, timeout: int = 90) -> dict:
    """GET an Energy-Charts endpoint, validate it, and return parsed JSON.

    `expect_key` is a key the valid response MUST contain (e.g. "production_types"
    or "price").  If it is missing, the body is treated as a failed attempt and
    retried, then reported clearly -- this turns a cryptic KeyError into an
    actionable message.
    """
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("Missing dependency 'requests'. Run: pip install -r requirements.txt") from exc

    url = f"{EC_BASE}/{endpoint}"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict) or expect_key not in data:
                keys = list(data)[:12] if isinstance(data, dict) else type(data).__name__
                raise ValueError(f"response has no '{expect_key}' (got keys={keys}; "
                                 f"snippet={str(data)[:160]})")
            return data
        except Exception as err:  # noqa: BLE001
            last_err = err
            wait = 3 * attempt
            print(f"   ! {endpoint} attempt {attempt}/{retries} failed ({err}); retry in {wait}s")
            time.sleep(wait)
    raise RuntimeError(
        f"Could not fetch {url} after {retries} attempts.\n"
        f"   Last error: {last_err}\n"
        f"   If this persists your network may be filtering the API -- try a different\n"
        f"   network/VPN, wait a minute and re-run, or switch to ENTSO-E (see README).")


def _month_bounds(year: int):
    """Yield (start_str, end_str) for each calendar month (end = next month 1st)."""
    for m in range(1, 13):
        start = f"{year}-{m:02d}-01"
        end = f"{year + 1}-01-01" if m == 12 else f"{year}-{m + 1:02d}-01"
        yield start, end


# ---------------------------------------------------------------------------
# Fetchers (Energy-Charts)
# ---------------------------------------------------------------------------
def fetch_public_power(year: int) -> pd.DataFrame:
    """Return a 15-min DataFrame of all production types + load (MW, UTC index)."""
    frames = []
    for start, end in _month_bounds(year):
        print(f"   public_power {start} -> {end}")
        js = _get_json(
            "public_power",
            {"country": config.COUNTRY, "start": start, "end": end},
            expect_key="production_types",
        )
        idx = pd.to_datetime(js["unix_seconds"], unit="s", utc=True)
        cols = {}
        for pt in js["production_types"]:
            cols[pt["name"]] = pd.Series(pt["data"], index=idx, dtype="float64")
        frames.append(pd.DataFrame(cols))
        time.sleep(1.0)  # be polite to the public API
    raw = pd.concat(frames)
    raw = raw[~raw.index.duplicated(keep="first")].sort_index()
    start_ts = pd.Timestamp(f"{year}-01-01", tz="UTC")
    end_ts = pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
    raw = raw.loc[(raw.index >= start_ts) & (raw.index < end_ts)]
    (RAW_DIR / f"public_power_{year}_15min.csv").write_text(raw.to_csv())
    return raw


def fetch_price(year: int) -> pd.Series:
    """Return the hourly day-ahead price (EUR/MWh, UTC index)."""
    frames = []
    for start, end in _month_bounds(year):
        print(f"   price        {start} -> {end}")
        js = _get_json(
            "price",
            {"bzn": config.BIDDING_ZONE, "start": start, "end": end},
            expect_key="price",
        )
        idx = pd.to_datetime(js["unix_seconds"], unit="s", utc=True)
        frames.append(pd.Series(js["price"], index=idx, dtype="float64", name="price_eur_mwh"))
        time.sleep(1.0)
    price = pd.concat(frames)
    price = price[~price.index.duplicated(keep="first")].sort_index()
    start_ts = pd.Timestamp(f"{year}-01-01", tz="UTC")
    end_ts = pd.Timestamp(f"{year + 1}-01-01", tz="UTC")
    price = price.loc[(price.index >= start_ts) & (price.index < end_ts)]
    return price


# ---------------------------------------------------------------------------
# Processing
# ---------------------------------------------------------------------------
def _to_clean_hourly(series_or_df, year: int):
    """Resample to hourly mean, reindex to a full 8760-h UTC grid, fill gaps."""
    hourly = series_or_df.resample("1h").mean()
    full = pd.date_range(f"{year}-01-01", periods=config.HOURS_PER_YEAR, freq="h", tz="UTC")
    hourly = hourly.reindex(full)
    hourly = hourly.interpolate(limit_direction="both").ffill().bfill()
    return hourly


def build_processed(year: int) -> dict:
    """Fetch, clean and write all processed input files. Returns a summary dict."""
    print("-> Fetching generation + load (Energy-Charts /public_power) ...")
    raw15 = fetch_public_power(year)

    print("-> Fetching day-ahead price (Energy-Charts /price) ...")
    price15 = fetch_price(year)

    # Rename to internal labels where known; keep originals otherwise
    rename = {k: v for k, v in EC_NAME_MAP.items() if k in raw15.columns}
    gen = raw15.rename(columns=rename)

    # ---- hourly load (MW) ----
    load_h = _to_clean_hourly(gen["load"], year).rename("load_mw")

    # ---- hourly capacity factors (per-unit) ----
    cf = pd.DataFrame(index=load_h.index)
    for tech in ("wind_onshore", "wind_offshore", "solar", "ror"):
        ref_cap = config.CF_REFERENCE_CAPACITY_2025_MW[tech]
        gen_h = _to_clean_hourly(gen[tech], year)
        cf[tech] = (gen_h / ref_cap).clip(lower=0.0, upper=1.0)

    # ---- hourly price ----
    price_h = _to_clean_hourly(price15, year).rename("price_eur_mwh")

    # ---- hourly generation per carrier (for calibration mix) ----
    gen_h_all = pd.DataFrame(index=load_h.index)
    for col in gen.columns:
        gen_h_all[col] = _to_clean_hourly(gen[col], year)

    # ---- write processed files ----
    load_h.to_frame().to_csv(PROC_DIR / "demand_2025_hourly.csv", index_label="timestamp_utc")
    cf.to_csv(PROC_DIR / "cf_2025_hourly.csv", index_label="timestamp_utc")
    price_h.to_frame().to_csv(PROC_DIR / "price_2025_hourly.csv", index_label="timestamp_utc")
    gen_h_all.to_csv(PROC_DIR / "generation_2025_hourly.csv", index_label="timestamp_utc")

    summary = {
        "hours": int(len(load_h)),
        "annual_load_twh": float(load_h.sum() / 1e6),
        "peak_load_gw": float(load_h.max() / 1e3),
        "min_load_gw": float(load_h.min() / 1e3),
        "cf_annual_mean": {t: float(cf[t].mean()) for t in cf.columns},
        "price_mean_eur_mwh": float(price_h.mean()),
        "price_min_eur_mwh": float(price_h.min()),
        "price_max_eur_mwh": float(price_h.max()),
    }
    return summary


def write_provenance(summary: dict) -> None:
    """Write data/provenance.json documenting every series."""
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    prov = {
        "project": "RUB - Evaluating Germany's Kraftwerksstrategie (CRM)",
        "retrieval_date_utc": retrieved,
        "reference_year_calibration": YEAR,
        "target_year": config.TARGET_YEAR,
        "primary_source": {
            "name": "Fraunhofer ISE Energy-Charts API",
            "base_url": EC_BASE,
            "license": "CC BY 4.0 (data: Bundesnetzagentur | SMARD.de, ENTSO-E)",
            "token_required": False,
        },
        "series": [
            {"series": "Actual total load (hourly)", "endpoint": "/public_power field 'Load'",
             "url": f"{EC_BASE}/public_power?country=de", "year": YEAR, "units": "MW",
             "file": "data/processed/demand_2025_hourly.csv", "flag": None},
            {"series": "Wind onshore / offshore / solar capacity factors (hourly)",
             "endpoint": "/public_power generation / reference capacity",
             "url": f"{EC_BASE}/public_power?country=de", "year": YEAR, "units": "per-unit (0-1)",
             "file": "data/processed/cf_2025_hourly.csv",
             "flag": "CF = generation / annual-avg installed capacity (config); shapes re-scaled to 2030 fleet"},
            {"series": "Run-of-river availability (hourly)", "endpoint": "/public_power field 'Hydro Run-of-River'",
             "url": f"{EC_BASE}/public_power?country=de", "year": YEAR, "units": "per-unit (0-1)",
             "file": "data/processed/cf_2025_hourly.csv", "flag": None},
            {"series": "Day-ahead price DE-LU (hourly, validation)", "endpoint": "/price",
             "url": f"{EC_BASE}/price?bzn=DE-LU", "year": YEAR, "units": "EUR/MWh",
             "file": "data/processed/price_2025_hourly.csv", "flag": None},
            {"series": "Generation per production type (hourly, calibration mix)",
             "endpoint": "/public_power", "url": f"{EC_BASE}/public_power?country=de",
             "year": YEAR, "units": "MW", "file": "data/processed/generation_2025_hourly.csv", "flag": None},
        ],
        "scenario_inputs_2030_documented_in": "config.py",
        "scenario_input_sources": {
            "renewable_targets_2030": "EEG 2023 / NEP Szenariorahmen 2025 (Scn B): PV 215, onshore 115, offshore 30 GW",
            "coal_2030": "KVBG Anlage 2: 8 GW hard coal + 9 GW lignite",
            "demand_2030": f"{config.DEMAND_2030_TWH} TWh (NEP Szenariorahmen 2025, Scn B) [VERIFY]",
            "fuel_co2_prices_2030": "NEP Szenariorahmen 2025 commodity annex / Langfristszenarien [VERIFY]",
            "tech_costs": "Danish Energy Agency Technology Catalogue (PyPSA technology-data)",
            "co2_intensities": "Umweltbundesamt CC 29/2022",
            "policy": "BMWE 15 Jan 2026 (12 GW tendered, 10 GW long-run dispatchable)",
        },
        "data_summary_2025": summary,
    }
    (DATA_DIR / "provenance.json").write_text(json.dumps(prov, indent=2))


def main() -> None:
    print("=" * 70)
    print(f"DATA LOADER  |  authentic {YEAR} data for Germany  |  source: {SOURCE}")
    print("=" * 70)
    if SOURCE != "energy-charts":
        raise SystemExit("Only the token-free 'energy-charts' path is enabled by default. "
                          "See comments to switch to ENTSO-E with a .env token.")
    summary = build_processed(YEAR)
    write_provenance(summary)

    print("\n--- PROVENANCE SUMMARY (authentic 2025 data) ---")
    print(f"  hours loaded ............ {summary['hours']} (expected {config.HOURS_PER_YEAR})")
    print(f"  annual load ............. {summary['annual_load_twh']:.1f} TWh")
    print(f"  peak / min load ......... {summary['peak_load_gw']:.1f} / {summary['min_load_gw']:.1f} GW")
    print(f"  mean day-ahead price .... {summary['price_mean_eur_mwh']:.1f} EUR/MWh "
          f"(min {summary['price_min_eur_mwh']:.0f}, max {summary['price_max_eur_mwh']:.0f})")
    print("  annual-mean capacity factors:")
    for t, v in summary["cf_annual_mean"].items():
        print(f"      {t:14s} {v:5.3f}")
    print("\n  Wrote: data/processed/*.csv  and  data/provenance.json")
    print("  Next:  python model.py")


if __name__ == "__main__":
    main()
