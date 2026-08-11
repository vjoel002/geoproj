# Mandar dados para o banco
formBlog.html --> views.py --> models.py chamando models

# instalar todas as depencias ao mesmo tempo
pip install -r requirements.txt

``` 
Acessar a área administrativa
http://127.0.0.1:8000/admin_dashboard/

```
# Subir simulações
```bash
python manage.py import_flood_simulation --folder "C:\Users\joelv\Desktop\temp\PROJET\ComHec\newfolde1" --name "nome do barragem"
python manage.py import_flood_simulation --folder "C:\Users\joelv\Desktop\temp\PROJET\ComHec\newfolde1" --name "Cheia AUG 2026" --id 1
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

