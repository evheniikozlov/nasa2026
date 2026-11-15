"""
Data access module for NASA Trend Detector.

Four functions for four data sources:
    get_data_earthaccess() — earthaccess (GLDAS, GPM, OMI, MERRA-2)
    get_data_appeears()    — AppEEARS (MODIS LST, NDVI, Burned Area)
    get_data_ntl()         — blackmarblepy (VIIRS Nighttime Lights)
    get_data_noaa()        — NOAA CSV (CO₂, CH₄ global time series)

Usage:
    from data_access import get_data

    # One function for everything — routes to the right source automatically:
    da = get_data("GWS_tavg", "2010-01-01", "2023-12-31", bbox=(76.8, 28.4, 77.4, 28.9))
    da = get_data("NDVI", "2010-01-01", "2023-12-31", bbox=(76.8, 28.4, 77.4, 28.9))
    da = get_data("CO2_Mauna_Loa", "2000-01-01", "2023-12-31")  # no bbox needed
"""

import earthaccess
import xarray as xr
import numpy as np
import pandas as pd
import geopandas as gpd
import requests
import time
import os
import re
import tempfile
from shapely.geometry import box
from dotenv import load_dotenv

load_dotenv(override=True)

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".data_cache")

# ============================================================
# Variable configs
# ============================================================

# OPeNDAP grid definitions per dataset
_GRIDS = {
    "GLDAS_CLSM025_DA1_D": {
        # lat: 600 pts, -59.875..89.875 (0.25°), lon: 1440 pts, -179.875..179.875 (0.25°)
        "lat": {"start": -59.875, "step": 0.25, "n": 600},
        "lon": {"start": -179.875, "step": 0.25, "n": 1440},
        "dap_field_tpl": "/{field}[0][{lat_s}:{lat_e}][{lon_s}:{lon_e}]",
        "group": None,
    },
    "GPM_3IMERGM": {
        # lon: 3600 pts, -179.95..179.95 (0.1°), lat: 1800 pts, -89.95..89.95 (0.1°)
        # DAP dims: (time, lon, lat)
        "lat": {"start": -89.95, "step": 0.1, "n": 1800},
        "lon": {"start": -179.95, "step": 0.1, "n": 3600},
        "dap_field_tpl": "/Grid/{field}[0][{lon_s}:{lon_e}][{lat_s}:{lat_e}]",
        "group": "Grid",
    },
    "OMNO2d": {
        # YDim: 720 pts, -89.875..89.875 (0.25°), XDim: 1440 pts, -179.875..179.875 (0.25°)
        # No time dim in OPeNDAP
        "lat": {"start": -89.875, "step": 0.25, "n": 720},
        "lon": {"start": -179.875, "step": 0.25, "n": 1440},
        "dap_field_tpl": "/HDFEOS/GRIDS/ColumnAmountNO2/Data_Fields/{field}[{lat_s}:{lat_e}][{lon_s}:{lon_e}]",
        "group": "HDFEOS/GRIDS/ColumnAmountNO2/Data_Fields",
    },
    "M2TMNXAER": {
        # lat: 361 pts, -90..90 (0.5°), lon: 576 pts, -180..179.375 (0.625°)
        "lat": {"start": -90.0, "step": 0.5, "n": 361},
        "lon": {"start": -180.0, "step": 0.625, "n": 576},
        "dap_field_tpl": "/{field}[0][{lat_s}:{lat_e}][{lon_s}:{lon_e}]",
        "group": None,
    },
}

EARTHACCESS_VARIABLES = {
    "GWS_tavg": {
        "dataset": "GLDAS_CLSM025_DA1_D",
        "version": "2.2",
        "field": "GWS_tavg",
        "daily": True,
        "description": "Groundwater storage (mm)",
    },
    "TWS_tavg": {
        "dataset": "GLDAS_CLSM025_DA1_D",
        "version": "2.2",
        "field": "TWS_tavg",
        "daily": True,
        "description": "Total water storage (mm)",
    },
    "precipitation": {
        "dataset": "GPM_3IMERGM",
        "version": "07",
        "field": "precipitation",
        "daily": False,
        "description": "Monthly accumulated precipitation (mm/hr)",
    },
    "NO2": {
        "dataset": "OMNO2d",
        "version": "003",
        "field": "ColumnAmountNO2TropCloudScreened",
        "daily": True,
        "description": "Tropospheric NO2 column, cloud-screened (molec/cm²)",
    },
    # MERRA-2 aerosols
    "Dust": {
        "dataset": "M2TMNXAER",
        "version": "5.12.4",
        "field": "DUSMASS",
        "daily": False,
        "description": "Dust surface mass concentration (kg/m³)",
    },
    "Black_Carbon": {
        "dataset": "M2TMNXAER",
        "version": "5.12.4",
        "field": "BCSMASS",
        "daily": False,
        "description": "Black carbon surface mass concentration (kg/m³)",
    },
    "SO2": {
        "dataset": "M2TMNXAER",
        "version": "5.12.4",
        "field": "SO2SMASS",
        "daily": False,
        "description": "SO2 surface mass concentration (kg/m³)",
    },
    "SO4": {
        "dataset": "M2TMNXAER",
        "version": "5.12.4",
        "field": "SO4SMASS",
        "daily": False,
        "description": "SO4 surface mass concentration (kg/m³)",
    },
    "Organic_Carbon": {
        "dataset": "M2TMNXAER",
        "version": "5.12.4",
        "field": "OCSMASS",
        "daily": False,
        "description": "Organic carbon surface mass concentration (kg/m³)",
    },
    "Aerosol_AOT": {
        "dataset": "M2TMNXAER",
        "version": "5.12.4",
        "field": "TOTEXTTAU",
        "daily": False,
        "description": "Total aerosol extinction AOT at 550nm (unitless)",
    },
}

APPEEARS_VARIABLES = {
    "NDVI": {
        "product": "MOD13A3.061",
        "layer": "_1_km_monthly_NDVI",
        "description": "Vegetation index — monthly 1km (MODIS)",
    },
    "LST_Day": {
        "product": "MOD11A2.061",
        "layer": "LST_Day_1km",
        "description": "Daytime land surface temperature — 8-day 1km (MODIS)",
    },
    "LST_Night": {
        "product": "MOD11A2.061",
        "layer": "LST_Night_1km",
        "description": "Nighttime land surface temperature — 8-day 1km (MODIS)",
    },
    "Burned_Area": {
        "product": "MCD64A1.061",
        "layer": "Burn_Date",
        "description": "Burn date detection — monthly 500m (MODIS)",
    },
}

NTL_VARIABLE = {
    "NTL": {
        "product": "VNP46A4",
        "description": "Nighttime lights — yearly composite 500m (VIIRS Black Marble)",
    },
}

NOAA_VARIABLES = {
    "CO2_Mauna_Loa": {
        "url": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv",
        "value_col": "average",
        "unit": "ppm",
        "description": "Atmospheric CO₂ — Mauna Loa (NOAA/Scripps, 1958–present)",
    },
    "CO2_global": {
        "url": "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_gl.csv",
        "value_col": "average",
        "unit": "ppm",
        "description": "Atmospheric CO₂ — global marine surface (NOAA, 1979–present)",
    },
    "CH4_global": {
        "url": "https://gml.noaa.gov/webdata/ccgg/trends/ch4/ch4_mm_gl.csv",
        "value_col": "average",
        "unit": "ppb",
        "description": "Atmospheric CH₄ — global marine surface (NOAA, 1983–present)",
    },
}

# ============================================================
# Phenomena, regions, investigations
# ============================================================

PHENOMENA = {
    "water_stress": {
        "name": "Water Stress",
        "variables": ["GWS_tavg", "precipitation"],
    },
    "urban_growth": {
        "name": "Urban Growth",
        "variables": ["NTL", "LST_Day", "LST_Night", "NO2"],
    },
    "air_pollution": {
        "name": "Air Pollution",
        "variables": ["NO2", "SO2", "Black_Carbon", "Aerosol_AOT"],
    },
    "deforestation": {
        "name": "Deforestation",
        "variables": ["NDVI"],
    },
    "wildfires": {
        "name": "Wildfires",
        "variables": ["Burned_Area"],
    },
    "desertification": {
        "name": "Desertification",
        "variables": ["NDVI", "precipitation"],
    },
    "greenhouse_gases": {
        "name": "Greenhouse Gases",
        "variables": ["CO2_Mauna_Loa", "CO2_global", "CH4_global"],
    },
}

REGIONS = {
    "punjab": {"name": "Punjab, India", "bbox": (73.8, 29.5, 76.9, 32.5)},
    "delhi": {"name": "Delhi, India", "bbox": (76.8, 28.4, 77.4, 28.9)},
    "beijing": {"name": "Beijing, China", "bbox": (116.0, 39.6, 116.8, 40.2)},
    "rondonia": {"name": "Rondônia, Brazil", "bbox": (-65.0, -13.5, -60.0, -8.0)},
    "se_australia": {"name": "SE Australia", "bbox": (147.0, -38.0, 153.0, -33.0)},
    "sahel": {"name": "Sahel (Niger/Nigeria border)", "bbox": (2.0, 11.0, 10.0, 16.0)},
}

# One investigation per phenomenon — the most vivid region
INVESTIGATIONS = {
    "water_stress": {
        "phenomenon": "water_stress",
        "region": "punjab",
        "period": ("2003-01-01", "2023-12-31"),
        "hypothesis": "Groundwater declines while precipitation stays stable → human pumping",
    },
    "urban_growth": {
        "phenomenon": "urban_growth",
        "region": "delhi",
        "period": ("2012-01-01", "2023-12-31"),
        "hypothesis": "Nighttime lights expand, heat island grows, NO₂ rises → rapid urbanization",
    },
    "air_pollution": {
        "phenomenon": "air_pollution",
        "region": "beijing",
        "period": ("2005-01-01", "2023-12-31"),
        "hypothesis": "NO₂ and aerosols decline after 2013 clean air policies, sharp COVID-2020 drop",
    },
    "deforestation": {
        "phenomenon": "deforestation",
        "region": "rondonia",
        "period": ("2001-01-01", "2023-12-31"),
        "hypothesis": "Vegetation index declines as forest is cleared for cattle and agriculture",
    },
    "wildfires": {
        "phenomenon": "wildfires",
        "region": "se_australia",
        "period": ("2001-01-01", "2023-12-31"),
        "hypothesis": "Burned area increases over time, peak during 2019–2020 Black Summer",
    },
    "desertification": {
        "phenomenon": "desertification",
        "region": "sahel",
        "period": ("2001-01-01", "2023-12-31"),
        "hypothesis": "Vegetation declines while precipitation is stable → overgrazing/overfarming",
    },
    "greenhouse_gases": {
        "phenomenon": "greenhouse_gases",
        "region": None,
        "period": ("1980-01-01", "2023-12-31"),
        "hypothesis": "CO₂ and CH₄ show steady upward trends from fossil fuels and agriculture",
    },
}


# ============================================================
# Auth & OPeNDAP helpers
# ============================================================

_ea_logged_in = False


def _coord_to_indices(coord_cfg, low, high):
    """Convert coordinate range to grid indices."""
    start, step = coord_cfg["start"], coord_cfg["step"]
    i_low = max(0, int((low - start) / step))
    i_high = min(coord_cfg["n"] - 1, int((high - start) / step))
    return i_low, i_high


def _get_opendap_url(granule):
    """Extract OPeNDAP URL from an earthaccess granule."""
    for u in granule.get("umm", {}).get("RelatedUrls", []):
        if u.get("Type") == "USE SERVICE API" and "opendap" in u.get("URL", "").lower():
            return u["URL"]
    return None


def _granule_date(granule):
    """Extract date from granule temporal metadata."""
    try:
        t = granule.get("umm", {}).get("TemporalExtent", {}).get("RangeDateTime", {})
        begin = t.get("BeginningDateTime", "")
        if begin:
            return pd.Timestamp(begin[:10])
    except Exception:
        pass
    return None


def _fetch_dap4_nc4(session, opendap_url, ce, group=None):
    """Fetch a DAP4 subset as NetCDF-4 and open with xarray."""
    resp = session.get(f"{opendap_url}.dap.nc4?dap4.ce={ce}")
    resp.raise_for_status()
    tmp = tempfile.NamedTemporaryFile(suffix=".nc4", delete=False)
    tmp.write(resp.content)
    tmp.close()
    open_kwargs = {"engine": "h5netcdf"}
    if group:
        open_kwargs["group"] = group
    ds = xr.open_dataset(tmp.name, **open_kwargs)
    os.unlink(tmp.name)
    return ds


def _standardize_coords(da, grid, bbox):
    """Rename coords to lat/lon and ensure (time, lat, lon) order."""
    west, south, east, north = bbox
    g_lat, g_lon = grid["lat"], grid["lon"]
    lat_s, lat_e = _coord_to_indices(g_lat, south, north)
    lon_s, lon_e = _coord_to_indices(g_lon, west, east)
    lat_vals = np.arange(lat_s, lat_e + 1) * g_lat["step"] + g_lat["start"]
    lon_vals = np.arange(lon_s, lon_e + 1) * g_lon["step"] + g_lon["start"]

    # Drop any existing lat/lon coords that aren't dims (avoids rename conflicts)
    for c in list(da.coords):
        if c in ("lat", "lon") and c not in da.dims:
            da = da.drop_vars(c)

    # Find non-time dims and assign lat/lon values
    non_time_dims = [d for d in da.dims if d != "time"]
    rename = {}
    if len(non_time_dims) == 2:
        # Match dims to lat/lon — prefer name match, fall back to size match
        lat_dim, lon_dim = None, None
        for d in non_time_dims:
            if d == "lat" or d in ("YDim", "latitude"):
                lat_dim = d
            elif d == "lon" or d in ("XDim", "longitude"):
                lon_dim = d
        # Fall back to size-based matching only if names didn't match
        if lat_dim is None or lon_dim is None:
            for d in non_time_dims:
                if d == lat_dim or d == lon_dim:
                    continue
                if lat_dim is None and da.sizes[d] == len(lat_vals):
                    lat_dim = d
                elif lon_dim is None and da.sizes[d] == len(lon_vals):
                    lon_dim = d

        if lat_dim:
            da = da.assign_coords({lat_dim: lat_vals})
            if lat_dim != "lat":
                rename[lat_dim] = "lat"
        if lon_dim:
            da = da.assign_coords({lon_dim: lon_vals})
            if lon_dim != "lon":
                rename[lon_dim] = "lon"
    if rename:
        da = da.rename(rename)

    if set(da.dims) >= {"time", "lat", "lon"}:
        da = da.transpose("time", "lat", "lon")
    return da


def _ensure_earthaccess_login():
    global _ea_logged_in
    if not _ea_logged_in:
        earthaccess.login(strategy="environment")
        _ea_logged_in = True


def _get_appeears_token():
    user = os.getenv("EARTHDATA_USER")
    password = os.getenv("EARTHDATA_PASS")
    resp = requests.post(
        "https://appeears.earthdatacloud.nasa.gov/api/login",
        auth=(user, password),
    )
    resp.raise_for_status()
    return resp.json()["token"]


# ============================================================
# Universal entry point
# ============================================================

def get_data(
    variable: str,
    start_date: str,
    end_date: str,
    bbox: tuple = None,
) -> xr.DataArray:
    """
    Fetch any variable — automatically routes to the right data source.

    Args:
        variable: any variable name from list_variables()
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
        bbox: (west, south, east, north) — required for gridded data, ignored for NOAA

    Returns:
        xarray.DataArray sorted by time.
    """
    if variable in NOAA_VARIABLES:
        return get_data_noaa(variable, start_date, end_date)

    if bbox is None:
        all_vars = (
            list(EARTHACCESS_VARIABLES) + list(APPEEARS_VARIABLES)
            + list(NTL_VARIABLE) + list(NOAA_VARIABLES)
        )
        if variable not in all_vars:
            raise ValueError(f"Unknown variable '{variable}'. Available: {', '.join(all_vars)}")
        raise ValueError(f"bbox is required for variable '{variable}'")

    if variable in EARTHACCESS_VARIABLES:
        return get_data_earthaccess(bbox, variable, start_date, end_date)
    if variable in APPEEARS_VARIABLES:
        return get_data_appeears(bbox, variable, start_date, end_date)
    if variable == "NTL":
        return get_data_ntl(bbox, start_date, end_date)

    all_vars = (
        list(EARTHACCESS_VARIABLES) + list(APPEEARS_VARIABLES)
        + list(NTL_VARIABLE) + list(NOAA_VARIABLES)
    )
    raise ValueError(f"Unknown variable '{variable}'. Available: {', '.join(all_vars)}")


# ============================================================
# 1. earthaccess via OPeNDAP — GLDAS, GPM, OMI, MERRA-2
# ============================================================

def get_data_earthaccess(
    bbox: tuple,
    variable: str,
    start_date: str,
    end_date: str,
) -> xr.DataArray:
    """
    Fetch data via OPeNDAP (server-side subsetting — downloads only the bbox, not full global files).

    Args:
        bbox: (west, south, east, north) in degrees
        variable: any key from EARTHACCESS_VARIABLES
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"

    Returns:
        xarray.DataArray with dims (time, lat, lon), subsetted to bbox.
    """
    if variable not in EARTHACCESS_VARIABLES:
        available = ", ".join(EARTHACCESS_VARIABLES.keys())
        raise ValueError(f"Unknown variable '{variable}'. Available: {available}")

    cfg = EARTHACCESS_VARIABLES[variable]
    grid = _GRIDS[cfg["dataset"]]
    _ensure_earthaccess_login()

    results = earthaccess.search_data(
        short_name=cfg["dataset"],
        version=cfg["version"],
        temporal=(start_date, end_date),
        bounding_box=bbox,
    )

    if not results:
        raise ValueError(f"No data found for {variable} in bbox={bbox}, dates={start_date}..{end_date}")

    print(f"Found {len(results)} granules for {variable}, fetching via OPeNDAP...")

    session = earthaccess.get_requests_https_session()
    west, south, east, north = bbox
    lat_s, lat_e = _coord_to_indices(grid["lat"], south, north)
    lon_s, lon_e = _coord_to_indices(grid["lon"], west, east)
    ce = grid["dap_field_tpl"].format(
        field=cfg["field"], lat_s=lat_s, lat_e=lat_e, lon_s=lon_s, lon_e=lon_e,
    )

    arrays = []
    for i, granule in enumerate(results):
        opendap_url = _get_opendap_url(granule)
        if not opendap_url:
            continue
        try:
            ds = _fetch_dap4_nc4(session, opendap_url, ce, grid["group"])
            da = ds[cfg["field"]]

            # Ensure time dim with correct date
            date = _granule_date(granule)
            if "time" in da.dims and date:
                da["time"] = [date]
            elif "time" not in da.dims:
                da = da.expand_dims(time=[date] if date else [i])

            arrays.append(da)
        except Exception as e:
            print(f"  Warning: skipping granule {i}: {e}")
            continue

        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(results)} granules fetched")

    if not arrays:
        raise RuntimeError(f"Could not fetch any data for {variable}")

    da = xr.concat(arrays, dim="time")

    # Mask NO2 fill values (large negatives ~-1e16)
    if variable == "NO2":
        da = da.where(da > 0)

    # Standardize coord names and dim order
    da = _standardize_coords(da, grid, bbox)

    print(f"  Done: {da.sizes}")
    return da.sortby("time")


# ============================================================
# 2. AppEEARS — MODIS LST, NDVI, Burned Area
# ============================================================

def get_data_appeears(
    bbox: tuple,
    variable: str,
    start_date: str,
    end_date: str,
    poll_interval: int = 30,
) -> xr.DataArray:
    """
    Fetch data via AppEEARS REST API (MODIS products).

    Args:
        bbox: (west, south, east, north) in degrees
        variable: "NDVI", "LST_Day", "LST_Night", or "Burned_Area"
        start_date: "YYYY-MM-DD"
        end_date: "YYYY-MM-DD"
        poll_interval: seconds between status checks (default 30)

    Returns:
        xarray.DataArray with dims (time, lat, lon).
    """
    if variable not in APPEEARS_VARIABLES:
        available = ", ".join(APPEEARS_VARIABLES.keys())
        raise ValueError(f"Unknown variable '{variable}'. Available: {available}")

    cfg = APPEEARS_VARIABLES[variable]
    api = "https://appeears.earthdatacloud.nasa.gov/api"
    token = _get_appeears_token()
    headers = {"Authorization": f"Bearer {token}"}

    west, south, east, north = bbox
    # Convert dates from YYYY-MM-DD to MM-DD-YYYY (AppEEARS format)
    sd = f"{start_date[5:7]}-{start_date[8:10]}-{start_date[0:4]}"
    ed = f"{end_date[5:7]}-{end_date[8:10]}-{end_date[0:4]}"

    task_payload = {
        "task_type": "area",
        "task_name": f"{variable}_{int(time.time())}",
        "params": {
            "dates": [{"startDate": sd, "endDate": ed}],
            "layers": [{"product": cfg["product"], "layer": cfg["layer"]}],
            "output": {"format": {"type": "geotiff"}, "projection": "geographic"},
            "geo": {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [west, south], [east, south], [east, north],
                            [west, north], [west, south],
                        ]],
                    },
                    "properties": {},
                }],
            },
        },
    }

    # Submit task
    resp = requests.post(f"{api}/task", json=task_payload, headers=headers)
    resp.raise_for_status()
    task_id = resp.json()["task_id"]
    print(f"AppEEARS task submitted for {variable}: {task_id}")

    # Poll until done
    for i in range(60):
        status = requests.get(f"{api}/task/{task_id}", headers=headers).json()["status"]
        print(f"  [{i+1}] {status}")
        if status == "done":
            break
        if status == "error":
            raise RuntimeError(f"AppEEARS task failed: {task_id}")
        time.sleep(poll_interval)
    else:
        raise TimeoutError(f"AppEEARS task did not complete in time: {task_id}")

    # Download files
    bundle = requests.get(f"{api}/bundle/{task_id}", headers=headers).json()
    tif_files = [f for f in bundle["files"] if f["file_name"].endswith(".tif")]

    task_dir = os.path.join(CACHE_DIR, "appeears", task_id)
    os.makedirs(task_dir, exist_ok=True)

    local_paths = []
    for f_info in tif_files:
        file_id = f_info["file_id"]
        file_name = f_info["file_name"].split("/")[-1]
        local_path = os.path.join(task_dir, file_name)

        if not os.path.exists(local_path):
            resp = requests.get(
                f"{api}/bundle/{task_id}/{file_id}",
                headers=headers,
                stream=True,
            )
            resp.raise_for_status()
            with open(local_path, "wb") as out:
                for chunk in resp.iter_content(chunk_size=8192):
                    out.write(chunk)

        local_paths.append(local_path)

    print(f"Downloaded {len(local_paths)} GeoTIFFs for {variable}")

    # Open as xarray Dataset with time dimension
    import rioxarray  # noqa: F401 — needed for .rio accessor

    arrays = []
    for path in sorted(local_paths):
        da = xr.open_dataarray(path, engine="rasterio")
        # Extract date from filename (doyYYYYDDD pattern)
        fname = os.path.basename(path)
        doy_str = _extract_doy(fname)
        if doy_str:
            da = da.assign_coords(time=pd.Timestamp(doy_str))
        arrays.append(da)

    if arrays:
        result = xr.concat(arrays, dim="time")
        result = result.rename({"x": "lon", "y": "lat"})
        if "band" in result.dims:
            result = result.squeeze("band", drop=True)
        return result.sortby("time")

    raise RuntimeError(f"No GeoTIFF files found for {variable}")


def _extract_doy(filename: str) -> str | None:
    """Extract date from AppEEARS filename like ...doy2022001... → '2022-01-01'."""
    match = re.search(r"doy(\d{4})(\d{3})", filename)
    if match:
        year, doy = int(match.group(1)), int(match.group(2))
        return (pd.Timestamp(f"{year}-01-01") + pd.Timedelta(days=doy - 1)).strftime("%Y-%m-%d")
    return None


# ============================================================
# 3. blackmarblepy — VIIRS Nighttime Lights
# ============================================================

def get_data_ntl(
    bbox: tuple,
    start_date: str,
    end_date: str,
) -> xr.DataArray:
    """
    Fetch VIIRS nighttime lights via blackmarblepy.

    Args:
        bbox: (west, south, east, north) in degrees
        start_date: "YYYY-MM-DD" (year granularity — uses Jan 1 of each year)
        end_date: "YYYY-MM-DD"

    Returns:
        xarray.DataArray with dims (time, lat, lon), nighttime light radiance.
    """
    from blackmarble.raster import bm_raster

    token = os.getenv("NASA_BEARER_TOKEN")
    if not token:
        raise ValueError("NASA_BEARER_TOKEN not set in .env")

    west, south, east, north = bbox
    gdf = gpd.GeoDataFrame(geometry=[box(west, south, east, north)], crs="EPSG:4326")

    date_range = pd.date_range(start_date, end_date, freq="YS")
    if len(date_range) == 0:
        date_range = pd.date_range(start_date, periods=1, freq="YS")

    print(f"Fetching nighttime lights for {len(date_range)} year(s)...")

    result = bm_raster(
        gdf,
        product_id="VNP46A4",
        date_range=date_range,
        token=token,
    )

    if "x" in result.dims:
        result = result.rename({"x": "lon", "y": "lat"})

    # Extract DataArray from Dataset
    if isinstance(result, xr.Dataset):
        var_name = list(result.data_vars)[0]
        result = result[var_name].rename("NTL")

    return result


# ============================================================
# 4. NOAA — CO₂, CH₄ global time series
# ============================================================

def get_data_noaa(
    variable: str,
    start_date: str = None,
    end_date: str = None,
) -> xr.DataArray:
    """
    Fetch NOAA global greenhouse gas time series (CO₂, CH₄).

    These are global (non-gridded) monthly time series — no bbox needed.

    Args:
        variable: "CO2_Mauna_Loa", "CO2_global", or "CH4_global"
        start_date: "YYYY-MM-DD" (optional, filters result)
        end_date: "YYYY-MM-DD" (optional, filters result)

    Returns:
        xarray.DataArray with dim (time,), monthly values.
    """
    if variable not in NOAA_VARIABLES:
        available = ", ".join(NOAA_VARIABLES.keys())
        raise ValueError(f"Unknown variable '{variable}'. Available: {available}")

    cfg = NOAA_VARIABLES[variable]

    resp = requests.get(cfg["url"], timeout=30)
    resp.raise_for_status()

    # Parse CSV, skip comment lines starting with #
    lines = resp.text.strip().split("\n")
    data_lines = [l for l in lines if not l.startswith("#")]
    csv_text = "\n".join(data_lines)

    df = pd.read_csv(pd.io.common.StringIO(csv_text))
    df["time"] = pd.to_datetime(df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2) + "-15")
    values = df[cfg["value_col"]].values.astype(float)

    da = xr.DataArray(
        values,
        dims=["time"],
        coords={"time": df["time"].values},
        name=variable,
        attrs={"units": cfg["unit"], "description": cfg["description"]},
    )

    # Filter by date range
    if start_date:
        da = da.sel(time=slice(start_date, None))
    if end_date:
        da = da.sel(time=slice(None, end_date))

    print(f"Fetched {variable}: {len(da.time)} monthly values")
    return da.sortby("time")


# ============================================================
# Info helpers
# ============================================================

def list_variables():
    """Print all available variables across all sources."""
    print("  earthaccess:")
    for name, cfg in EARTHACCESS_VARIABLES.items():
        print(f"    {name:20s} — {cfg['description']}")
    print("  AppEEARS:")
    for name, cfg in APPEEARS_VARIABLES.items():
        print(f"    {name:20s} — {cfg['description']}")
    print("  blackmarblepy:")
    for name, cfg in NTL_VARIABLE.items():
        print(f"    {name:20s} — {cfg['description']}")
    print("  NOAA:")
    for name, cfg in NOAA_VARIABLES.items():
        print(f"    {name:20s} — {cfg['description']}")


def list_regions():
    """Print available regions."""
    for key, r in REGIONS.items():
        print(f"  {key:20s} — {r['name']:30s} bbox={r['bbox']}")


def list_investigations():
    """Print all investigations with their configs."""
    for key, inv in INVESTIGATIONS.items():
        ph = PHENOMENA[inv["phenomenon"]]
        region = REGIONS[inv["region"]]["name"] if inv["region"] else "Global"
        variables = ", ".join(ph["variables"])
        print(f"  {key:20s} — {ph['name']} @ {region}")
        print(f"  {'':20s}   period: {inv['period'][0]} .. {inv['period'][1]}")
        print(f"  {'':20s}   variables: {variables}")
        print(f"  {'':20s}   hypothesis: {inv['hypothesis']}")
        print()
