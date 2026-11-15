# NASA Trend Detector

Hackathon project for NASA Space Apps Challenge. Аналіз впливу людської діяльності на Земну систему через супутникові дані NASA.

## Quick Start

### 1. Credentials

Зареєструйся на [NASA Earthdata](https://urs.earthdata.nasa.gov/users/new), скопіюй `.env.example` → `.env` і заповни:

```bash
cp .env.example .env
# відредагуй .env — впиши логін, пароль і bearer token
```

### 2. Залежності

```bash
pip install earthaccess xarray numpy pandas geopandas requests shapely python-dotenv h5netcdf rioxarray blackmarblepy
```

### 3. Отримання даних

Одна функція для всього:

```python
from data_access import get_data

# Gridded дані — потрібен bbox (west, south, east, north)
da = get_data("GWS_tavg", "2010-01-01", "2023-12-31", bbox=(73.8, 29.5, 76.9, 32.5))

# Глобальні часові ряди — без bbox
da = get_data("CO2_Mauna_Loa", "2000-01-01", "2023-12-31")
```

Повертає `xarray.DataArray`:
- Gridded: dims `(time, lat, lon)`, координати в градусах, час `datetime64`
- Глобальні: dims `(time,)`

### 4. Prefetch для офлайн-демо

Завантажити всі дані для 7 досліджень наперед (~3 GB):

```bash
python prefetch.py --list     # подивитись план
python prefetch.py             # завантажити все
python prefetch.py water_stress  # одне дослідження
```

Дані зберігаються в `data/{investigation}/{variable}.nc`. Пропускає вже завантажені.

## Змінні (18)

| Джерело | Змінні | Метод |
|---------|--------|-------|
| earthaccess + OPeNDAP | `GWS_tavg`, `TWS_tavg`, `precipitation`, `NO2`, `Dust`, `Black_Carbon`, `SO2`, `SO4`, `Organic_Carbon`, `Aerosol_AOT` | Server-side subsetting, ~1 KB/запит |
| AppEEARS | `NDVI`, `LST_Day`, `LST_Night`, `Burned_Area` | Async обробка, 2–10 хв |
| blackmarblepy | `NTL` | Tile download, ~1–2 хв/рік |
| NOAA CSV | `CO2_Mauna_Loa`, `CO2_global`, `CH4_global` | HTTP, <1с |

Повний опис змінних і джерел: [`datasets.md`](datasets.md)

## Дослідження (7)

| Явище | Регіон | Змінні | Гіпотеза |
|-------|--------|--------|----------|
| Water Stress | Punjab, India | GWS_tavg, precipitation | Підземні води падають при стабільних опадах |
| Urban Growth | Delhi, India | NTL, LST_Day, LST_Night, NO2 | Світло, тепло, NO₂ ростуть разом |
| Air Pollution | Beijing, China | NO2, SO2, Black_Carbon, Aerosol_AOT | Спад після 2013 + провал COVID-2020 |
| Deforestation | Rondonia, Brazil | NDVI | NDVI падає — ліс вирубують |
| Wildfires | SE Australia | Burned_Area | Площа пожеж зростає, пік 2019–2020 |
| Desertification | Sahel | NDVI, precipitation | Рослинність падає при стабільних опадах |
| Greenhouse Gases | Global | CO2_Mauna_Loa, CO2_global, CH4_global | CO₂ і CH₄ стабільно ростуть |

Детальний опис з гіпотезами: [`investigations.md`](investigations.md)

## Структура проєкту

```
data_access.py          — модуль завантаження даних (головний файл)
                           get_data() → xarray.DataArray
                           4 джерела: earthaccess/OPeNDAP, AppEEARS, blackmarblepy, NOAA
                           конфіги: PHENOMENA, REGIONS, INVESTIGATIONS

prefetch.py             — скрипт попереднього завантаження для офлайн-демо
                           зберігає .nc файли в data/

datasets.md             — довідник: датасети, змінні, як працює кожне джерело
investigations.md       — опис 7 досліджень з гіпотезами
REPORT.md               — звіт про пророблену роботу та бачення аналізу

test_data_access.ipynb  — тестовий ноутбук

.env                    — credentials (НЕ комітити!)
.env.example            — шаблон для .env
data/                   — prefetch-дані (НЕ комітити!)
.data_cache/            — кеш AppEEARS (НЕ комітити!)
```

## Як додати нову змінну

1. Додати конфіг в відповідний словник (`EARTHACCESS_VARIABLES`, `APPEEARS_VARIABLES`, тощо) в `data_access.py`
2. Для earthaccess — переконатись що датасет є в `_GRIDS` (або додати новий grid)
3. Додати змінну в `PHENOMENA` якщо вона належить до існуючого явища
4. `get_data("new_variable", ...)` — працює автоматично
