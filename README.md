# Buildings Roads Project

## Описание проекта

Проект для анализа и визуализации данных о дорогах и зданиях, с использованием Python (FastAPI) и фронтенда (PNPM). 

## Структура проекта

- **backend/**: исходный код backend-сервиса на FastAPI.
- **frontend/**: HTML шаблоны и ресурсы для визуализации.
- **db/**: папка для хранения данных PostgreSQL.
- **uploaded_files/**: папка для загрузок пользователя.
- **default_data/**: файлы с предустановленными данными.

## Требования

- Docker и Docker Compose
- Python 3.11+
- PNPM (для фронтенда)

## Установка и запуск

### 1. Убедитесь, что установлены все зависимости

- Установите [Docker](https://docs.docker.com/get-docker/).
- Установите [PNPM](https://pnpm.io/installation).

### 2. Запуск через Docker Compose

Выполните команду:

```bash
docker-compose up --build
