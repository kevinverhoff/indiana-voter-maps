# Indiana Voting District Mapper

A Streamlit application to visualize voting districts (Precincts, US Congress, State Senate, and State House) for Indiana counties.

## Features
- Select any Indiana county to filter the map.
- View different geographic layers:
    - Precincts
    - US Congressional Districts
    - State Senate Districts
    - State House Districts
- Upload local mapping CSVs to visualize custom districts (e.g., County Council, Commissioner Districts, Wards).
- Interactive maps with hover and search functionality.

## Data Requirements
Due to file size limits, the primary shapefile is not included in this repository.
1. Download the **Voting District Boundaries 2023** (or latest) from the [Indiana Geographic Information Office](https://www.in.gov/itp/data-and-statistics/geographic-information-office/indiana-gis-data-harvest/).
2. Place the extracted `Voting_District_Boundaries_2023` folder in the parent directory of this project (or update `SHAPEFILE_PATH` in `app.py`).

## Installation
1. Clone this repository.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application:
   ```bash
   streamlit run app.py
   ```

## Custom Mapping
You can join local data by uploading a CSV. The CSV must contain a column that matches the precinct names (the `p23` column in the shapefile).
