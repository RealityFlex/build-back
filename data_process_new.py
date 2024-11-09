import geopandas as gpd
import networkx as nx
from shapely.geometry import Point, LineString
from scipy.spatial import cKDTree
import json
import numpy as np
from tqdm import tqdm
import pandas as pd
from pathlib import Path

def find_shapefile(directory, keyword=None):
    """Ищет первый файл .shp в директории с опциональной фильтрацией по ключевому слову"""
    for file in Path(directory).glob("*.shp"):
        if keyword is None or keyword.lower() in file.stem.lower():
            return str(file)
    return None

def find_routes_and_places(folder_path):
    """Загружает файлы маршрутов и местоположений"""
    folder_path = Path(folder_path)

    # Ищем shapefiles в папке
    files = {
        "Street": find_shapefile(folder_path / "streets"),
    }

    for name, path in files.items():
        if path:
            print(f"Found {name}: {path}")
        else:
            print(f"{name} shapefile not found!")

    # Ищем файлы для зданий и остановок
    house_path = find_shapefile(folder_path / "buildings")
    stations = find_shapefile(folder_path / "stations")

    print(f"House path: {house_path}")
    print(f"Stations path: {stations}")

    if house_path and stations:
        # Загружаем данные
        houses = gpd.read_file(house_path).to_crs(epsg=4326).sample(n=100)
        buses = gpd.read_file(stations).to_crs(epsg=4326)  # Остановки транспорта

        # Загружаем данные для улиц
        streets = gpd.GeoDataFrame(pd.concat([ 
            gpd.read_file(path).to_crs(epsg=4326)[lambda data: data['Foot'] == 1] 
            for path in files.values() 
        ], ignore_index=True))

    # Создаем граф с NetworkX
    def create_graph(streets):
        G = nx.DiGraph()
        nodes = set()
        for _, row in streets.iterrows():
            coords = list(row.geometry.coords)
            for start, end in zip(coords[:-1], coords[1:]):
                distance = Point(start).distance(Point(end))
                G.add_edge(start, end, weight=distance)
                G.add_edge(end, start, weight=distance)
                nodes.add(start)
                nodes.add(end)
        return G, list(nodes)

    G, nodes = create_graph(streets)

    # cKDTree и поиск ближайших точек
    node_coords = np.array(nodes)
    tree = cKDTree(node_coords)

    def find_nearest_node(point, tree, node_coords):
        dist, idx = tree.query((point.x, point.y))
        return tuple(node_coords[idx]), dist

    # Добавление домов и остановок в граф
    def add_places_to_graph(places, G, tree, node_coords, place_type):
        for _, place in tqdm(places.iterrows(), desc=f"Adding {place_type}", total=len(places)):
            point = place.geometry.centroid if place_type == "house" else place.geometry
            nearest_node, dist = find_nearest_node(point, tree, node_coords)
            new_node = (point.x, point.y)
            G.add_edge(nearest_node, new_node, weight=dist)
            G.add_edge(new_node, nearest_node, weight=dist)
            G.nodes[new_node]['type'] = place_type

    add_places_to_graph(houses, G, tree, node_coords, 'house')
    add_places_to_graph(buses, G, tree, node_coords, 'bus_stop')

    # Поиск маршрута от дома до ближайшей остановки
    def find_shortest_paths_to_bus_stops(houses, buses, G):
        house_locations = []
        bus_stops = {tuple(bus.geometry.coords[0]): bus for _, bus in buses.iterrows()}
        routes = {}
        
        for house in tqdm(houses, desc="Finding shortest paths"):
            house_point = house
            house_location = (house_point[0], house_point[1])
            house_locations.append(house_location)
            
            # Находим ближайшую остановку
            nearest_bus_stop = min(bus_stops.keys(), key=lambda bus: Point(house_point).distance(Point(bus_stops[bus].geometry)))
            
            # Проверим, существует ли путь между домом и ближайшей остановкой
            if nx.has_path(G, house_location, nearest_bus_stop):
                # Находим кратчайший путь
                shortest_path = nx.shortest_path(G, source=house_location, target=nearest_bus_stop, weight='weight')
                routes[house_location] = shortest_path
            else:
                # Если пути нет, можно добавить сообщение о невозможности найти путь
                routes[house_location] = None
        
        return routes, house_locations

    def find_buildings_within_1km(houses, buses, G):
        bus_stops = {tuple(bus.geometry.coords[0]): bus for _, bus in buses.iterrows()}
        buildings_near_stops = []

        for _, house in tqdm(houses.iterrows(), desc="Finding buildings within 1km"):
            house_point = house.geometry.centroid
            house_location = (house_point.x, house_point.y)
            
            # Находим ближайшую остановку
            nearest_bus_stop = min(bus_stops.keys(), key=lambda bus: Point(house_point).distance(Point(bus_stops[bus].geometry)))
            
            # Проверяем, находится ли здание в пределах 1 км от остановки
            if Point(house_point).distance(Point(bus_stops[nearest_bus_stop].geometry)) <= 1.0:
                buildings_near_stops.append(house_location)
        
        return buildings_near_stops


    buildings_near_stops = find_buildings_within_1km(houses, buses, G)
    routes, house_locations = find_shortest_paths_to_bus_stops(buildings_near_stops, buses, G)

    # Создаем словарь с результатами
    result = {
        "houses": [{"x": house[0], "y": house[1]} for house in house_locations],
        "bus_stops": [{"x": bus.geometry.coords[0][0], "y": bus.geometry.coords[0][1]} for _, bus in buses.iterrows()],
        "routes": {
            f"{house_location[0]},{house_location[1]}": [
                {"x": point[0], "y": point[1]} for point in route
            ] if route else None
            for house_location, route in routes.items()
        }
    }

    return result
