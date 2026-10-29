from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('pedagogical', 'Agent pédagogique'),
        ('staff', 'Agent Administratif'),
        ('trainer', 'Formateur'),
        ('viewer', 'Consultant'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateur"
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_role_display()}"
    
    def is_admin(self):
        """Strict administrator only (user management, formation creation…)."""
        return self.role == 'admin'

    def is_pedagogical(self):
        return self.role == 'pedagogical'

    def has_admin_rights(self):
        """Administrator-level operational rights: admin + pedagogical agent.

        Everything an admin can do EXCEPT what is explicitly kept for
        `is_admin()` (user accounts, creating / deleting catalogue formations)
        and what goes through the approval workflow (editing a formation).
        """
        return self.role in ['admin', 'pedagogical']

    def is_staff_or_admin(self):
        return self.role in ['admin', 'pedagogical', 'staff']

    def is_trainer_or_above(self):
        return self.role in ['admin', 'pedagogical', 'staff', 'trainer']

    def can_manage_sessions(self):
        return self.role in ['admin', 'pedagogical', 'staff']

    def can_edit_scores(self):
        return self.role in ['admin', 'pedagogical', 'staff', 'trainer']

    def can_generate_documents(self):
        return self.role in ['admin', 'pedagogical', 'staff']

    def can_archive_sessions(self):
        return self.role in ['admin', 'pedagogical']

    # ── Catalogue formations (approval workflow) ───────────────────────────
    def can_create_formation(self):
        return self.role == 'admin'

    def can_delete_formation(self):
        return self.role == 'admin'

    def needs_approval_for_formation_edit(self):
        return self.role == 'pedagogical'