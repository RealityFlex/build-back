from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from typing import List
import shutil
import os
import uuid
import data_process

app = FastAPI()

# Папка для хранения загруженных файлов
BASE_SAVE_FOLDER = "./uploaded_files/"

# Ожидаемые расширения файлов
EXPECTED_EXTENSIONS = {
    "shp": "shp",
    "shx": "shx",  # shx файл с тем же именем
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

@app.post("/upload_files/")
async def upload_files(
    dataset_name: str, 
    version: str, 
    files: List[UploadFile] = File(...),
    request: Request = None
):
    # Получаем или генерируем ID сессии
    session_id = get_session_id(request)
    
    # Формируем путь для сессии и версии
    session_folder = os.path.join(BASE_SAVE_FOLDER, session_id)
    version_folder = os.path.join(session_folder, version)
    
    # Создаем папки, если их нет
    os.makedirs(version_folder, exist_ok=True)

    file_paths = []
    
    # Обрабатываем каждый файл
    for file in files:
        # Определяем расширение файла
        extension = file.filename.split('.')[-1]
        
        if extension in EXPECTED_EXTENSIONS:
            # Формируем новое имя файла
            new_filename = f"{dataset_name}.{extension}"
            file_location = os.path.join(version_folder, new_filename)
            
            # Сохраняем файл
            with open(file_location, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            # Добавляем путь к файлу в список
            file_paths.append(file_location)
        else:
            # Если расширение файла не подходит, возвращаем ошибку
            raise HTTPException(status_code=400, detail=f"Invalid file extension for {file.filename}")
    
    return data_process.convert_data(os.path.join(version_folder, f"{dataset_name}.{'shp'}"))
