# Mandar dados para o banco
formBlog.html --> views.py --> models.py chamando models

# instalar todas as depencias ao mesmo tempo
pip install -r requirements.txt

```browser 
Acessar a área administrativa
http://127.0.0.1:8000/admin_dashboard/

acessar a paginas das simulações
http://127.0.0.1:8000/flood/
```
# Subir simulações
```bash
# Terminal do windows
python manage.py import_flood_simulation --folder "C:\Users\joelv\Desktop\temp\PROJET\ComHec\newfolde1" --name "nome do barragem"
python manage.py import_flood_simulation --folder "/caminho" --name "Cheia AUG 2026" --description "Simulação da barragem X considerando cota máxima de 120m, cenário de chuva intensa."

# Terminal do projeto (http://127.0.0.1:8000/terminal/) - Local / WSL
importar_simulacao "/mnt/c/Users/joelv/Desktop/temp/PROJET/ComHec/newfolde1" "Barragem Itaipu" "Cenário de chuva intensa, cota máxima 120m"

# Quando estiver em produção
importar_simulacao "<caminho_da_pasta_no_servidor>" "<nome da barragem>" "<descrição>"
importar_simulacao "/opt/render/project/src/uploads/newfolder1" "Cheia AUG 2026" "Cenário de chuva intensa"
```

# Excluir simulações
```bash
# Entrar no python
python manage.py shell

# importar a classe FloodSimulation
from AppRas.models import FloodSimulation

# Ver quais simulações existem
list(FloodSimulation.objects.values_list("id", "name"))

# deletar por ID
FloodSimulation.objects.get(id=1).delete()
# deletar todas
FloodSimulation.objects.all().delete()
```

# Ver, salvar no requirements e instalar dependencias do projeto

```bash
# ver
python -m pip freeze

# salvar no requirements
python -m pip freeze > requirements.txt

# instalar noprojeto
pip install -r requirements.txt
# Antes de executar requirements, instala libgdal-dev para o GDAL pode ser instalado
sudo apt update
sudo apt install libgdal-dev
# ao instalar as dependencias, se der erro por falta de espaça de disco (tmp do WSL com pouco espaço)
# primeiro limpar o cache do pip
python -m pip cache purge
# segundo verificar se libgdal-dev está instalado
gdal-config --version
# terceiro usar o tmp do pip
mkdir -p ~/pip-tmp
```
# subir ridis no docker
```bash
docker run -d --name redis -p 6379:6379 redis
# confirmar
docker ps
# Rodar o worker
celery -A myproject_new worker -l info
```

## Rodar em desenvolvimento
```bash
redis-server &
daphne -b 0.0.0.0 -p 8000 myproject_new.asgi:application
```


# importar banco do windows para wsl

```bash
# Instalar posgresql no wsl
sudo apt install postgresql postgresql-contrib
psql --version
which pg_lsclusters && pg_lsclusters

# deu certo a instalação o postgis 
# 18 é a versão do postgre instalado e 3 é a versão do postgis a ser instalado
sudo apt install postgis postgresql-18-postgis-3

# deu certo a instalação, no powershell do windows faça:
pg_dump -h localhost -U seu_usuario -F c -f backup.dump nome_do_banco
# confirmar se o arquivo foi gerado de verdade. No powershell
# o arquivo deve ter um tamanho razoável (não 0 bytes)
dir backup.dump

# mo terminal do wsl, faça:
cp /mnt/c/Users/joelv/backup.dump ~/backup.dump
# se depois por algum motivo, quiser desfazer esse dump, faça:
rm ~/backup.dump

# cria o usuário e o banco dentro do Postgres 18 do WSL, já com PostGIS
sudo -u postgres psql
```
## criar o banco
```sql
CREATE USER postgres_local WITH PASSWORD 'sua_senha' SUPERUSER;
CREATE DATABASE NomeDoBanco OWNER postgres_local;
\c NomeDoBanco
CREATE EXTENSION postgis;
\q

# se quiser excluir o banco e/ou o superuser
DROP DATABASE NomeDoBanco;
DROP USER IF EXISTS postgres_local;
```
```bash
pg_restore -U postgres_local -d NomeDoBanco -h localhost ~/backup.dump

# confirmar que os dados chegaram de verdade. Entra no banco:
psql -U postgres_local -d NomeDoBanco -h localhost
```

## E dentro dele, lista as tabelas:

```sql
\l # ver a lista dos bancos
\c nomeDoBanco 
\dt
```
## ver o usuario do banco
```sql
\c nomeDoBanco 
\du
```

# rodar o projeto
```bash
sudo service redis-server start
redis-cli ping
celery -A geoproject worker -l info



