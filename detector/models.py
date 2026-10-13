from django.db import models
from django.conf import settings

# Imported from dedicated account app for unified authentication
from account.models import ROLE_CHOICES, UserProfile, UserRegistration



RISK_LEVEL_CHOICES = (
    ('HIGH', 'High'),
    ('MEDIUM', 'Medium'),
    ('LOW', 'Low'),
)


class TransactionCheck(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='transaction_checks')
    user_email = models.EmailField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    card_number = models.CharField(max_length=16)
    ip_address = models.GenericIPAddressField(default='127.0.0.1')
    is_fraud = models.BooleanField(default=False)
    risk_score = models.IntegerField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default='LOW')
    checked_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"[Transaction] {self.user_email} - Level: {self.risk_level} - Fraud: {self.is_fraud}"


class EmailFraudCheck(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='email_checks')
    sender_email = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    body_text = models.TextField()
    is_fraud = models.BooleanField(default=False)
    risk_score = models.IntegerField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default='LOW')
    detected_reasons = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[Email] {self.sender_email} - Level: {self.risk_level} - Risk: {self.risk_score}%"


class CallFraudCheck(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='call_checks')
    phone_number = models.CharField(max_length=30)
    call_context = models.TextField(blank=True)
    is_fraud = models.BooleanField(default=False)
    risk_score = models.IntegerField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default='LOW')
    detected_reasons = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[Call] {self.phone_number} - Level: {self.risk_level} - Risk: {self.risk_score}%"


class MessageFraudCheck(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='message_checks')
    sender_info = models.CharField(max_length=100)
    message_text = models.TextField()
    is_fraud = models.BooleanField(default=False)
    risk_score = models.IntegerField(default=0)
    risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default='LOW')
    detected_reasons = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[SMS] {self.sender_info} - Level: {self.risk_level} - Risk: {self.risk_score}%"