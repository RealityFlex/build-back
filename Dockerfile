FROM python:3.8-buster

# рабочая директория внутри проекта
WORKDIR /usr/src/app
# устанавливаем зависимости

RUN pip install --upgrade pip
COPY req.txt .
RUN pip install -r req.txt
RUN pip install geopandas==0.11.1 fiona==1.8.20
# copy project
COPY . .