from rest_framework import serializers
from .models import FraudCase


class FraudCaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FraudCase
        fields = [
            'id', 'case_id', 'user', 'victim_name', 'victim_email', 'victim_phone',
            'fraud_category', 'suspect_identity', 'loss_amount', 'recovered_amount',
            'description', 'evidence_notes', 'priority', 'status', 'is_solved',
            'assigned_officer', 'arrest_location', 'resolution_summary',
            'created_at', 'updated_at', 'solved_at'
        ]
        read_only_fields = ['case_id', 'created_at', 'updated_at', 'solved_at']
