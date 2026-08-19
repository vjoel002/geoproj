import os

from celery import Celery

# Aponta pro mesmo settings.py que o Django usa. Se o seu projeto tiver
# um nome diferente de "geoproject.settings", ajuste essa linha.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "geoproject.settings")

app = Celery("geoproject")

# lê as configurações do Celery a partir do settings.py do Django,
# só as que começam com CELERY_ (CELERY_BROKER_URL, etc)
app.config_from_object("django.conf:settings", namespace="CELERY")

# procura automaticamente por um tasks.py dentro de cada app instalado
# (é assim que ele vai achar o AppRas/tasks.py com a rodar_simulacao_task)
app.autodiscover_tasks()
