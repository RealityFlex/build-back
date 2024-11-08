FROM python:3.8-buster

# рабочая директория внутри проекта
WORKDIR /usr/src/app
# устанавливаем зависимости

RUN pip install --upgrade pip
COPY req.txt .
RUN pip install -r req.txt
# copy project
COPY . .