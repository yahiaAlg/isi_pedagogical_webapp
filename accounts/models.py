from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
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
        return self.role == 'admin'
    
    def is_staff_or_admin(self):
        return self.role in ['admin', 'staff']
    
    def is_trainer_or_above(self):
        return self.role in ['admin', 'staff', 'trainer']
    
    def can_manage_sessions(self):
        return self.role in ['admin', 'staff']
    
    def can_edit_scores(self):
        return self.role in ['admin', 'staff', 'trainer']
    
    def can_generate_documents(self):
        return self.role in ['admin', 'staff']
    
    def can_archive_sessions(self):
        return self.role == 'admin'