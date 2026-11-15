# Звіт: Data Access Layer

## Що зроблено

Створено модуль `data_access.py` — єдина точка доступу до всіх NASA-даних для команди.

### Інтерфейс

Одна функція для всього:

```python
from data_access import get_data

da = get_data("NDVI", "2015-01-01", "2023-12-31", bbox=(76.8, 28.4, 77.4, 28.9))
da = get_data("CO2_Mauna_Loa", "2000-01-01", "2023-12-31")  # без bbox
```

Повертає `xarray.DataArray` з dims `(time, lat, lon)`, відсортований за часом, з `datetime64` на осі часу. Для глобальних рядів (CO₂, CH₄) — dims `(time,)`.

### Джерела даних (4)

| Джерело | Бібліотека | Що завантажує | Метод |
|---------|-----------|---------------|-------|
| GES DISC | `earthaccess` + OPeNDAP | GLDAS, GPM, OMI, MERRA-2 | DAP4 server-side subsetting (~1 KB/granule) |
| LP DAAC | AppEEARS REST API | MODIS LST, NDVI, Burned Area | async обробка (2–5 хв) |
| LAADS DAAC | `blackmarblepy` | VIIRS Nighttime Lights | tile download (~146 MB/рік) |
| NOAA GML | HTTP CSV | CO₂, CH₄ глобальні ряди | пряме завантаження (<1с) |

### Змінні (18 шт., всі протестовані)

**earthaccess (10):**
- `GWS_tavg` — запаси підземних вод (mm)
- `TWS_tavg` — загальні запаси води (mm)
- `precipitation` — місячні опади (mm/hr)
- `NO2` — тропосферний NO₂ (molec/cm²)
- `Dust` — пил, поверхнева концентрація (kg/m³)
- `Black_Carbon` — чорний вуглець (kg/m³)
- `SO2` — діоксид сірки (kg/m³)
- `SO4` — сульфати (kg/m³)
- `Organic_Carbon` — органічний вуглець (kg/m³)
- `Aerosol_AOT` — аерозольна оптична товщина (безрозмірна)

**AppEEARS (4):**
- `NDVI` — індекс вегетації, місячний 1km
- `LST_Day` — денна температура поверхні, 8-денний 1km
- `LST_Night` — нічна температура поверхні, 8-денний 1km
- `Burned_Area` — дата пожежі, місячний 500m

**blackmarblepy (1):**
- `NTL` — нічне освітлення, річний композит 500m

**NOAA (3):**
- `CO2_Mauna_Loa` — CO₂ Мауна-Лоа (ppm, з 1958)
- `CO2_global` — CO₂ глобальне середнє (ppm, з 1979)
- `CH4_global` — CH₄ глобальне середнє (ppb, з 1983)

### Preprocessing (вже вбудований)

- earthaccess (OPeNDAP): дати з метаданих гранул, координати з grid config, стандартизація dims
- OMI NO₂: маскування fill values (-1e16 → NaN)
- NTL: конвертація Dataset → DataArray
- Всі джерела: dims завжди `(time, lat, lon)`, `.sortby("time")`

### Що НЕ робимо в data_access (свідомий вибір)

- LST Kelvin → °C — конвертація залежить від задачі аналітика
- Burned Area агрегація (день пожежі → % площі) — логіка аналізу, не завантаження
- Scale factors для NDVI/LST — AppEEARS вже застосовує їх автоматично

---

## Дослідження (7)

Кожне дослідження = одне явище + один яскравий регіон.

| # | Явище | Регіон | Період | Змінні | Гіпотеза |
|---|-------|--------|--------|--------|----------|
| 1 | Water Stress | Punjab, India | 2003–2023 | GWS_tavg, precipitation | GWS падає при стабільних опадах → людина качає воду |
| 2 | Urban Growth | Delhi, India | 2012–2023 | NTL, LST_Day, LST_Night, NO2 | Світло, тепло, NO₂ ростуть разом → місто розширюється |
| 3 | Air Pollution | Beijing, China | 2005–2023 | NO2, SO2, Black_Carbon, Aerosol_AOT | Спад після 2013 (політика) + різкий провал COVID-2020 |
| 4 | Deforestation | Rondônia, Brazil | 2001–2023 | NDVI | NDVI падає → ліс вирубують під пасовища |
| 5 | Wildfires | SE Australia | 2001–2023 | Burned_Area | Площа пожеж зростає, пік 2019–2020 Black Summer |
| 6 | Desertification | Sahel | 2001–2023 | NDVI, precipitation | NDVI падає при стабільних опадах → перевипас/переорювання |
| 7 | Greenhouse Gases | Global | 1980–2023 | CO2_Mauna_Loa, CO2_global, CH4_global | CO₂ і CH₄ стабільно ростуть |

Конфігурація в коді: `INVESTIGATIONS`, `PHENOMENA`, `REGIONS` — три окремі словники в `data_access.py`.
Детальний опис: `investigations.md`.

---

## Бачення аналізу (наступні кроки)

### 1. Trend Analysis Pipeline

Для кожного дослідження:
1. **Завантажити дані** — `get_data()` вже готовий
2. **Агрегувати в часовий ряд** — spatial mean по bbox на кожен timestep → одномірний ряд `(time,)`
3. **Обчислити тренд:**
   - Linear regression → slope (швидкість зміни за рік)
   - Mann-Kendall test → p-value (статистична значущість)
   - Confidence interval для slope
4. **Порівняти змінні** — якщо GWS падає, а precipitation стабільний → людський фактор підтверджено

### 2. Візуалізація

Для кожного дослідження:
- **Time series plot** — лінія + тренд + confidence band
- **Comparison plot** — дві змінні на одному графіку (GWS vs precipitation)
- **Map** — регіон на карті + heatmap останнього значення

### 3. Логіка висновку

Кожне явище має "контрольну змінну":
- Water Stress: precipitation = контроль. Якщо precipitation stable + GWS declining → **human cause confirmed**
- Desertification: precipitation = контроль. NDVI declining + precipitation stable → **human cause confirmed**
- Air Pollution: trend direction + COVID dip presence → **policy/human activity link**
- Інші: trend presence + significance → **human impact detected**

### 4. Фронтенд

Користувач обирає явище → бачить:
- Карту з регіоном
- Часовий ряд з трендом
- Статистику (slope, p-value, "значущий" / "не значущий")
- Пояснення простою мовою ("Groundwater in Punjab drops by X mm per year...")

---

## Важливо: офлайн-дані для презентації

На презентації не буде часу чекати на завантаження (AppEEARS — 2–5 хв, NTL — 146 MB/рік). **Треба заздалегідь завантажити всі дані локально.**

Скрипт `prefetch.py` вже написаний:
1. Проходить по всіх `INVESTIGATIONS` і викликає `get_data()` для кожної змінної з потрібним bbox і періодом
2. Зберігає результати як `.nc` (NetCDF) файли в папку `data/`
3. Пропускає вже завантажені змінні (skip-if-exists)
4. Для daily datasets (GLDAS, OMI) бере 1-е число кожного місяця (обмеження кількості HTTP-запитів)

Орієнтовний обсяг даних на всі 7 досліджень: **~3 GB** (основний вклад — AppEEARS продукти: Burned Area 500m, NDVI 1km на великих регіонах). earthaccess-змінні через OPeNDAP займають лише ~5 MB сумарно.

---

## Файли проєкту

```
data_access.py          — модуль завантаження (головний файл, OPeNDAP для earthaccess)
prefetch.py             — скрипт попереднього завантаження даних для офлайн-демо
datasets.md             — довідник датасетів та змінних (EN)
Датасети та змінні.md   — довідник датасетів (UA, початковий)
investigations.md       — опис досліджень
CLAUDE.md               — контекст проєкту
test_data_access.ipynb  — тестовий ноутбук
.env                    — credentials (не комітити!)
.data_cache/            — кеш завантажених файлів (AppEEARS)
data/                   — prefetch-дані для офлайн-демо (не комітити!)
```
