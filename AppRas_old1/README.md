# AppRas — Visualizador de Resultados HEC-RAS (estilo RAS Mapper)

App Django que recebe GeoTIFFs de profundidade exportados do HEC-RAS/RAS
Mapper, converte para PNG colorizado em EPSG:4326, e exibe num mapa Leaflet
com player (play/pause + slider de timeline), igual ao comportamento do
RAS Mapper.

## Como o pipeline funciona

1. Você sobe os `.tif` pelo Django Admin (um por timestep).
2. O timestamp é extraído automaticamente do nome do arquivo
   (`Depth__03APR2025_17_00_00__Terrain_NEW_DSM.tif` → 2025-04-03 17:00:00).
3. Ao processar (via action do admin), o sistema:
   - Calcula o range global de profundidade (todos os timesteps), para a
     escala de cor não "pular" entre frames.
   - Reprojeta cada GeoTIFF de EPSG:31982 (ou o que for) para EPSG:4326.
   - Recorta para a área molhada (+ margem), reduzindo bastante o tamanho
     do arquivo final.
   - Coloriza por profundidade (paleta azul-claro → roxo, estilo RAS
     Mapper) e salva como PNG RGBA com transparência onde não há água.
4. A página do viewer busca a lista de timesteps via API JSON e desenha
   cada PNG como `L.imageOverlay` no Leaflet, trocando o overlay conforme
   o usuário usa o play ou arrasta o slider.

## Instalação no seu projeto (`myproject_new`)

### 1. Copiar o app

Copie a pasta `AppRas/` inteira para a raiz do seu projeto Django,
no mesmo nível de `AppGeo` e `adminApp`.

### 2. Instalar dependências

```bash
pip install rasterio numpy pillow matplotlib
```

> Obs: `rasterio` já requer GDAL, que você já deve ter instalado já que
> usa GeoDjango. Se dor de cabeça com instalação no Windows, considere
> rodar isso dentro do mesmo container/WSL2 que você já usa para o
> HEC-RAS Docker.

### 3. settings.py

```python
INSTALLED_APPS = [
    ...
    "AppRas",
]
```

Confirme que `MEDIA_URL` e `MEDIA_ROOT` estão configurados (provavelmente
já estão, já que você tem upload de imagens em outros lugares do projeto):

```python
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

### 4. urls.py principal

```python
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    ...
    path("flood/", include("AppRas.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### 5. Template base

O template `simulation_viewer.html` usa `{% extends "base.html" %}` com
os blocos `title`, `extra_head` e `content`. Ajuste esses nomes de bloco
se o seu `base.html` usar nomes diferentes.

### 6. Migrations

```bash
python manage.py makemigrations AppRas
python manage.py migrate
```

### 7. Criar superuser (se ainda não tiver) e usar

```bash
python manage.py runserver
```

No admin (`/admin/`), crie uma **Simulação de Inundação**, suba os `.tif`
no inline de timesteps, salve, depois use a action **"Processar GeoTIFFs"**
na lista de simulações.

Acesse o resultado em `/flood/<id>/`.

## Alternativa: importar uma pasta inteira de uma vez

Se você já tem uma pasta cheia de exports do RAS Mapper (em vez de subir
um por um pelo admin):

```bash
python manage.py import_flood_simulation \
    --folder "C:\caminho\para\export_rasmapper" \
    --name "Cheia Rio X - Abril 2025"
```

Isso cria a simulação, importa todos os `.tif` que casem com o padrão
`Depth__*.tif`, e já dispara o processamento.

## Estrutura de arquivos

```
AppRas/
├── models.py              # FloodSimulation, FloodTimestep
├── raster_processing.py   # Núcleo: reprojeção + colorização (rasterio)
├── services.py             # Orquestra processamento usando os models
├── admin.py                 # Upload + action "Processar" no Django Admin
├── views.py                  # Página do viewer + API JSON de timesteps
├── urls.py
├── templates/AppRas/
│   ├── simulation_list.html
│   └── simulation_viewer.html   # Mapa Leaflet + player (play/pause/slider)
└── management/commands/
    └── import_flood_simulation.py   # Importação em lote via CLI
```

## Próximos passos sugeridos

- **Performance para muitos timesteps**: se uma simulação tiver
  dezenas/centenas de frames, pré-carregar todos os PNGs no browser antes
  de iniciar o play evita "engasgos" — dá pra adicionar isso no JS com um
  loop de `Image()` antes de habilitar o botão play.
- **Celery**: como você já usa Celery/Redis no projeto, o processamento
  (`process_simulation_timesteps`) é uma função pura que pode virar uma
  task assíncrona facilmente — assim o upload no admin não trava
  esperando o GDAL processar todos os arquivos.
- **Múltiplas variáveis**: hoje o pipeline assume "Depth" (profundidade).
  Se quiser também velocidade (Velocity) ou WSE, o mesmo
  `raster_processing.py` serve, só trocando a paleta de cores e o texto
  da legenda.
