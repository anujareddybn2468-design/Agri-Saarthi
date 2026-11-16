# AgriSaarthi

**Predict Climate Risks. Protect Crops. Empower Farmers.**

AgriSaarthi is an agricultural climate intelligence dashboard. Enter a village, town or district and it shows current weather, a 7-day forecast, observed rainfall and temperature history, estimated soil properties, explainable climate risks, crop-specific risk indicators and practical recommendations.

## Features

- **Location search:** village, town or district lookup, or direct latitude and longitude entry.
- **Weather:** current temperature, humidity, rainfall and wind, plus a 7-day forecast (Open-Meteo).
- **Climate risks:** drought, heat stress and excessive rainfall, each with the evidence behind its level. Forecast and observed evidence are labelled separately.
- **Soil:** SoilGrids estimates (pH, clay, sand, organic carbon, nitrogen, cation exchange capacity) with an explanation of why each matters. Missing values are shown as unavailable.
- **Crops:** rice, wheat, maize, ragi (finger millet), cotton and tomato, with temperature, heat, water, excess rain and pH indicators.
- **AI advisory:** a seven-part farm advisory (status, top priority, weather, crop actions, next 7 days, preventive measures, data confidence). Written by Gemini AI when a key is configured, otherwise by the rule-based engine. The source is always labelled.
- **Mandi prices:** wholesale prices for the selected crop and state from data.gov.in, with the source and fetch time shown. Needs a free data.gov.in key.
- **Optional NDVI:** interpret a vegetation index value you enter.
- **Method and limits:** data sources, every rule and its points, and known limitations.

All thresholds and crop reference values are **preliminary** and have not been validated locally. AgriSaarthi does not make yield predictions, because no validated training data is available.

## Setup

Requirements: Python 3.10 or newer and an internet connection.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Optional keys

Set these as environment variables or in `.streamlit/secrets.toml`. Without them the app still works, using the rule-based advisory and showing mandi prices as not connected.

- `GEMINI_API_KEY`: enables Gemini-written advisory text.
- `DATA_GOV_IN_API_KEY`: enables mandi prices.

## Run the app

```bash
streamlit run app.py
```

Open the address Streamlit prints (usually http://localhost:8501).

## Run the tests

```bash
python -m pytest tests
```

The tests use synthetic fixtures and do not call the internet.

## Project structure

```
app.py                  Streamlit entry point (sidebar, data loading, tabs)
agri/
  views.py              Dashboard tab renderers
  charts.py             Plotly charts
  geocoding.py          Place search (Open-Meteo)
  weather.py            Forecast and observed history (Open-Meteo)
  soil.py               Soil properties (SoilGrids)
  http_client.py        Shared request helper and error type
  risk.py               Climate risk engine
  crop_risk.py          Crop-specific indicators
  crops.py              Preliminary crop reference profiles
  recommendations.py    Rule-based advice
  ndvi.py               Optional NDVI interpretation
assets/style.css        Custom styling
.streamlit/config.toml  Theme
tests/                  Unit and parsing tests
docs/ARCHITECTURE.md    Architecture and data flow
```

See `docs/ARCHITECTURE.md` for how the layers fit together.

## Data sources

| Source | Used for | Notes |
|---|---|---|
| Open-Meteo geocoding | Place search | Free, no key |
| Open-Meteo forecast | Current conditions and 7-day forecast | Free, no key |
| Open-Meteo archive | Observed 30-day history | Ends 5 days before today |
| ISRIC SoilGrids v2.0 | Soil properties, 0-5 cm | Model estimates on a 250 m grid, not field tests |

If a service is slow or unavailable, the affected section shows a notice and the rest of the dashboard still works.

## Limitations

- Forecasts are model predictions and can be wrong.
- Soil values are estimates, not laboratory tests on your field.
- NDVI is not fetched automatically. Enter a value if you have one.
- Risk thresholds and crop profiles need validation against local extension data before real decisions.
- Recommendations are general. Confirm with a local agricultural extension officer or Krishi Vigyan Kendra.
