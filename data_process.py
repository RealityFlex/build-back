import geopandas as gpd     

def convert_data(path):
    gdf = gpd.read_file(path).to_crs(epsg=4326)
    gdf_json = gdf.to_json()
    return gdf_json
