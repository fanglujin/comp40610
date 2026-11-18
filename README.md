# Did pay keep up with prices in Ireland, 2015–2025?

COMP40610 Information Visualisation – interactive visualisation assignment.

## Files

| File | What it is |
|---|---|
| `dashboard.json` | The dashboard: a Vega-Lite 6 specification with the data included. Opens in the [Vega Editor](https://vega.github.io/editor/) or any Vega-Lite 6 viewer. |
| `dashboard.html` | The same specification in a self-contained web page that works offline. |
| `prepare_data.py` | Data preparation: CSO raw files → `monthly.csv`, `quarterly.csv`. |
| `dashboard.py` | Builds `dashboard.json` and `dashboard.html` from the prepared data. |
| `monthly.csv`, `quarterly.csv` | The prepared data. |
| `requirements.txt` | Python packages. |

## Data

- **CSO CPM23** – EU Harmonised Index of Consumer Prices by commodity group, COICOP 2018 (High Value Dataset; primary data).
  <https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/CPM23/CSV/1.0/en>
- **CSO EHQ03** – Earnings and Labour Costs, quarterly (external data, used to measure prices against pay).
  <https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/EHQ03/CSV/1.0/en>

## Reproduce

```
pip install -r requirements.txt
python prepare_data.py path/to/folder/with/CPM23.csv-and-EHQ03.csv
python dashboard.py
```

`dashboard.py` names the views that carry each interaction and binds the interactions to those names.
Altair 6.0 keeps the names as given; later 6.x releases append suffixes to them, which breaks the
bindings, hence the pinned version. `dashboard.json` itself runs in any Vega-Lite 6 viewer.
