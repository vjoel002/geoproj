from django.db import models

class Contato(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=100)
    message = models.CharField(max_length=3000)
'''    lida = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)'''

'''    def __str__(self):
        return f"{self.email} — {self.criado_em.strftime('%d/%m/%Y %H:%M')}"'''

'''    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Mensagem'''


def __str__(self):
        return self.name
