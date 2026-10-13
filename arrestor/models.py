import random
from django.db import models
from django.conf import settings
from django.utils import timezone


class FraudCase(models.Model):
    CATEGORY_CHOICES = (
        ('FINANCIAL', 'Financial Fraud / UPI Scam'),
        ('DIGITAL_ARREST', 'Digital Arrest & Law Impersonation'),
        ('EMAIL_PHISHING', 'Email Phishing & Banking Lure'),
        ('CALL_SPOOFING', 'Spoofed Call & Parcel Scam'),
        ('SMS_MALWARE', 'Scam SMS / Dangerous APK'),
        ('OTHER', 'Other Cyber Offense'),
    )

    PRIORITY_CHOICES = (
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    )

    STATUS_CHOICES = (
        ('PENDING', 'Pending Review'),
        ('INVESTIGATING', 'Under Investigation'),
        ('ARREST_ISSUED', 'Arrest Action Initiated'),
        ('COMPLETED', 'Completed (Solved & Recovered)'),
        ('CLOSED', 'Closed'),
    )

    case_id = models.CharField(max_length=40, unique=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='arrestor_cases'
    )
    victim_name = models.CharField(max_length=150)
    victim_email = models.EmailField()
    victim_phone = models.CharField(max_length=30, blank=True)
    fraud_category = models.CharField(max_length=40, choices=CATEGORY_CHOICES, default='FINANCIAL')
    suspect_identity = models.CharField(max_length=255, blank=True, help_text="Suspect name, phone, UPI ID, or account details")
    loss_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    recovered_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    description = models.TextField()
    evidence_notes = models.TextField(blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='HIGH')
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PENDING')
    is_solved = models.BooleanField(default=False)
    assigned_officer = models.CharField(max_length=150, default='Cyber Crime Special Cell')
    arrest_location = models.CharField(max_length=150, blank=True)
    resolution_summary = models.TextField(blank=True, help_text="Notes on suspect apprehension, freeze orders, or recovery")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    solved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Fraud Arrest Case'
        verbose_name_plural = 'Fraud Arrest Cases'

    def save(self, *args, **kwargs):
        if not self.case_id:
            rand_suffix = random.randint(1000, 9999)
            self.case_id = f"ARR-{timezone.now().strftime('%Y%m')}-{rand_suffix}"

        if self.status == 'COMPLETED':
            self.is_solved = True
            if not self.solved_at:
                self.solved_at = timezone.now()
        elif self.is_solved and self.status != 'COMPLETED':
            self.status = 'COMPLETED'
            if not self.solved_at:
                self.solved_at = timezone.now()
        elif not self.is_solved and self.status == 'COMPLETED':
            self.is_solved = True

        super().save(*args, **kwargs)

    def __str__(self):
        status_display = "COMPLETED" if self.is_solved or self.status == 'COMPLETED' else self.status
        return f"[{self.case_id}] {self.victim_name} - {self.get_fraud_category_display()} ({status_display})"
