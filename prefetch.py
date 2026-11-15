"""
Pre-download all data for investigations.
Run once before the presentation so the demo works offline.

earthaccess variables use OPeNDAP (server-side subsetting), so each
granule is tiny (~1 KB). Daily datasets (GLDAS, OMI) are still sampled
to 1st of each month to limit HTTP request count (~250 vs ~7600).

Usage:
    python prefetch.py                  # all investigations
    python prefetch.py water_stress     # one investigation
    python prefetch.py --list           # show what will be downloaded
"""

import sys
import os
import time as time_module

import pandas as pd
import xarray as xr

from data_access import (
    get_data, INVESTIGATIONS, PHENOMENA, REGIONS,
    EARTHACCESS_VARIABLES,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def _is_daily(variable: str) -> bool:
    """Check if a variable comes from a daily dataset."""
    cfg = EARTHACCESS_VARIABLES.get(variable)
    return cfg is not None and cfg.get("daily", False)


def nc_path(investigation_key: str, variable: str) -> str:
    return os.path.join(DATA_DIR, investigation_key, f"{variable}.nc")


def _download_daily_monthly_sampled(variable, start_date, end_date, bbox):
    """
    For daily datasets: download 1st of each month instead of every day.
    E.g. 2003-2023 = 252 days instead of 7600.
    """
    months = pd.date_range(start_date, end_date, freq="MS")
    print(f"  ... daily dataset → sampling 1st of each month ({len(months)} months)")

    arrays = []
    for i, month_start in enumerate(months):
        day_str = month_start.strftime("%Y-%m-%d")
        day_end = month_start.strftime("%Y-%m-%d")
        try:
            da = get_data(variable, day_str, day_end, bbox=bbox)
            arrays.append(da)
            if (i + 1) % 12 == 0:
                print(f"  ... {i + 1}/{len(months)} months downloaded")
        except Exception as e:
            print(f"  ... skip {day_str}: {e}")
            continue

    if not arrays:
        raise RuntimeError(f"No data downloaded for {variable}")

    return xr.concat(arrays, dim="time").sortby("time")


def prefetch_variable(investigation_key, variable, bbox, start_date, end_date):
    """Download one variable and save as NetCDF. Skips if exists."""
    path = nc_path(investigation_key, variable)

    if os.path.exists(path):
        print(f"  SKIP {variable} — already exists")
        return True

    os.makedirs(os.path.dirname(path), exist_ok=True)

    try:
        t0 = time_module.time()

        if _is_daily(variable):
            da = _download_daily_monthly_sampled(variable, start_date, end_date, bbox)
        else:
            da = get_data(variable, start_date, end_date, bbox=bbox)

        da.to_netcdf(path)
        elapsed = time_module.time() - t0
        size_mb = os.path.getsize(path) / 1024 / 1024
        print(f"  OK   {variable} — {da.sizes.get('time', '?')} timesteps, {size_mb:.1f} MB, {elapsed:.0f}s")
        return True
    except Exception as e:
        print(f"  FAIL {variable} — {e}")
        return False


def prefetch_investigation(key):
    inv = INVESTIGATIONS[key]
    ph = PHENOMENA[inv["phenomenon"]]
    region = REGIONS[inv["region"]] if inv["region"] else None
    bbox = region["bbox"] if region else None
    region_name = region["name"] if region else "Global"
    start_date, end_date = inv["period"]

    print(f"\n{'='*60}")
    print(f"{ph['name']} @ {region_name}")
    print(f"Period: {start_date} .. {end_date}")
    print(f"Variables: {', '.join(ph['variables'])}")
    print(f"{'='*60}")

    results = {}
    for variable in ph["variables"]:
        results[variable] = prefetch_variable(key, variable, bbox, start_date, end_date)

    passed = sum(results.values())
    total = len(results)
    print(f"\nResult: {passed}/{total} variables OK")
    return results


def show_plan():
    print("Prefetch plan:\n")
    for key, inv in INVESTIGATIONS.items():
        ph = PHENOMENA[inv["phenomenon"]]
        region = REGIONS[inv["region"]] if inv["region"] else None
        region_name = region["name"] if region else "Global"
        start_date, end_date = inv["period"]

        months = len(pd.date_range(start_date, end_date, freq="MS"))

        print(f"  {key}: {ph['name']} @ {region_name} ({start_date[:4]}–{end_date[:4]})")
        for var in ph["variables"]:
            exists = "CACHED" if os.path.exists(nc_path(key, var)) else "TO DOWNLOAD"
            daily_note = f" (monthly sampled, ~{months} granules)" if _is_daily(var) else ""
            print(f"    {var:20s} [{exists}]{daily_note}")
        print()


def main():
    if "--list" in sys.argv:
        show_plan()
        return

    targets = [a for a in sys.argv[1:] if not a.startswith("-")]
    if targets:
        for t in targets:
            if t not in INVESTIGATIONS:
                print(f"Unknown investigation: {t}")
                print(f"Available: {', '.join(INVESTIGATIONS.keys())}")
                return
        keys = targets
    else:
        keys = list(INVESTIGATIONS.keys())

    print(f"Prefetching {len(keys)} investigation(s): {', '.join(keys)}")

    all_results = {}
    t_start = time_module.time()

    for key in keys:
        all_results[key] = prefetch_investigation(key)

    elapsed = time_module.time() - t_start

    print(f"\n{'='*60}")
    print(f"SUMMARY ({elapsed:.0f}s total)")
    print(f"{'='*60}")
    for key, results in all_results.items():
        passed = sum(results.values())
        total = len(results)
        mark = "OK" if passed == total else "PARTIAL"
        print(f"  {key:20s} {passed}/{total} {mark}")

    total_size = 0
    for root, dirs, files in os.walk(DATA_DIR):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))
    print(f"\nTotal data size: {total_size / 1024 / 1024:.0f} MB")


if __name__ == "__main__":
    main()
