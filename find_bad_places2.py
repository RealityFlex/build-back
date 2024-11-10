import geopandas as gpd
from shapely.geometry import Point
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from fpdf import FPDF
import matplotlib.pyplot as plt
from pathlib import Path
from fpdf import FPDF
from street_graph import (create_graph, add_places_to_graph, calculate_population, summarize_traffic_data,
                          assign_routes_to_population, calculate_population_loads, update_weights, plot_heatmap, add_population_column_to_houses, cpu_shortest_path_usage, plot_street_usage)

users_data = {}

# --- Load and preprocess data ---
def find_shapefile(directory, keyword=None):
    """Ищет первый файл .shp в директории с опциональной фильтрацией по ключевому слову"""
    for file in Path(directory).glob("*.shp"):
        if keyword is None or keyword.lower() in file.stem.lower():
            return str(file)
    return None

def generate_raport(folder_path, id, version, lat=55.555, long=37.495):
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

    point = gpd.GeoDataFrame(geometry=[Point(long, lat)], crs="EPSG:4326").to_crs(epsg=3857)
    radius = 1000

    houses = houses.to_crs(epsg=3857)
    buses = buses.to_crs(epsg=3857)
    streets = streets.to_crs(epsg=3857)

    houses = houses[houses.geometry.distance(point.geometry.iloc[0]) <= radius]
    buses = buses[buses.geometry.distance(point.geometry.iloc[0]) <= radius]
    streets = streets[streets.geometry.distance(point.geometry.iloc[0]) <= radius]

    houses = houses.to_crs(epsg=4326)
    buses = buses.to_crs(epsg=4326)
    streets = streets.to_crs(epsg=4326)

    # --- Calculate population in each house ---
    houses = add_population_column_to_houses(houses)  # Добавление столбца 'Total_People'

    # --- Create graph and add places ---
    G, nodes = create_graph(streets)
    node_coords = np.array(nodes)
    tree = cKDTree(node_coords)

    add_places_to_graph(houses, G, tree, node_coords, 'house')
    add_places_to_graph(buses, G, tree, node_coords, 'bus_stop')

    # --- Assign routes and calculate loads based on population ---
    route_distribution = assign_routes_to_population(G, houses, buses, tree, node_coords)
    edge_loads = calculate_population_loads(G, route_distribution)

    # --- Update weights based on loads and visualize heatmap ---
    update_weights(G, edge_loads)

    summary = summarize_traffic_data(G, edge_loads, route_distribution, buses)

    def create_pdf_report(summary, heatmap_image_path, street_usage_path):
        pdf = FPDF()
        pdf.add_page()

        # Добавляем шрифт с поддержкой кириллицы
        pdf.add_font('ArialUnicode', '', 'arial.ttf', uni=True)  # Путь к вашему шрифту
        pdf.set_font('ArialUnicode', size=16)

        # Заголовок
        pdf.cell(200, 10, txt="Отчет по данным о движении пешеходов", ln=True, align='C')

        # Вставка краткого описания на русском
        pdf.ln(10)  # Перенос строки
        pdf.set_font("ArialUnicode", size=12)
        pdf.multi_cell(0, 10, txt=f"""
        В этом отчете представлены ключевые результаты анализа данных о движении пешеходов. Основные показатели:
        - Количество автобусных остановок: {summary['num_bus_stops']}
        - Общее количество людей, обслуживаемых: {int(summary['total_people'])}
        - Количество перегруженных улиц: {summary['overloaded_edges_count']}
        - Длина самой длинной перегруженной улицы: {summary['longest_overloaded_edge_length']} метров
        - Оценка системы: {summary['sytem_score']}
        """)

        # Вставка изображения тепловой карты
        pdf.ln(2)  # Перенос строки
        pdf.set_font("ArialUnicode", size=12)
        pdf.cell(200, 10, txt="График интенсивности движения пешеходов (тепловая карта):", ln=True)
        pdf.ln(2)
        pdf.image(heatmap_image_path, x=30, w=150)

        # Вставка изображения графика использования улиц
        pdf.ln(2)  # Перенос строки
        pdf.set_font("ArialUnicode", size=12)
        pdf.cell(200, 10, txt="График использования улиц по маршрутам пешеходов:", ln=True)
        pdf.ln(2)
        pdf.image(street_usage_path, x=30, w=150)

        # Вывод PDF
        output_path = 'traffic_summary_report.pdf'  # Сохраняем отчет в текущей директории
        pdf.output(output_path)
        return output_path

    # Генерация тепловой карты и получение пути к изображению
    heatmap_image_path, edge_colors = plot_heatmap(G, edge_loads, buses)
    street_usage = cpu_shortest_path_usage(houses, buses, G)
    street_usage_path = plot_street_usage(streets, street_usage, houses, buses)

    # Создание PDF с изображением тепловой карты
    pdf_file_path = create_pdf_report(summary, heatmap_image_path, street_usage_path)
    return pdf_file_path

