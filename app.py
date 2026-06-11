import streamlit as st
import geopandas as gpd
import pandas as pd
import leafmap.foliumap as leafmap
import os
import requests
import json
from folium.plugins import Geocoder
from county_fips import COUNTY_FIPS, FIPS_TO_COUNTY

st.set_page_config(layout="wide", page_title="Indiana Voting District Mapper")

st.title("Indiana Voting District Mapper")
st.markdown("""
This application allows you to visualize various voting districts across Indiana. 
It uses the Indiana GIS REST API with a local fallback for Putnam County specific districts.
""")

# API Configuration
BASE_URL = "https://gisdata.in.gov/server/rest/services/Hosted"
LAYER_CONFIG = {
    "Precincts": {
        "url": f"{BASE_URL}/Voting_District_Boundaries_2024/FeatureServer/1",
        "filter_field": "county",
        "display_field": "p24"
    },
    "County Commissioner": {
        "url": f"{BASE_URL}/Administrative_Boundaries_of_Indiana_Current/FeatureServer/3",
        "filter_field": None, 
        "display_field": "dsplayname"
    },
    "County Council": {
        "url": f"{BASE_URL}/Administrative_Boundaries_of_Indiana_Current/FeatureServer/4",
        "filter_field": None, 
        "display_field": "dsplayname"
    },
    "City Council": {
        "url": None, 
        "filter_field": None,
        "display_field": "city_council_dist"
    },
    "Incorporated Municipalities": {
        "url": f"{BASE_URL}/Administrative_Boundaries_of_Indiana_Current/FeatureServer/0",
        "filter_field": "county", 
        "display_field": "inc_muni"
    },
    "US Congress": {
        "url": f"{BASE_URL}/Congressional_Districts_of_Indiana_Current/FeatureServer/0",
        "filter_field": None, 
        "display_field": "district"
    },
    "State Senate": {
        "url": f"{BASE_URL}/Senate_Districts_of_Indiana_Current/FeatureServer/0",
        "filter_field": None, 
        "display_field": "district"
    },
    "State House": {
        "url": f"{BASE_URL}/House_Districts_of_Indiana_Current/FeatureServer/57",
        "filter_field": None, 
        "display_field": "district_2021"
    },
}

@st.cache_data
def fetch_gis_data(service_url, where_clause="1=1", geometry=None):
    """Fetch data from ArcGIS REST API."""
    if not service_url:
        return None
    params = {
        "where": where_clause,
        "outFields": "*",
        "f": "geojson",
        "outSR": "4326"
    }
    if geometry:
        # Convert envelope to JSON string for API
        params["geometry"] = json.dumps(geometry)
        params["geometryType"] = "esriGeometryEnvelope"
        params["spatialRel"] = "esriSpatialRelIntersects"

    try:
        response = requests.get(f"{service_url}/query", params=params)
        response.raise_for_status()
        data = response.json()
        if 'features' in data and len(data['features']) > 0:
            return gpd.GeoDataFrame.from_features(data, crs="EPSG:4326")
    except Exception as e:
        print(f"API Error: {e}")
    return None

# Sidebar
st.sidebar.header("Mapping Options")
county_list = sorted(list(FIPS_TO_COUNTY.keys()))
selected_county_name = st.sidebar.selectbox("Select County", county_list, index=county_list.index("Putnam") if "Putnam" in county_list else 0)
selected_county_fips = FIPS_TO_COUNTY[selected_county_name]

selected_layer_label = st.sidebar.selectbox("Select District Type", list(LAYER_CONFIG.keys()))
config = LAYER_CONFIG[selected_layer_label]

# Main Logic
with st.spinner(f"Loading {selected_layer_label} for {selected_county_name}..."):
    # 1. Get County Boundary for spatial context
    county_service = f"{BASE_URL}/County_Boundaries_of_Indiana_Current/FeatureServer/0"
    county_where = f"fips = '18{selected_county_fips}'"
    county_gdf = fetch_gis_data(county_service, county_where)
    
    if county_gdf is not None:
        # Convert total_bounds (numpy floats) to native Python floats
        extent = county_gdf.total_bounds # [minx, miny, maxx, maxy]
        envelope = {
            "xmin": float(extent[0]), 
            "ymin": float(extent[1]), 
            "xmax": float(extent[2]), 
            "ymax": float(extent[3]),
            "spatialReference": {"wkid": 4326}
        }
        
        filtered_gdf = None
        used_fallback = False

        # 2. Try API first (if URL exists)
        if config["url"]:
            if config["filter_field"] == "county":
                filtered_gdf = fetch_gis_data(config["url"], where_clause=f"county = '{selected_county_fips}'")
            else:
                filtered_gdf = fetch_gis_data(config["url"], geometry=envelope)
                if filtered_gdf is not None and selected_layer_label in ["County Commissioner", "County Council"]:
                    if 'source_originator' in filtered_gdf.columns:
                        filtered_gdf = filtered_gdf[filtered_gdf['source_originator'].str.contains(selected_county_name, case=False)]

        # 3. Fallback Logic for Putnam County
        if (filtered_gdf is None or filtered_gdf.empty) and selected_county_name == "Putnam":
            fallback_path = "voting_precincts/fallback_boundaries.csv"
            if os.path.exists(fallback_path):
                # Fetch precincts as base geometry
                precinct_url = LAYER_CONFIG["Precincts"]["url"]
                precinct_gdf = fetch_gis_data(precinct_url, where_clause=f"county = '{selected_county_fips}'")
                
                if precinct_gdf is not None:
                    fallback_df = pd.read_csv(fallback_path)
                    # Join geometry with local mapping
                    merged_gdf = precinct_gdf.merge(fallback_df, left_on='p24', right_on='precinct_names', how='left')
                    
                    # Map labels
                    local_col_map = {
                        "County Commissioner": "county_commissioner_dist",
                        "County Council": "county_council_dist",
                        "City Council": "city_council_dist"
                    }
                    target_col = local_col_map.get(selected_layer_label)
                    
                    if target_col and target_col in merged_gdf.columns:
                        # Filter out 'Not in City' for City Council layer
                        if selected_layer_label == "City Council":
                            merged_gdf = merged_gdf[merged_gdf[target_col] != "Not in City"]

                        # Combine precincts into single polygons
                        filtered_gdf = merged_gdf.dissolve(by=target_col).reset_index()
                        display_col = target_col
                        used_fallback = True
                        st.sidebar.info(f"Using local dissolved boundaries for {selected_layer_label}.")
        
        if not used_fallback:
            display_col = config["display_field"]

        # 4. Map display
        if filtered_gdf is not None and not filtered_gdf.empty:
            m = leafmap.Map(center=[39.7684, -86.1581], zoom=7)
            centroid = county_gdf.geometry.unary_union.centroid
            m.set_center(centroid.x, centroid.y, zoom=10 if selected_layer_label != "Incorporated Municipalities" else 11)
            
            # Add address search control using folium Geocoder
            Geocoder().add_to(m)
            
            cmap = "Set1" if selected_layer_label != "Precincts" else "viridis"
            
            if display_col not in filtered_gdf.columns:
                display_col = filtered_gdf.columns[0]

            m.add_gdf(
                filtered_gdf,
                layer_name=selected_layer_label,
                style={'fillOpacity': 0.5, 'weight': 1, 'color': 'black'},
                hover_style={'fillOpacity': 0.7, 'weight': 3},
                column=display_col,
                cmap=cmap
            )
            m.to_streamlit(height=700)
            
            if st.checkbox("Show Data Table"):
                st.write(filtered_gdf.drop(columns='geometry') if 'geometry' in filtered_gdf.columns else filtered_gdf)
        else:
            st.warning(f"No data found for {selected_layer_label} in {selected_county_name}.")
    else:
        st.error(f"Could not find boundary for {selected_county_name}. The server may be having issues.")
