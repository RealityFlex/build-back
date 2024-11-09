import geopandas as gpd
import pandas as pd
import networkx as nx
import json
from shapely.geometry import Point
from scipy.spatial import cKDTree

from pathlib import Path

def find_shapefile(directory, keyword=None):
    # Ищем первый файл с расширением .shp, опционально фильтруем по ключевому слову
    for file in Path(directory).glob("*.shp"):
        if keyword is None or keyword.lower() in file.stem.lower():
            return str(file)
    return None

def process_shapefiles(folder_path):
    folder_path = Path(folder_path)
    
    files = {
        "Street": find_shapefile(folder_path / "streets").items()[0]
    }

    for name, path in files.items():
        if path:
            print(f"Found {name}: {path}")
        else:
            print(f"{name} shapefile not found!")

    # Загрузка данных
    house_path = find_shapefile(folder_path / "buildings").items()[0],
    metro_path = find_shapefile(folder_path / "metro").items()[0]

    print(house_path)

    houses = gpd.read_file(house_path).to_crs(epsg=4326)
    metroes = gpd.read_file(metro_path).to_crs(epsg=4326)  # Станции метро

    streets = gpd.GeoDataFrame(pd.concat([ 
        gpd.read_file(path).to_crs(epsg=4326)[lambda data: data['Foot'] == 1] 
        for path in files.values() 
    ], ignore_index=True))

    streets = streets[streets.geometry.type == 'LineString']
    G = nx.Graph()
    nodes = []
    edges = []
    for _, row in streets.iterrows():
        coords = list(row.geometry.coords)
        for i in range(len(coords) - 1):
            G.add_edge(coords[i], coords[i + 1], weight=Point(coords[i]).distance(Point(coords[i + 1])))
            nodes.append(coords[i])
            nodes.append(coords[i + 1])

    nodes = sorted(set(nodes), key=lambda x: (x[0], x[1]))
    node_coords = [(x, y) for x, y in nodes]
    tree = cKDTree(node_coords)

    houses['centroid'] = houses.geometry.centroid

    def find_nearest_node(house_center, tree):
        house_coords = (house_center.x, house_center.y)
        distance, idx = tree.query(house_coords)
        nearest_node = node_coords[idx]
        return nearest_node, distance

    # Добавление домов в граф
    for _, house in houses.iterrows():
        house_center = house['centroid']
        nearest_point, nearest_distance = find_nearest_node(house_center, tree)
        G.add_node((house_center.x, house_center.y), type='house')
        G.add_edge((house_center.x, house_center.y), nearest_point, weight=nearest_distance)

    # Формирование ответа
    result = {
        "buildings": [],
        "metro_stations": [],
        "routes": []
    }

    # Полигоны зданий
    result["buildings"] = [house.geometry.__geo_interface__ for _, house in houses.iterrows()]

    # Точки остановок метро
    result["metro_stations"] = [{"x": metro.geometry.x, "y": metro.geometry.y} for _, metro in metroes.iterrows()]

    # Поиск маршрутов
    max_distance = 1000  # в метрах
    for _, metro in metroes.iterrows():
        metro_coords = metro.geometry
        metro_point = Point(metro_coords.x, metro_coords.y)

        # Выбираем дома, которые находятся на расстоянии 1 км или меньше от станции метро
        nearby_houses = []
        for _, house in houses.iterrows():
            house_center = house['centroid']
            distance = metro_point.distance(house_center) * 100000  # Переводим в метры
            if distance <= max_distance:
                nearby_houses.append(house_center)

        # Строим кратчайшие пути для ближайших домов
        for start_node in nearby_houses:
            start_node_coords = (start_node.x, start_node.y)
            end_node = (metro_coords.x, metro_coords.y)

            if start_node_coords in G.nodes and end_node in G.nodes:
                shortest_path = nx.shortest_path(G, source=start_node_coords, target=end_node, weight='weight')
                result["routes"].append({
                    "start": {"x": start_node.x, "y": start_node.y},
                    "end": {"x": metro_coords.x, "y": metro_coords.y},
                    "path": [{"x": node[0], "y": node[1]} for node in shortest_path]
                })

    # Возвращаем данные в формате JSON
    return json.dumps(result, ensure_ascii=False, indent=4)