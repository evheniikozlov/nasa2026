# NASA Trend Detector

## Project Overview

Hackathon project for **NASA Space Apps Challenge**. The tool allows users to select Earth science variables, visualize how they change over time in a specific region, and perform statistical trend analysis (rate of change, significance testing via Mann-Kendall / t-test / confidence intervals).

## Focus

Human activity impact on the Earth system. The app is organized around **phenomena** — each phenomenon groups multiple variables that together tell one story.

### Core Phenomena (7)

1. **Water Stress** — groundwater depletion vs stable precipitation → human pumping (GLDAS + GPM)
2. **Urban Growth** — nighttime lights + heat island + NO₂ rising together → city expansion (VIIRS + MODIS LST + OMI)
3. **Air Pollution** — NO₂ + aerosol trends, COVID lockdown drop (OMI + MERRA-2)
4. **Deforestation** — vegetation index declining → forest loss (MODIS NDVI)
5. **Wildfires** — burned area increasing over time (MODIS Burned Area)
6. **Desertification** — vegetation declining + precipitation stable → overgrazing/overfarming (MODIS NDVI + GPM)
7. **Greenhouse Gases** — CO₂ and CH₄ steady upward trends (NOAA GML)

## Target Audience

High school / college students and scientifically curious public. UI should explain variables in simple terms.

## Key Requirements

- Interactive region selection (at minimum from a curated list, ideally on a map)
- Time series visualization with interactive charts
- Statistical trend analysis: slope, p-value, significance indicator
- Extensible architecture — adding a new dataset should be a config change, not a rewrite

## Tech Stack

TBD

## Data Sources

See `datasets.md` for the finalized list of datasets and variables.

## Language

Application UI — English. Internal team communication — Ukrainian.
