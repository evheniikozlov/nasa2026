# Project Details

**Project Name:**

EarthPulse: A Tool for Detecting Human Impact on Earth Through NASA Satellite Data Trends

**Project Details:**

**What it does:**
EarthPulse is a data analysis tool that lets users explore how human activity shapes the Earth system. Users choose one of 7 phenomena — Water Stress, Urban Growth, Air Pollution, Deforestation, Wildfires, Desertification, or Greenhouse Gases — select any region on the globe, and the tool fetches relevant NASA satellite data, builds time series, computes statistical trends (linear regression slope, Mann-Kendall significance test, confidence intervals), and presents the results as interactive charts with plain-language explanations. The tool covers 9 NASA and NOAA datasets and 18 Earth science variables in total. To showcase the tool's capabilities, we include pre-configured investigations in regions where each effect is especially vivid — groundwater depletion in Punjab, rapid urbanization in Delhi, the impact of China's 2013 clean air policies in Beijing, deforestation in Rondônia, the 2019–2020 Black Summer fires in SE Australia, and land degradation in the Sahel.

**How it works:**
The tool applies two complementary analytical approaches depending on the phenomenon. For some, like Water Stress and Desertification, it compares a "signal" variable with a "control" variable — if groundwater storage drops while precipitation stays stable, the cause is human pumping, not drought. For others, like Urban Growth or Air Pollution, it tracks multiple correlated indicators together — nighttime lights, surface temperature, and NO₂ all rising in the same area is strong evidence of urbanization. In every case, trends are backed by statistical testing (slope, p-value, significance), making the conclusions data-driven rather than anecdotal.

Technically, a unified data access layer routes every request to one of 4 NASA data sources: GES DISC via OPeNDAP server-side subsetting (GLDAS, GPM, OMI, MERRA-2), LP DAAC AppEEARS REST API (MODIS LST, NDVI, Burned Area), LAADS DAAC via blackmarblepy (VIIRS Nighttime Lights), and NOAA GML CSV endpoints (CO₂, CH₄). Regardless of the source, data is returned in a standardized format with consistent dimensions (time, latitude, longitude), ready for analysis. The architecture is config-driven — adding a new dataset or variable requires only a configuration entry, not a code rewrite.

**Benefits:**
- Turns complex, multi-source satellite data into clear, accessible evidence of human impact on the environment.
- Groups multiple variables into coherent "phenomena" that tell a story — for example, a user doesn't just see that NO₂ is declining in Beijing, they see it alongside SO₂, black carbon, and aerosol optical thickness all declining together, with a visible COVID-2020 lockdown dip.
- Works for any region on Earth, not just pre-selected examples, so users can investigate their own city or country.
- Statistical rigor: every trend comes with a p-value and significance indicator, teaching users the difference between a real trend and noise.
- Designed for high school and college students — variables are explained in simple terms, and the interface guides users through the analysis without requiring a scientific background.

**Intended impact and results:**
Our goal was to make NASA's open Earth science data tangible and meaningful for non-experts — to bridge the gap between raw satellite archives and the question "what is humanity doing to the planet?" We achieved a working tool that ingests data from 9 different datasets across 4 NASA data centers, standardizes it into a common format, and produces statistically rigorous trend analyses for 7 distinct environmental phenomena. The showcase investigations confirm real-world signals: declining groundwater in Punjab despite stable rainfall, expanding nighttime lights and heat islands in Delhi, measurable pollution drops after China's clean-air legislation, progressive deforestation in the Amazon, worsening wildfire seasons in Australia, and the relentless rise of atmospheric CO₂ and CH₄.

**Tools, languages, and technologies:**
- Language: Python
- Data handling: xarray, NumPy, pandas, GeoPandas, rioxarray
- NASA data access: earthaccess (with OPeNDAP DAP4 protocol), AppEEARS REST API, blackmarblepy
- Data formats: NetCDF-4, HDF5, GeoTIFF, CSV
- Statistical analysis: SciPy (linear regression, Mann-Kendall test)
- Visualization: Matplotlib, Plotly
- Data sources: GLDAS, GPM IMERG, OMI, MERRA-2, MODIS (LST, NDVI, Burned Area), VIIRS Black Marble, NOAA GML
