from django.db import models
from django.core.exceptions import ValidationError

class InstituteInfo(models.Model):
    """Singleton model for institute configuration"""
    name_fr = models.CharField(max_length=200, verbose_name="Nom de l'institut (FR)")
    name_ar = models.CharField(max_length=200, verbose_name="Nom de l'institut (AR)")
    logo = models.ImageField(upload_to='institute/', blank=True, null=True)
    address = models.TextField(verbose_name="Adresse")
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    nif = models.CharField(max_length=20, verbose_name="NIF")
    nis = models.CharField(max_length=20, verbose_name="NIS")
    rc = models.CharField(max_length=20, verbose_name="RC")
    article_imposition = models.CharField(max_length=20, verbose_name="Article d'imposition")
    rib = models.CharField(max_length=50, verbose_name="RIB")
    accreditation_number = models.CharField(max_length=50, verbose_name="Numéro d'agrément")
    accreditation_date = models.DateField(verbose_name="Date d'agrément")
    if_number = models.CharField(max_length=20, verbose_name="Numéro IF")
    footer_fr = models.TextField(blank=True, verbose_name="Pied de page (FR)")
    footer_ar = models.TextField(blank=True, verbose_name="Pied de page (AR)")
    
    class Meta:
        verbose_name = "Informations de l'institut"
        verbose_name_plural = "Informations de l'institut"
    
    def save(self, *args, **kwargs):
        if not self.pk and InstituteInfo.objects.exists():
            raise ValidationError("Une seule instance d'informations institut est autorisée")
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.name_fr
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance"""
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            return None