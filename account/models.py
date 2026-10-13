from django.db import models
from django.conf import settings

ROLE_CHOICES = (
    ('detector', 'Fraud Detector (Citizen / Analyst)'),
    ('arrestor', 'Fraud Arrestor (Law Enforcement Officer)'),
)


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='detector')

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} - {self.role}"


class UserRegistration(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=100, unique=True)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='detector')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'User Registration'
        verbose_name_plural = 'User Registrations'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.username}) [{self.role}]"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username
