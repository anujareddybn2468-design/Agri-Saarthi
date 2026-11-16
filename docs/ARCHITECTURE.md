# AgriSaarthi Architecture

AgriSaarthi is a Python Streamlit application. It fetches public agricultural and weather data, runs transparent rule-based analysis, and presents the results in a dashboard.

## Layers

| Layer | Location | Responsibility |
|---|---|---|
| Entry point and UI state | `app.py` | Page setup, sidebar (location, crop, optional NDVI), cached data loading, tab layout |
| Dashboard views | `agri/views.py` | Renders each tab from loaded data; never calls external APIs |
| Charts | `agri/charts.py` | Plotly figures for the forecast and observed history |
| Styling | `assets/style.css`, `.streamlit/config.toml` | Visual theme, cards, badges, responsive rules |
| Data services | `agri/geocoding.py`, `agri/weather.py`, `agri/soil.py` | Call external APIs and convert responses into plain Python and pandas structures |
| HTTP helper | `agri/http_client.py` | Timeouts, HTTP errors and malformed responses become one `ApiError` type |
| Analysis | `agri/risk.py`, `agri/crop_risk.py`, `agri/recommendations.py`, `agri/ndvi.py` | Pure functions: rules, risk levels, crop indicators, advice |
| Reference data | `agri/crops.py` | Preliminary crop profiles (temperature, heat limit, water need, pH range) |

## Data flow

1. The user searches a place name (or types coordinates). `geocoding.search_places` returns candidates.
2. For the chosen location, `app.py` loads three independent sources, each wrapped so a failure only affects its own section:
   - Forecast and current conditions (`weather.fetch_forecast`)
   - Observed 30-day history (`weather.fetch_history`, Open-Meteo archive)
   - Soil properties (`soil.fetch_soil`, ISRIC SoilGrids)
3. `risk.assess_all_risks` scores drought, heat and excessive rainfall. Each result lists its evidence, labelled "Forecast" or "Observed".
4. `crop_risk.assess_crop` produces indicators for the selected crop using the forecast, observed rainfall and soil pH.
5. `advisory_facts.build_facts` collects only the loaded values (missing ones stay null). `advisory.generate_advisory` asks Gemini (`gemini_client.py`) for the seven-part advisory when `GEMINI_API_KEY` is set, and falls back to `advisory_rules.rule_advisory` when Gemini is missing, fails, or quotes a figure not in the facts. The source is shown with the advisory.
6. Mandi prices (`mandi.py`) load only when `DATA_GOV_IN_API_KEY` is set.
7. `views.py` and `advisory_view.py` render the results. Errors appear as notices in the relevant section.

## Caching

Streamlit `st.cache_data` caches successful responses only (exceptions are not cached, so retries happen on the next interaction):

| Data | Time to live |
|---|---|
| Place search | 24 hours |
| Forecast | 15 minutes |
| Observed history | 6 hours |
| Soil | 7 days |

## Design rules

- Forecast and observed evidence are never merged into a single number without a label.
- Every threshold is marked preliminary. Crop reference values are general guidance.
- No yield prediction exists because there is no validated training data.
- Missing data is shown as "unavailable", never filled with estimates.
- NDVI is only interpreted when the user enters a value. No satellite feed is connected.

## External services

| Service | Used for | Key required |
|---|---|---|
| Open-Meteo geocoding | Place search | No |
| Open-Meteo forecast | Current conditions, 7-day forecast | No |
| Open-Meteo archive | Observed 30-day history | No |
| ISRIC SoilGrids v2.0 | Soil properties (0-5 cm mean) | No |
| Google Gemini (optional) | Written advisory text from collected facts | `GEMINI_API_KEY` |
| data.gov.in daily market prices (optional) | Mandi prices | `DATA_GOV_IN_API_KEY` |

## Testing

- `tests/test_analysis.py`: risk rules, crop indicators, NDVI bands, recommendations (synthetic inputs).
- `tests/test_services.py`: parsing of API response shapes, with network calls replaced by fixtures.

Run with `python -m pytest tests`.

## Possible next steps

- Connect a satellite NDVI source (for example Sentinel-2 via Copernicus Data Space) with credentials.
- Validate thresholds and crop profiles against local extension data.
- Add saved farm profiles once user accounts are introduced.
