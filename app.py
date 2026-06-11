import streamlit as st
import geopandas as gpd
import pandas as pd
import leafmap.foliumap as leafmap
import os
from county_fips import COUNTY_FIPS, FIPS_TO_COUNTY

st.set_page_config(layout="wide", page_title="Indiana Voting District Mapper")

st.title("Indiana Voting District Mapper")
st.markdown("""
This application allows you to visualize various voting districts across Indiana. 
Select a county and the type of district you want to map.
""")

# Path to the shapefile (should be in the root or a data folder)
SHAPEFILE_PATH = "../Voting_District_Boundaries_2023/Voting_District_Boundaries_2023.shp"

@st.cache_data
def load_data(path):
    if not os.path.exists(path):
        return None
    gdf = gpd.read_file(path)
    # Convert to WGS84 for mapping
    gdf = gdf.to_crs(epsg=4326)
    return gdf

# Sidebar for selections
st.sidebar.header("Mapping Options")

county_list = sorted(list(FIPS_TO_COUNTY.keys()))
selected_county_name = st.sidebar.selectbox("Select County", ["All Counties"] + county_list)

layer_options = {
    "Precincts (p23)": "p23",
    "US Congress (c)": "c",
    "State Senate (s)": "s",
    "State House (h)": "h"
}
selected_layer_label = st.sidebar.selectbox("Select District Type", list(layer_options.keys()))
selected_column = layer_options[selected_layer_label]

st.sidebar.markdown("---")
st.sidebar.header("Local Data Integration")
uploaded_file = st.sidebar.file_uploader("Upload local mapping CSV (optional)", type="csv")
st.sidebar.info("CSV should have a column 'precinct_names' matching the 'p23' field and your district columns.")

# Main Logic
gdf = load_data(SHAPEFILE_PATH)

if gdf is None:
    st.error(f"Shapefile not found at {SHAPEFILE_PATH}. Please ensure the data is available.")
    st.stop()

# Filtering
if selected_county_name != "All Counties":
    fips = FIPS_TO_COUNTY[selected_county_name]
    filtered_gdf = gdf[gdf['county'] == fips].copy()
else:
    filtered_gdf = gdf.copy()

# Join local data if uploaded
if uploaded_file is not None:
    local_df = pd.read_csv(uploaded_file)
    join_col = st.sidebar.selectbox("Select join column in CSV (precinct names)", local_df.columns)
    map_col = st.sidebar.selectbox("Select district column to map", local_df.columns)
    
    filtered_gdf = filtered_gdf.merge(local_df, left_on='p23', right_on=join_col, how='left')
    display_col = map_col
else:
    display_col = selected_column

# Map display
m = leafmap.Map(center=[39.7684, -86.1581], zoom=7)

if not filtered_gdf.empty:
    # Set center to the filtered data
    centroid = filtered_gdf.geometry.unary_union.centroid
    m.set_center(centroid.x, centroid.y, zoom=10 if selected_county_name != "All Counties" else 7)
    
    m.add_gdf(
        filtered_gdf,
        layer_name=selected_layer_label,
        style={'fillOpacity': 0.5, 'weight': 1, 'color': 'black'},
        hover_style={'fillOpacity': 0.7, 'weight': 3},
        column=display_col,
        cmap="Set1"
    )

m.to_streamlit(height=700)

# Data Table
if st.checkbox("Show Data Table"):
    st.write(filtered_gdf.drop(columns='geometry'))
