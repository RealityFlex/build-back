from fastapi import FastAPI, File, UploadFile, Request, HTTPException, Response
from typing import List
import shutil
import os
import uuid
import data_process_new
import json
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Папка для хранения загруженных файлов
BASE_SAVE_FOLDER = "./uploaded_files/"

# Ожидаемые расширения файлов
EXPECTED_EXTENSIONS = {
    "shp": "shp",
    "shx": "shx",
    "dbf": "dbf",
    "prj": "prj",
    "qmd": "qmd",
    "cpg": "cpg"
}

# Функция для получения или генерации ID сессии
def get_session_id(request: Request) -> str:
    session_id = request.cookies.get("session_id")
    if not session_id:
        # Если сессия не найдена, генерируем новый уникальный ID
        session_id = str(uuid.uuid4())
    return session_id

def get_folders_in_directory(session_id: str):
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    
    # Проверяем, существует ли директория
    if not os.path.exists(session_folder):
        return []
    
    # Получаем список всех элементов в папке, фильтруем только папки
    folders = [f for f in os.listdir(session_folder) if os.path.isdir(os.path.join(session_folder, f))]
    
    return folders

from fastapi import FastAPI, HTTPException, Request, Response
import os

app = FastAPI()

origins = [
    "http://localhost:8080",
    "http://localhost:3000",
    "http://62.109.26.235:8180",
    "http://62.109.26.235:3000",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Папка для хранения файлов
BASE_SAVE_FOLDER = "./uploaded_files/"

def get_files_in_session_folder(session_id: str, version = None):
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    
    # Проверяем, существует ли директория
    if not os.path.exists(session_folder):
        raise HTTPException(status_code=404, detail="Session folder not found")
    
    # Получаем список всех папок и файлов внутри папки session_id
    result = {}
    if version != None:
        folder_path = os.path.join(session_folder, version)
        result[version] = {}
        # Проверяем, что это директория
        if os.path.isdir(folder_path):
            # Получаем список файлов в папке
            for folder_name_2 in os.listdir(folder_path):
                result[version][folder_name_2] = []
                ppth = os.path.join(folder_path, folder_name_2)
                if os.path.isdir(ppth):
                    files = os.listdir(ppth)
                    result[version][folder_name_2] = files
    else:
        for folder_name in os.listdir(session_folder):
            folder_path = os.path.join(session_folder, folder_name)
            result[folder_name] = {}
            # Проверяем, что это директория
            if os.path.isdir(folder_path):
                # Получаем список файлов в папке
                for folder_name_2 in os.listdir(folder_path):
                    result[folder_name][folder_name_2] = []
                    ppth = os.path.join(folder_path, folder_name_2)
                    if os.path.isdir(ppth):
                        files = os.listdir(ppth)
                        result[folder_name][folder_name_2] = files
        
    return result

@app.get("/api/files/")
async def list_files(request: Request, response: Response, version = None):
    # Извлекаем session_id из cookies
    session_id = get_session_id(request)
    
    if not session_id:
        response.headers["Set-Cookie"] = f"session_id={session_id}; Path=/; SameSite=None; Secure=false; HttpOnly=true;"
    
    try:
        # Получаем список файлов для session_id
        files = get_files_in_session_folder(session_id, version)
        return {"versions": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Путь к файлу метаданных
def get_metadata_path(session_folder: str):
    return os.path.join(session_folder, "metadata.json")

# Функция для записи метаданных
def write_metadata(session_folder: str, version: str):
    metadata_path = get_metadata_path(session_folder)
    # Если файл метаданных существует, загружаем его
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    # Добавляем или обновляем информацию о версии
    metadata[version] = {"created_at": datetime.utcnow().isoformat()}
    
    # Записываем обновленные метаданные обратно в файл
    with open(metadata_path, "w") as f:
        json.dump(metadata, f)

# Функция для чтения метаданных
def read_metadata(session_folder: str):
    metadata_path = get_metadata_path(session_folder)
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            return json.load(f)
    return {}

import shutil

@app.get("/api/folders/")
async def get_folders(request: Request, response: Response):
    # Извлекаем session_id из cookies
    session_id = get_session_id(request)
    if not session_id:
        response.headers["Set-Cookie"] = f"session_id={session_id}; Path=/; SameSite=None; Secure=false; HttpOnly=true;"
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    try:
        folders = get_folders_in_directory(session_id)
        # Проверка наличия папки "default"
        if "default" not in folders:
            session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
            
            # Создаем папки, если их нет
            os.makedirs(session_folder, exist_ok=True)

            # Записываем время создания версии в метаданные
            write_metadata(session_folder, "default_data")
            # Папка "default" отсутствует, копируем данные из default_data
            default_data_folder = "default_data"
            default_version_folder = os.path.join(session_folder, "default")
            # Копируем все содержимое из default_data в папку "default"
            if os.path.exists(default_data_folder):
                shutil.copytree(default_data_folder, default_version_folder)
            else:
                raise HTTPException(status_code=404, detail="default_data folder not found")
            # После копирования создаем метаданные для версии "default"
            write_metadata(session_folder, "default")
            folders = get_folders_in_directory(session_id)
        # Чтение метаданных и добавление времени создания
        metadata = read_metadata(session_folder)
        folders_info = [{"version": folder, "created_at": metadata.get(folder, {}).get("created_at")} for folder in folders]
        response.headers["Set-Cookie"] = f"session_id={session_id}; Path=/; SameSite=None; Secure=false; HttpOnly=true;"
        return {"folders": folders_info}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload_files/")
async def upload_files(
    dataset_name: str, 
    version: str,
    response: Response,
    files: List[UploadFile] = File(...),
    request: Request = None,
):
    # Получаем или генерируем ID сессии
    session_id = get_session_id(request)
    
    # Формируем путь для сессии и версии
    response.headers["Set-Cookie"] = f"session_id={session_id}; Path=/; SameSite=None; Secure=false; HttpOnly=true;"
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    version_folder = os.path.join(session_folder, version)
    dataset_folder = os.path.join(version_folder, dataset_name)
    
    # Создаем папки, если их нет
    os.makedirs(version_folder, exist_ok=True)
    os.makedirs(dataset_folder, exist_ok=True)

    # Записываем время создания версии в метаданные
    write_metadata(session_folder, version)

    file_paths = []
    
    # Обрабатываем каждый файл
    for file in files:
        extension = file.filename.split('.')[-1]
        if extension in EXPECTED_EXTENSIONS:
            new_filename = f"{dataset_name}.{extension}"
            file_location = os.path.join(dataset_folder, new_filename)
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_paths.append(file_location)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid file extension for {file.filename}")
    
    return {"uploaded_files": file_paths}

@app.get("/api/get_routes/")
async def upload_files(
    version: str,
    response: Response,
    request: Request = None,
):
    # Получаем или генерируем ID сессии
    session_id = get_session_id(request)
    # Проверяем, существует ли директория
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    if not os.path.exists(session_folder):
        response.headers["Set-Cookie"] = f"session_id={session_id}; Path=/; SameSite=None; Secure=false; HttpOnly=true;"
        raise HTTPException(status_code=404, detail="Session folder not found")
    # Формируем путь для сессии и версии
    response.headers["Set-Cookie"] = f"session_id={session_id}; Path=/; SameSite=None; Secure=false; HttpOnly=true;"
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    version_folder = os.path.join(session_folder, version)
    return data_process_new.find_routes_and_places(version_folder, session_id, version)


@app.delete("/api/delete_version/")
async def delete_version(request: Request, response: Response, version: str):
    # Получаем session_id из cookies
    session_id = get_session_id(request)
    
    if not session_id:
        response.headers["Set-Cookie"] = f"session_id={session_id}; Path=/; SameSite=None; Secure=false; HttpOnly=true;"
    
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    version_folder = os.path.join(session_folder, version)
    metadata_path = get_metadata_path(session_folder)

    # Проверяем, существует ли папка версии
    if not os.path.exists(version_folder):
        raise HTTPException(status_code=404, detail="Version folder not found")

    try:
        # Удаляем папку версии
        shutil.rmtree(version_folder)
        
        # Удаляем запись из метаданных
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
            
            if version in metadata:
                del metadata[version]
            
            # Записываем обновленные метаданные
            with open(metadata_path, "w") as f:
                json.dump(metadata, f)
        
        return {"message": f"Version {version} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

