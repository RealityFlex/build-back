# utils.py
from shapely.geometry import Point, LineString
from collections import defaultdict
import geopandas as gpd
import networkx as nx
from shapely.geometry import Point
import numpy as np
import matplotlib.cm as cm
from scipy.spatial import cKDTree
import matplotlib.pyplot as plt
from tqdm import tqdm

# --- Create Graph from Streets ---
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

# --- Find nearest node ---
def find_nearest_node(point, tree, node_coords):
    dist, idx = tree.query((point.x, point.y))
    return tuple(node_coords[idx]), dist

# --- Add Places (houses, bus stops) to Graph ---
def add_places_to_graph(places, G, tree, node_coords, place_type):
    for _, place in tqdm(places.iterrows(), desc=f"Adding {place_type}", total=len(places)):
        point = place.geometry.centroid if place_type == "house" else place.geometry
        nearest_node, dist = find_nearest_node(point, tree, node_coords)
        new_node = (point.x, point.y)
        G.add_edge(nearest_node, new_node, weight=dist)
        G.add_edge(new_node, nearest_node, weight=dist)
        G.nodes[new_node]['type'] = place_type
        if place_type == "house":
            G.nodes[new_node]['total_people'] = place["Total_People"]
        else: 
            G.nodes[new_node]['total_people'] = 0
        

# --- Compute paths and loads ---
def compute_paths_and_loads(G, sources, targets):
    flow_distribution = {source: {target: np.random.randint(800, 1000) for target in targets} for source in sources}
    paths = {source: nx.single_source_dijkstra_path(G, source) for source in sources}

    edge_loads = {edge: 0 for edge in G.edges}
    
    for source, target_flows in tqdm(flow_distribution.items(), desc="Calculating loads"):
        if source not in paths:
            continue
        for target, flow in target_flows.items():
            if target not in paths[source]:
                continue
            path = paths[source][target]
            for i in range(len(path) - 1):
                edge = (path[i], path[i+1])
                edge_loads[edge] += flow
                
    return edge_loads

# --- Update Edge Weights based on Loads ---
def update_weights(G, edge_loads, capacity=300):
    for edge, load in edge_loads.items():
        weight = G[edge[0]][edge[1]]['weight']
        congestion = load / capacity
        G[edge[0]][edge[1]]['weight'] = weight * (1 + congestion * 2)

# --- Plot Heatmap for Edge Loads ---
# def plot_heatmap(G, edge_loads):
#     loads = np.array(list(edge_loads.values()))
#     norm = plt.Normalize(vmin=0, vmax=loads.max())
#     cmap = plt.cm.Reds

#     fig, ax = plt.subplots(figsize=(12, 8))
#     for (u, v, data) in G.edges(data=True):
#         load = edge_loads[(u, v)]
#         color = cmap(norm(load))
#         ax.plot([u[0], v[0]], [u[1], v[1]], color=color, linewidth=2)

#     sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
#     sm.set_array([])
#     plt.colorbar(sm, ax=ax, label='Load Intensity')
#     plt.title("Heatmap of Pedestrian Congestion")
#     plt.show()

def plot_heatmap(G, edge_loads, buses):
    # Extract the load values
    loads = np.array(list(edge_loads.values()))
    norm = plt.Normalize(vmin=0, vmax=loads.max())
    cmap = plt.cm.Reds

    # Увеличиваем размер изображения
    fig, ax = plt.subplots(figsize=(20, 18))  # Увеличен размер до 24x18 дюймов

    edge_colors = []
    
    for (u, v, data) in G.edges(data=True):
        load = edge_loads[(u, v)]
        color = cmap(norm(load))
        edge_colors.append((u, v, load, color))
        ax.plot([u[0], v[0]], [u[1], v[1]], color=color, linewidth=2)

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])  # Make the ScalarMappable a no-op
    plt.colorbar(sm, ax=ax, label='Load Intensity')
    plt.title("Heatmap of Pedestrian Congestion")
    heatmap_path = 'heatmap_image.png'
    plt.tight_layout()

    # Plot buses after the heatmap to ensure they're visible on top
    buses.plot(ax=ax, color='green', markersize=10, label='Bus Stops', zorder=5)

    # Add legend and save the figure
    plt.legend()
    plt.savefig(heatmap_path, format='png')

    plt.close(fig)
    return heatmap_path, edge_colors

# --- Calculate people in one apartment ---
def calculate_people_in_apartment(mean=2, std_dev=1):
    people = int(np.random.normal(mean, std_dev))
    return max(1, min(people, 4))  # Limit to 1-4 people

# --- Calculate total people in a house based on apartments ---
def calculate_total_people_in_house(house, mean=2, std_dev=1):
    """
    Рассчитывает общее количество людей в доме на основе количества квартир.
    Параметры:
    - house: строка датафрейма с данными о доме
    - mean: среднее количество людей в квартире
    - std_dev: стандартное отклонение для нормального распределения
    Возвращает:
    - Общее количество людей в доме
    """
    apartments = int(house['Apartments'])  # Количество квартир
    if apartments == 0:
        apartments = 5
    total_people = sum([calculate_people_in_apartment(mean, std_dev) for _ in range(apartments)])  # Суммируем количество людей
    return total_people

# --- Добавление столбца с количеством людей в домах ---
def add_population_column_to_houses(houses, mean=2, std_dev=1):
    """
    Для каждого дома в датафрейме houses рассчитывает общее количество людей и добавляет новый столбец 'Total_People'.
    Параметры:
    - houses: GeoDataFrame с данными о домах
    - mean: среднее количество людей в квартире
    - std_dev: стандартное отклонение для нормального распределения
    Возвращает:
    - GeoDataFrame с добавленным столбцом 'Total_People', содержащим количество людей в доме
    """
    houses['Total_People'] = houses.apply(lambda row: calculate_total_people_in_house(row, mean, std_dev), axis=1)
    return houses

# --- Calculate population for all houses in GeoDataFrame ---
def calculate_population(houses, mean=2, std_dev=1):
    if 'Apartments' in houses.columns:
        houses['Total_People'] = houses.apply(lambda row: calculate_total_people_in_house(row, mean, std_dev), axis=1)
    else:
        print("Column 'Apartments' missing in data.")
    return houses

# Внутри функции assign_routes_to_population
def assign_routes_to_population(G, houses, buses, tree, node_coords):
    """
    Назначение маршрутов для населения, идущего от домов к ближайшим остановкам.
    """
    route_distribution = {}

    # Итерация по домам
    for _, house in houses.iterrows():
        house_location = house.geometry.centroid if house.geometry.geom_type != "Point" else house.geometry
        nearest_house_node, _ = find_nearest_node(house_location, tree, node_coords)
        
        # Проверка, что house_node существует в графе
        if nearest_house_node not in G:
            continue

        # Получаем количество людей в доме
        total_people = house['Total_People'] * 0.51 / 60

        # Итерация по остановкам
        for _, bus_stop in buses.iterrows():
            # Здесь bus_stop — это строка GeoDataFrame и мы обращаемся к bus_stop.geometry
            bus_stop_location = bus_stop.geometry.centroid if bus_stop.geometry.geom_type != "Point" else bus_stop.geometry
            nearest_bus_node, _ = find_nearest_node(bus_stop_location, tree, node_coords)
            
            # Проверка, что bus_node существует в графе
            if nearest_bus_node not in G:
                continue

            # Если путь существует, добавляем информацию о маршруте
            if nearest_house_node in G and nearest_bus_node in G:
                try:
                    # Находим путь от дома до остановки
                    path = nx.shortest_path(G, source=nearest_house_node, target=nearest_bus_node, weight="weight")
                    
                    # Добавляем новый маршрут в route_distribution с ключом (nearest_house_node, nearest_bus_node)
                    route_distribution[(nearest_house_node, nearest_bus_node)] = {
                        'path': path,
                        'total_people': total_people
                    }

                except nx.NetworkXNoPath:
                    # Если нет пути, пропускаем
                    continue

    return route_distribution

def cpu_shortest_path_usage(houses, buses, G):
    house_nodes = np.array([(c.x, c.y) for c in houses.geometry.centroid])
    bus_nodes = np.array([(g.x, g.y) for g in buses.geometry])
    
    usage = defaultdict(int)
    
    for house_node in tqdm(house_nodes, desc="Calculating paths"):
        distances = []
        for bus_node in bus_nodes:
            try:
                length = nx.shortest_path_length(G, source=tuple(house_node), target=tuple(bus_node), weight='weight')
                distances.append((bus_node, length))
            except nx.NetworkXNoPath:
                continue
        
        nearest_stops = sorted(distances, key=lambda x: x[1])[:2]
        
        for bus_node, _ in nearest_stops:
            path = nx.shortest_path(G, source=tuple(house_node), target=tuple(bus_node), weight='weight')
            for start, end in zip(path[:-1], path[1:]):
                usage[(start, end)] += 1
    
    return usage

# Визуализация результата
def plot_street_usage(streets, street_usage, houses, buses):
    fig, ax = plt.subplots(figsize=(12, 12))
    streets.plot(ax=ax, color='lightgray', linewidth=0.5)
    
    max_usage = max(street_usage.values())
    for (start, end), usage in street_usage.items():
        line = LineString([start, end])
        usage_norm = usage / max_usage
        gpd.GeoSeries([line]).plot(ax=ax, color=cm.viridis(usage_norm), linewidth=2)
    
    houses.plot(ax=ax, color='blue', markersize=10, label='Houses')
    buses.plot(ax=ax, color='red', markersize=10, label='Bus Stops')
    plt.legend()
    route_path = "routes.png"
    plt.savefig(route_path, format='png')

    plt.close(fig)
    return route_path

def calculate_population_loads(G, route_distribution):
    """
    Рассчитывает нагрузку на ребра графа на основе распределения маршрутов от домов к остановкам.
    Каждый маршрут имеет количество людей, идущих по пути.
    """
    # Словарь для хранения нагрузки на ребра
    edge_loads = {edge: 0 for edge in G.edges}
    
    # Итерация по маршрутам в route_distribution
    for (house_node, bus_stop_node), route_info in tqdm(route_distribution.items(), desc="Calculating loads"):
        path = route_info['path']
        total_people = route_info['total_people']
        
        # Для каждого пути добавляем нагрузку только один раз для каждого ребра
        for i in range(len(path) - 1):
            edge = (path[i], path[i+1])
            
            # Увеличиваем нагрузку на ребро с учетом количества людей
            edge_loads[edge] += total_people
        
    return edge_loads

def summarize_traffic_data(G, edge_loads, route_distribution, buses):
    """
    Возвращает сводную аналитику по загруженности дорог, основанной на информации о маршрутах и нагрузках.
    
    Параметры:
    - G: граф, в котором происходят маршруты.
    - edge_loads: словарь, содержащий нагрузку на каждое ребро графа.
    - route_distribution: словарь маршрутов с количеством людей для каждого пути.

    Возвращает:
    - Словарь с аналитической информацией:
      1. Количество значимых объектов (остановок)
      2. Сумма людей, которые прошли по дорогам
      3. Количество перегруженных участков дорог (нагрузка > 800)
      4. Наибольший загруженный участок (длина самого длинного перегруженного участка)
    """
    # 1. Количество участков дорог
    edges = len(route_distribution)

    num_bus_stops = buses.shape[0]
    
    # 2. Сумма людей, которые прошли по дорогам
    total_people = sum(route_info['total_people'] for route_info in route_distribution.values())

    # 3. Количество перегруженных участков дорог (нагрузка на участке больше 800)
    overloaded_edges_count = sum(1 for load in edge_loads.values() if load > 800)

    # 4. Наибольший загруженный участок (длина самого длинного перегруженного участка)
    longest_overloaded_edge_length = 0
    for (u, v), load in edge_loads.items():
        if load > 800:
            # Расчет длины ребра, если его нагрузка больше 800
            edge_length = np.linalg.norm(np.array(u) - np.array(v))  # Используем евклидово расстояние для длины ребра
            if edge_length > longest_overloaded_edge_length:
                longest_overloaded_edge_length = edge_length

    # Возвращаем словарь с аналитикой
    summary = {
        "num_bus_stops": num_bus_stops,  # Количество значимых объектов (остановок)
        "total_people": total_people,    # Сумма людей, которые прошли по дорогам
        "overloaded_edges_count": overloaded_edges_count,  # Количество перегруженных участков дорог
        "longest_overloaded_edge_length": longest_overloaded_edge_length,  # Длина самого длинного перегруженного участка
        "sytem_score": (edges - overloaded_edges_count) / edges
    }
    
    return summary






