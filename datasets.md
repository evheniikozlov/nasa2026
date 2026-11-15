# Datasets & Variables

## Phenomena

| # | Phenomenon | Datasets | Variables |
|---|-----------|----------|-----------|
| 1 | Water Stress | GLDAS + GPM | GWS_tavg, precipitation |
| 2 | Urban Growth | VIIRS + MODIS LST + OMI | NTL, LST_Day, LST_Night, NO2 |
| 3 | Air Pollution | OMI + MERRA-2 | NO2, SO2, Black_Carbon, Aerosol_AOT |
| 4 | Deforestation | MODIS NDVI | NDVI |
| 5 | Wildfires | MODIS Burned Area | Burned_Area |
| 6 | Desertification | MODIS NDVI + GPM | NDVI, precipitation |
| 7 | Greenhouse Gases | NOAA GML | CO2_Mauna_Loa, CO2_global, CH4_global |

---

## Data Sources (як працює завантаження)

У нас 4 різних джерела даних, кожне зі своїм протоколом і особливостями.

### 1) earthaccess + OPeNDAP (GES DISC)

**Датасети:** GLDAS, GPM, OMI, MERRA-2 (10 змінних)

**Як працює:**
- `earthaccess.search_data()` знаходить гранули (файли) за датасетом, датами і bbox
- З кожної гранули витягуємо OPeNDAP URL — це адреса на сервері NASA Hyrax
- Робимо HTTP GET до `{url}.dap.nc4?dap4.ce=/{field}[0][lat_s:lat_e][lon_s:lon_e]` — сервер повертає тільки потрібний шматок даних, а не весь глобальний файл
- Отримуємо маленький NetCDF-4 (~1 KB замість ~16 MB на гранулу), відкриваємо через xarray

**Особливості:**
- **Server-side subsetting** — ключова перевага. Для bbox типу Делі (0.6°×0.5°) один запит повертає ~1 KB даних. Без OPeNDAP довелось би завантажувати повний глобальний файл (~16 MB для GLDAS, ~100 MB для GPM)
- Кожна гранула = один HTTP-запит. Для daily datasets (GLDAS — ~7600 днів за 21 рік) це надто багато запитів, тому в prefetch.py беремо тільки 1-е число кожного місяця (~252 запити)
- Різні датасети мають різні сітки (GLDAS 0.25°, GPM 0.1°, MERRA-2 0.5°×0.625°) та різний порядок dims — все стандартизується до `(time, lat, lon)`
- Координати відновлюємо з конфігурації сітки (сервер повертає тільки значення, без lat/lon)
- OMI NO₂ має fill values ~-1e16, які маскуються в NaN
- Потрібна авторизація через NASA Earthdata (логін/пароль в `.env`)

**Швидкість:** ~0.5–2с на гранулу (мережевий latency, не об'єм)

---

### 2) AppEEARS REST API (LP DAAC)

**Датасети:** MODIS LST, NDVI, Burned Area (4 змінні)

**Як працює:**
- Надсилаємо POST-запит із завданням: продукт, шар, bbox (як GeoJSON полігон), період
- Сервер ставить завдання в чергу, вирізає потрібну область з тайлових продуктів MODIS, репроєктує в geographic (lat/lon)
- Полимо статус кожні 30с — `queued → processing → done`
- Завантажуємо результати як GeoTIFF файли (один файл = один timestep)
- Відкриваємо через rioxarray, збираємо в один DataArray по часовій осі

**Особливості:**
- **Async обробка** — це не миттєвий запит. Від submit до done проходить 2–10 хвилин залежно від навантаження серверу і об'єму даних
- Повертає GeoTIFF, а не NetCDF — потрібен `rioxarray` + `rasterio`
- Дата кожного файлу витягується з імені файлу (паттерн `doyYYYYDDD`)
- Найбільші обсяги даних у проєкті — саме тут: Burned Area 500m на великих регіонах = ~2 GB, NDVI 1km = ~350–500 MB
- AppEEARS сам застосовує scale factors для NDVI/LST, тому не потрібно їх множити вручну
- Потрібна авторизація через Earthdata (той самий логін)

**Швидкість:** 2–10 хв на одне завдання (async)

---

### 3) blackmarblepy (LAADS DAAC)

**Датасети:** VIIRS Black Marble VNP46A4 (1 змінна — NTL)

**Як працює:**
- Бібліотека `blackmarblepy` обертає завантаження тайлів VIIRS
- Приймає GeoDataFrame з bbox і список дат, сама визначає потрібні тайли
- Завантажує HDF5-тайли, мозаїчить і обрізає по bbox
- Повертає xarray Dataset, з якого витягуємо перший DataVar → DataArray

**Особливості:**
- **Тайлова мозаїка** — VIIRS порізаний на тайли (як MODIS). Бібліотека автоматично визначає потрібні тайли за bbox, завантажує і зшиває
- Продукт VNP46A4 — річний композит, тому для 2012–2023 це лише 12 файлів, але кожен ~146 MB
- Роздільна здатність 500m — для невеликого bbox типу Делі це помірний обсяг (~900 KB), для великих регіонів може бути десятки MB
- Потрібен окремий NASA Bearer Token (не той самий, що Earthdata логін)

**Швидкість:** ~1–2 хв на рік (залежить від кількості тайлів і швидкості мережі)

---

### 4) NOAA GML (HTTP CSV)

**Датасети:** CO₂ Mauna Loa, CO₂ global, CH₄ global (3 змінні)

**Як працює:**
- Звичайний HTTP GET до CSV-файлу на сайті NOAA
- Парсимо CSV (пропускаємо рядки-коментарі з `#`), будуємо DataArray з dims `(time,)`
- Фільтруємо за датами якщо задано

**Особливості:**
- **Найпростіше джерело** — один HTTP-запит, отримуємо весь ряд одразу
- Це **не gridded дані** — немає lat/lon, тільки часовий ряд (глобальне середнє або одна станція)
- bbox не потрібний і ігнорується
- Маленькі файли (~50 KB), нічого оптимізувати не треба
- Не потрібна авторизація

**Швидкість:** <1с

---

## Datasets

### 1. GLDAS_CLSM025_DA1_D v2.2

GLDAS Catchment Land Surface Model with GRACE data assimilation. Daily, 0.25°.

| Variable | Description | Role |
|----------|-------------|------|
| **GWS_tavg** | Groundwater storage | Primary — human pumping signal |
| **TWS_tavg** | Total water storage (surface + subsurface) | Backup / context |

**Used in:** Water Stress

**Analysis logic:** Compare GWS trend with precipitation trend (GPM). If precipitation is stable but GWS declines → human extraction is the cause.

Source: <https://disc.gsfc.nasa.gov/datasets/GLDAS_CLSM025_DA1_D_2.2/summary>

---

### 2. GPM_3IMERGM v07 (IMERG Final)

Global Precipitation Measurement, monthly, 0.1°.

| Variable | Description | Role |
|----------|-------------|------|
| **precipitation** | Monthly accumulated precipitation | Control variable |

**Used in:** Water Stress, Desertification

Source: <https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGM_07/summary>

---

### 3. OMNO2d (OMI NO₂)

Ozone Monitoring Instrument, daily, 0.25°, 2004–present.

| Variable | Description | Role |
|----------|-------------|------|
| **NO2** (`ColumnAmountNO2TropCloudScreened`) | Tropospheric NO₂ column (cloud-screened) | Primary |

**Used in:** Air Pollution, Urban Growth

**About NO₂:**
- Source: high-temperature fuel combustion (transport, power plants, industry)
- Short-lived → stays near the source → good spatial marker of human activity
- Known effects: weekend drop, COVID-2020 lockdown drop

Source: <https://disc.gsfc.nasa.gov/datasets/OMNO2d_003/summary>

---

### 4. MOD11C3 / MOD11A2 (MODIS LST)

MODIS Land Surface Temperature via AppEEARS. Monthly (MOD11C3) or 8-day (MOD11A2), 2000–present.

| Variable | Description | Role |
|----------|-------------|------|
| **LST_Day** (`LST_Day_1km`) | Daytime land surface temperature | Primary — urban heat signal |
| **LST_Night** (`LST_Night_1km`) | Nighttime land surface temperature | Primary — UHI is strongest at night |

**Used in:** Urban Growth

**Analysis logic:** Compare LST trend in urban core vs surrounding rural area. Growing city → expanding heat island.

Source: <https://lpdaac.usgs.gov/products/mod11c3v061/>

---

### 5. VNP46A4 (VIIRS Black Marble)

VIIRS nighttime lights yearly composites, 500m resolution, 2012–present.

| Variable | Description | Role |
|----------|-------------|------|
| **NTL** | Average nighttime light radiance | Primary — urbanization proxy |

**Used in:** Urban Growth

**About nighttime lights:**
- Direct indicator of urbanization, economic activity, infrastructure expansion
- Can detect city sprawl, new industrial zones, electrification of rural areas

Source: <https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/VNP46A4>

---

### 6. MOD13C2 (MODIS NDVI)

MODIS Vegetation Index, monthly, 0.05°, 2000–present.

| Variable | Description | Role |
|----------|-------------|------|
| **NDVI** | Normalized Difference Vegetation Index (greenness) | Primary — vegetation loss/gain signal |

**Used in:** Deforestation, Desertification

**About NDVI:**
- Measures vegetation density and health (0 = bare soil, 1 = dense green)
- Declining NDVI = vegetation loss (deforestation, overgrazing, drought)
- Compare with precipitation to isolate human cause: NDVI drops + precip stable → human activity

Source: <https://lpdaac.usgs.gov/products/mod13c2v061/>

---

### 7. MCD64A1 (MODIS Burned Area)

MODIS Burned Area product, monthly, 500m, 2000–present.

| Variable | Description | Role |
|----------|-------------|------|
| **Burned_Area** (`Burn_Date`) | Day of burn detection within the month | Primary — fire occurrence |

**Used in:** Wildfires

**About burned area:**
- Detects areas burned by fire each month
- Trend of increasing burned area in many regions (California, Australia, Siberia, Amazon)
- Human causes: land clearing, arson, negligence; amplified by climate conditions

Source: <https://lpdaac.usgs.gov/products/mcd64a1v061/>

---

### 8. M2TMNXAER (MERRA-2 Aerosols)

MERRA-2 aerosol diagnostics, monthly, 0.5°×0.625°, 1980–present.

| Variable | Field | Description | Role |
|----------|-------|-------------|------|
| **Dust** | DUSMASS | Dust surface mass concentration (kg/m³) | Aerosol component |
| **Black_Carbon** | BCSMASS | Black carbon surface mass concentration (kg/m³) | Soot / combustion marker |
| **SO2** | SO2SMASS | SO₂ surface mass concentration (kg/m³) | Coal / industry marker |
| **SO4** | SO4SMASS | SO₄ surface mass concentration (kg/m³) | Secondary aerosol |
| **Organic_Carbon** | OCSMASS | Organic carbon surface mass concentration (kg/m³) | Biomass burning marker |
| **Aerosol_AOT** | TOTEXTTAU | Total aerosol extinction AOT at 550nm (unitless) | Aggregate aerosol load |

**Used in:** Air Pollution

Source: <https://disc.gsfc.nasa.gov/datasets/M2TMNXAER_5.12.4/summary>

---

### 9. NOAA GML Greenhouse Gas Trends

NOAA Global Monitoring Laboratory, monthly time series (no spatial grid).

| Variable | Description | Role |
|----------|-------------|------|
| **CO2_Mauna_Loa** | Atmospheric CO₂ at Mauna Loa (ppm, 1958–present) | Primary — longest CO₂ record |
| **CO2_global** | Global marine surface CO₂ average (ppm, 1979–present) | Global context |
| **CH4_global** | Global marine surface CH₄ average (ppb, 1983–present) | Methane trend |

**Used in:** Greenhouse Gases

Source: <https://gml.noaa.gov/ccgg/trends/>
