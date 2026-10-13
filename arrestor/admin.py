from django.contrib import admin
from django.utils import timezone
from .models import FraudCase


@admin.register(FraudCase)
class FraudCaseAdmin(admin.ModelAdmin):
    list_display = (
        'case_id',
        'victim_name',
        'victim_email',
        'fraud_category',
        'priority',
        'status',
        'is_solved',
        'loss_amount',
        'recovered_amount',
        'assigned_officer',
        'created_at',
    )
    list_filter = ('status', 'is_solved', 'priority', 'fraud_category', 'created_at')
    search_fields = (
        'case_id',
        'victim_name',
        'victim_email',
        'victim_phone',
        'suspect_identity',
        'assigned_officer',
        'arrest_location',
        'description',
    )
    list_editable = ('priority', 'status', 'is_solved')
    actions = ['mark_as_completed', 'mark_as_investigating']

    @admin.action(description="Mark selected cases as Solved & Completed")
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(
            status='COMPLETED',
            is_solved=True,
            solved_at=timezone.now()
        )
        self.message_user(request, f"Successfully marked {updated} cases as COMPLETED.")

    @admin.action(description="Mark selected cases as Under Investigation")
    def mark_as_investigating(self, request, queryset):
        updated = queryset.update(
            status='INVESTIGATING',
            is_solved=False
        )
        self.message_user(request, f"Marked {updated} cases as UNDER INVESTIGATION.")
