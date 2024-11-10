import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString
from scipy.spatial import cKDTree
import json
import numpy as np
from tqdm import tqdm
import pandas as pd
from pathlib import Path
from street_graph import (create_graph, add_places_to_graph, calculate_population, summarize_traffic_data,
                          assign_routes_to_population, calculate_population_loads, update_weights, plot_heatmap, add_population_column_to_houses, cpu_shortest_path_usage, plot_street_usage)


users_data = {}

def find_shapefile(directory, keyword=None):
    """Ищет первый файл .shp в директории с опциональной фильтрацией по ключевому слову"""
    for file in Path(directory).glob("*.shp"):
        if keyword is None or keyword.lower() in file.stem.lower():
            return str(file)
    return None

def find_routes_and_places(folder_path, id, version, lat=37.495, long=55.555):
    """Загружает файлы маршрутов и местоположений"""
    folder_path = Path(folder_path)
    print(id, version)

    if id in users_data.keys():
        houses = users_data[id][version]['houses']
        buses = users_data[id][version]['buses']
        streets = users_data[id][version]['streets']

    else:
        # Ищем shapefiles в папке
        files = {
            "Street": find_shapefile(folder_path / "streets")
        }

        house_path = find_shapefile(folder_path / "buildings")
        stations = find_shapefile(folder_path / "stations")

        print(f"House path: {house_path}")
        print(f"Stations path: {stations}")

        houses = gpd.read_file(house_path).to_crs(epsg=4326)
        houses["Apartments"] = houses["Apartments"].fillna(0) 
        buses = gpd.read_file(stations).to_crs(epsg=4326)
        streets = gpd.GeoDataFrame(pd.concat([gpd.read_file(path).to_crs(epsg=4326).query("Foot == 1")
                                        for path in files.values()], ignore_index=True)).loc[lambda df: df.geometry.type == 'LineString']

        users_data[id] = {version: {}}
        users_data[id][version]['houses'] = houses
        users_data[id][version]['buses'] = buses
        users_data[id][version]['streets'] = streets

    point = gpd.GeoDataFrame(geometry=[Point(lat, long)], crs="EPSG:4326").to_crs(epsg=3857)
    radius = 1500

    houses = houses.to_crs(epsg=3857)
    buses = buses.to_crs(epsg=3857)
    streets = streets.to_crs(epsg=3857)

    houses = houses[houses.geometry.distance(point.geometry.iloc[0]) <= radius]
    buses = buses[buses.geometry.distance(point.geometry.iloc[0]) <= radius]
    streets = streets[streets.geometry.distance(point.geometry.iloc[0]) <= radius]

    houses = houses.to_crs(epsg=4326)
    buses = buses.to_crs(epsg=4326)
    streets = streets.to_crs(epsg=4326)

    houses = add_population_column_to_houses(houses)

    G, nodes = create_graph(streets)
    node_coords = np.array(nodes)
    tree = cKDTree(node_coords)

    add_places_to_graph(houses, G, tree, node_coords, 'house')
    add_places_to_graph(buses, G, tree, node_coords, 'bus_stop')

    # def find_shortest_paths_to_bus_stops(houses, buses, G):
    #     house_locations = []
    #     bus_stops = {tuple(bus.geometry.coords[0]): bus for _, bus in buses.iterrows()}
    #     routes = {}
        
    #     # Проходим по всем домам
    #     for house in tqdm(houses.iterrows(), desc="Finding shortest paths"):
    #         house_point = house[1]  # house[1] это сам объект серии (строки), а не индекс
    #         house_location = (house_point.geometry.centroid.x, house_point.geometry.centroid.y)  # Извлекаем координаты
            
    #         house_locations.append(house_location)
            
    #         # Находим ближайшую автобусную остановку
    #         nearest_bus_stop = min(bus_stops.keys(), key=lambda bus: Point(house_location).distance(Point(bus_stops[bus].geometry)))

    #         # Проверяем наличие пути между домом и ближайшей остановкой
    #         if nx.has_path(G, house_location, nearest_bus_stop):
    #             # Находим кратчайший путь
    #             shortest_path = nx.shortest_path(G, source=house_location, target=nearest_bus_stop, weight='weight')
    #             routes[house_location] = shortest_path
    #         else:
    #             # Если пути нет, записываем None
    #             routes[house_location] = None
        
    #     return routes, house_locations

    # routes, house_locations = find_shortest_paths_to_bus_stops(houses, buses, G)

    route_distribution = assign_routes_to_population(G, houses, buses, tree, node_coords)
    edge_loads = calculate_population_loads(G, route_distribution)

    # --- Update weights based on loads and visualize heatmap ---
    update_weights(G, edge_loads)
    summary = summarize_traffic_data(G, edge_loads, route_distribution, buses)
    print(summary)
    heat_map = plot_heatmap(G, edge_loads, buses)
    # Создаем словарь с результатами
    result = {
        "summary": summary,
        "houses": [{"x": row.geometry.centroid.x, "y": row.geometry.centroid.y} for _, row in houses.iterrows()],
        "bus_stops": [{"x": bus.geometry.coords[0][0], "y": bus.geometry.coords[0][1]} for _, bus in buses.iterrows()],
        "heat_map": heat_map
    }

    return result