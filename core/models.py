from django.db import models
from django.core.exceptions import ValidationError


class CommitteeMember(models.Model):
    """
    Default PV (محضر مداولات) committee members configured once in
    Settings — typically the institute director(s) and any other
    permanent members who sit on every deliberation committee, each
    with their fixed الصفة (role).

    The trainer (الأستاذ المكون) and the client company's representative
    (ممثل الشركة المتعاقد معها) are NOT stored here: they change with
    every session and are entered directly on the PV form instead
    (see documents.forms / documents.views set_committee_view).
    """

    full_name = models.CharField(max_length=200, verbose_name="الاسم و اللقب")
    role = models.CharField(
        max_length=150,
        verbose_name="الصفة",
        help_text="مثال : مدير المؤسسة، مدير الدراسات و العلاقات العامة",
    )
    order = models.PositiveIntegerField(default=0, verbose_name="الترتيب")
    is_active = models.BooleanField(
        default=True,
        verbose_name="نشط",
        help_text="الأعضاء غير النشطين لا يظهرون تلقائياً في محاضر المداولات الجديدة.",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "عضو افتراضي في اللجنة"
        verbose_name_plural = "الأعضاء الافتراضيون في اللجنة (محضر المداولات)"

    def __str__(self):
        return f"{self.full_name} — {self.role}"


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

    pv_notification_recipients = models.TextField(
        blank=True,
        verbose_name="Destinataires notification PV",
        help_text=(
            "Adresses email qui recevront une notification à chaque génération "
            "d'un PV de délibération (une adresse par ligne, ou séparées par des virgules)."
        ),
    )

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

    def get_pv_notification_recipients_list(self):
        """
        Parse `pv_notification_recipients` (one per line and/or comma-separated)
        into a deduplicated list of clean email addresses.
        """
        if not self.pv_notification_recipients:
            return []
        raw = self.pv_notification_recipients.replace(",", "\n").splitlines()
        seen = set()
        recipients = []
        for entry in raw:
            email = entry.strip()
            if email and email.lower() not in seen:
                seen.add(email.lower())
                recipients.append(email)
        return recipients