from django.db import models

class Client(models.Model):
    name = models.CharField(max_length=200, verbose_name="Raison sociale")
    name_ar = models.CharField(max_length=200, blank=True, verbose_name="Raison sociale (AR)")
    address = models.TextField(verbose_name="Adresse")
    city = models.CharField(max_length=100, verbose_name="Ville")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    contact_person = models.CharField(max_length=100, blank=True, verbose_name="Personne de contact")
    
    # Legal fields
    nif = models.CharField(max_length=20, blank=True, verbose_name="NIF")
    nis = models.CharField(max_length=20, blank=True, verbose_name="NIS")
    rc = models.CharField(max_length=20, blank=True, verbose_name="RC")
    
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def full_address(self):
        return f"{self.address}, {self.city}"
    
    @property
    def session_count(self):
        return self.session_set.count()