from rest_framework import serializers
from .models import TransactionCheck, EmailFraudCheck, CallFraudCheck, MessageFraudCheck


class TransactionCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionCheck
        fields = ['id', 'user', 'user_email', 'amount', 'card_number', 'ip_address', 'is_fraud', 'risk_score', 'risk_level', 'checked_at']
        read_only_fields = ['is_fraud', 'risk_score', 'risk_level', 'checked_at']


class EmailFraudCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailFraudCheck
        fields = ['id', 'user', 'sender_email', 'subject', 'body_text', 'is_fraud', 'risk_score', 'risk_level', 'detected_reasons', 'checked_at']
        read_only_fields = ['is_fraud', 'risk_score', 'risk_level', 'detected_reasons', 'checked_at']


class CallFraudCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallFraudCheck
        fields = ['id', 'user', 'phone_number', 'call_context', 'is_fraud', 'risk_score', 'risk_level', 'detected_reasons', 'checked_at']
        read_only_fields = ['is_fraud', 'risk_score', 'risk_level', 'detected_reasons', 'checked_at']


class MessageFraudCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageFraudCheck
        fields = ['id', 'user', 'sender_info', 'message_text', 'is_fraud', 'risk_score', 'risk_level', 'detected_reasons', 'checked_at']
        read_only_fields = ['is_fraud', 'risk_score', 'risk_level', 'detected_reasons', 'checked_at']
