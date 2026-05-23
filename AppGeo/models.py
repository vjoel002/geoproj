from mailbox import Message

from django.db import models


class Contato(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField()
    read = models.BooleanField(default=False)
    created_in = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} — {self.created_in.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        ordering = ['-created_in']
        verbose_name = 'Mensagem'



'''class Visit(models.Model):
    ip = models.CharField(max_length=100)
    path = models.CharField(max_length=255)
    user_agent = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.ip'''


class Visita(models.Model):
    pagina = models.CharField(max_length=100)
    ip = models.GenericIPAddressField(null=True, blank=True)
    pais = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.pagina} — {self.ip} — {self.criado_em.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Visita'
    
