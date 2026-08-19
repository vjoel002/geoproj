from django.db import models

# ++++++++++++++++++++++++++++++ Exemplo de envio de dados para o banco ++++++++++++++++++++++++++++++

class Admin(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=100)

    def __str__(self):
        return self.name

# ++++++++++++++++++++++++++++++ Administração do blog ++++++++++++++++++++++++++++++

from django.db import models

class Post(models.Model):
    STATUS = [('rascunho', 'Rascunho'), ('publicado', 'Publicado'), ('agendado', 'Agendado')]
    VISIBILIDADE = [('publico', 'Público'), ('privado', 'Privado'), ('senha', 'Protegido')]

    titulo = models.CharField(max_length=100)
    conteudo = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default='rascunho')
    visibilidade = models.CharField(max_length=20, choices=VISIBILIDADE, default='publico')
    imagem_destaque = models.ImageField(upload_to='posts/', blank=True, null=True)
    publicar_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.titulo

# ++++++++++++++++++++++++++++++ Página "Sobre" ++++++++++++++++++++++++++++++  

class Sobre(models.Model):
    nome = models.CharField(max_length=100)
    titulo_profissional = models.CharField(max_length=150, blank=True)
    bio = models.TextField(blank=True)
    foto = models.ImageField(upload_to='sobre/', blank=True, null=True)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    linkedin = models.URLField(blank=True)
    github = models.URLField(blank=True)
    lattes = models.URLField(blank=True)
    portfolio = models.URLField(blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name = 'Sobre'