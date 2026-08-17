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


class PVDefaultSignatory(models.Model):
    """
    Default committee member ("membre du comité de délibération") suggested
    on every محضر مداولات (PV) — e.g. the institute's director(s).

    These are configured once in Settings and re-used as pre-filled,
    editable rows every time a PV committee is built. The trainer (pulled
    live from the session) and the client's company representative are
    intentionally NOT stored here — they are entered fresh on each PV.
    """

    full_name = models.CharField(max_length=150, verbose_name="الاسم و اللقب")
    role = models.CharField(max_length=150, verbose_name="الصفة")
    order = models.PositiveIntegerField(default=0, verbose_name="Ordre")
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Décochez pour retirer ce membre des propositions par défaut sans le supprimer.",
    )

    class Meta:
        verbose_name = "Membre par défaut du PV"
        verbose_name_plural = "Membres par défaut du PV"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.full_name} — {self.role}"


class SequenceCounter(models.Model):
    """
    Generic, race-safe numbering counter shared by every document sequencer
    in the app. One row per (kind, period_key) — e.g. kind="pv",
    period_key="2026-08" (resets every month) or kind="certificate",
    period_key="2026" (resets every year). Values are never reused, even
    if a document is later deleted/regenerated, so numbers stay unique and
    strictly increasing within their own period.

    Three independent sequencers currently use this counter (see
    core/sequencing.py):
    - "pv" — محضر مداولات (PV) reference, one counter per calendar month.
    - "certificate" — شهادة / attestation number, one counter per year.
    - "mission_order" — ordre de mission archival number, one counter per year.
    """

    KIND_CHOICES = [
        ("pv", "Procès-verbal (PV) de délibération"),
        ("certificate", "Attestation / Certificat"),
        ("mission_order", "Ordre de mission"),
    ]

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name="Type")
    period_key = models.CharField(
        max_length=20,
        verbose_name="Période",
        help_text=(
            "Clé de la période sur laquelle le compteur est remis à zéro "
            "(ex. '2026-08' pour un compteur mensuel, '2026' pour un compteur annuel)."
        ),
    )
    last_value = models.PositiveIntegerField(default=0, verbose_name="Dernière valeur")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Compteur de séquence"
        verbose_name_plural = "Compteurs de séquence"
        constraints = [
            models.UniqueConstraint(
                fields=["kind", "period_key"], name="unique_sequence_kind_period"
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.period_key} → {self.last_value}"

    @classmethod
    def next_value(cls, kind, period_key):
        """
        Atomically allocate and return the next integer in the
        (kind, period_key) sequence.

        Safe under concurrent requests: the increment is a single
        UPDATE ... SET last_value = last_value + 1 (an F() expression)
        wrapped in a transaction, so two callers racing for the same
        (kind, period_key) can never be handed the same number — every
        supported backend serializes that UPDATE at the row (or, for
        SQLite, whole-database) level.

        On SQLite specifically, a burst of simultaneous writers can still
        surface as a transient "database is locked" OperationalError
        rather than a silent wait (Postgres deployments — the production
        target — block and retry internally and never hit this path). A
        few short, jittered retries absorb that burst without ever
        allowing a duplicate or skipped number: each retry re-attempts
        the whole atomic increment from scratch.
        """
        import random
        import time

        from django.db import OperationalError, transaction
        from django.db.models import F

        attempts = 5
        for attempt in range(attempts):
            try:
                with transaction.atomic():
                    counter, _ = cls.objects.get_or_create(
                        kind=kind, period_key=period_key
                    )
                    cls.objects.filter(pk=counter.pk).update(
                        last_value=F("last_value") + 1
                    )
                    counter.refresh_from_db(fields=["last_value"])
                    return counter.last_value
            except OperationalError:
                if attempt == attempts - 1:
                    raise
                time.sleep(0.05 * (attempt + 1) + random.uniform(0, 0.05))