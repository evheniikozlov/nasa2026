# Investigations

Each investigation = one phenomenon + one region where the effect is most visible.

## 1. Water Stress — Punjab, India

**Hypothesis:** Groundwater declines while precipitation stays stable → human pumping for irrigation.

- **Region:** Punjab (73.8°E, 29.5°N, 76.9°E, 32.5°N)
- **Period:** 2003–2023 (GLDAS available from Feb 2003)
- **Variables:**
  - `GWS_tavg` — groundwater storage trend (expect decline)
  - `precipitation` — control variable (expect no significant trend)
- **Why Punjab:** One of the most dramatic groundwater depletion zones on Earth. Green Revolution farming relies on tube wells; GRACE satellite data shows massive water table drop.

---

## 2. Urban Growth — Delhi, India

**Hypothesis:** Nighttime lights expand, heat island grows, NO₂ rises → rapid urbanization.

- **Region:** Delhi (76.8°E, 28.4°N, 77.4°E, 28.9°N)
- **Period:** 2012–2023 (VIIRS NTL available from 2012)
- **Variables:**
  - `NTL` — nighttime light radiance (expect increase + spatial expansion)
  - `LST_Day` — daytime land surface temperature (expect warming in urban core)
  - `LST_Night` — nighttime LST (expect stronger warming — UHI effect)
  - `NO2` — tropospheric NO₂ (expect increase from traffic/industry)
- **Why Delhi:** Population doubled in 20 years. Massive construction, expanding metro area, visible heat island.

---

## 3. Air Pollution — Beijing, China

**Hypothesis:** NO₂ and aerosols show long-term decline due to clean air policies, with a sharp COVID-2020 drop.

- **Region:** Beijing (116.0°E, 39.6°N, 116.8°E, 40.2°N)
- **Period:** 2005–2023 (OMI available from 2004)
- **Variables:**
  - `NO2` — tropospheric NO₂ (expect decline post-2013 policies + COVID dip)
  - `SO2` — SO₂ surface concentration (expect decline — coal plant regulations)
  - `Black_Carbon` — soot (expect decline)
  - `Aerosol_AOT` — total aerosol optical thickness (expect decline)
- **Why Beijing:** China's "war on pollution" from 2013 is one of the largest air quality interventions in history. COVID-2020 lockdown provides a natural experiment.

---

## 4. Deforestation — Rondônia, Brazil

**Hypothesis:** Vegetation index declines as tropical forest is cleared for cattle ranching and agriculture.

- **Region:** Rondônia (-65.0°W, -13.5°S, -60.0°W, -8.0°S)
- **Period:** 2001–2023 (MODIS NDVI available from 2000)
- **Variables:**
  - `NDVI` — vegetation index (expect decline in deforested areas)
- **Why Rondônia:** The "fishbone" deforestation pattern along roads is one of the most iconic examples of human-driven land use change. Visible from space.

---

## 5. Wildfires — SE Australia

**Hypothesis:** Burned area increases over time, with a dramatic peak during the 2019–2020 Black Summer.

- **Region:** SE Australia (147.0°E, -38.0°S, 153.0°E, -33.0°S)
- **Period:** 2001–2023 (MCD64A1 available from 2000)
- **Variables:**
  - `Burned_Area` — burn date detection per pixel (aggregate to monthly burned fraction)
- **Why SE Australia:** The 2019–2020 Black Summer burned 18.6 million hectares — unprecedented in modern records. Clear trend of worsening fire seasons.

---

## 6. Desertification — Sahel

**Hypothesis:** Vegetation declines while precipitation stays stable → overgrazing and overfarming degrade the land.

- **Region:** Sahel, Niger/Nigeria border (2.0°E, 11.0°N, 10.0°E, 16.0°N)
- **Period:** 2001–2023 (MODIS NDVI from 2000, GPM from 2000)
- **Variables:**
  - `NDVI` — vegetation index (expect decline)
  - `precipitation` — control variable (expect stable or slight increase)
- **Why Sahel:** Transition zone between Sahara and savanna. Population pressure drives overgrazing. Separating climate from human causes is the key analytical challenge.

---

## 7. Greenhouse Gases — Global

**Hypothesis:** CO₂ and CH₄ show steady upward trends driven by fossil fuel combustion, agriculture, and waste.

- **Region:** Global (no bbox — single station / marine average)
- **Period:** 1980–2023
- **Variables:**
  - `CO2_Mauna_Loa` — atmospheric CO₂ at Mauna Loa (expect ~2 ppm/year rise)
  - `CO2_global` — global marine surface average
  - `CH4_global` — global methane (expect rise, acceleration after 2007)
- **Why global:** Greenhouse gases are well-mixed in the atmosphere — a single time series tells the global story.
