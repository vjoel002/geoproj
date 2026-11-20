FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Bibliotecas de sistema: GDAL/GEOS (django.contrib.gis), libpq e libs exigidas pelo OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgdal-dev \
    libgeos-dev \
    libpq5 \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt

COPY requirements.extra.txt .
RUN pip install --no-cache-dir -r requirements.extra.txt

COPY . .

EXPOSE 8000

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "geoproject.asgi:application"]
