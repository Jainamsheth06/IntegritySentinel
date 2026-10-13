from django.contrib import admin
from .models import TransactionCheck, EmailFraudCheck, CallFraudCheck, MessageFraudCheck



@admin.register(TransactionCheck)
class TransactionCheckAdmin(admin.ModelAdmin):
    list_display = ('user', 'user_email', 'amount', 'risk_score', 'risk_level', 'is_fraud', 'checked_at')
    list_filter = ('risk_level', 'is_fraud', 'checked_at', 'user')
    search_fields = ('user__username', 'user_email', 'card_number')


@admin.register(EmailFraudCheck)
class EmailFraudCheckAdmin(admin.ModelAdmin):
    list_display = ('user', 'sender_email', 'subject', 'risk_score', 'risk_level', 'is_fraud', 'checked_at')
    list_filter = ('risk_level', 'is_fraud', 'checked_at', 'user')
    search_fields = ('user__username', 'sender_email', 'subject', 'body_text')


@admin.register(CallFraudCheck)
class CallFraudCheckAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'risk_score', 'risk_level', 'is_fraud', 'checked_at')
    list_filter = ('risk_level', 'is_fraud', 'checked_at', 'user')
    search_fields = ('user__username', 'phone_number', 'call_context')


@admin.register(MessageFraudCheck)
class MessageFraudCheckAdmin(admin.ModelAdmin):
    list_display = ('user', 'sender_info', 'risk_score', 'risk_level', 'is_fraud', 'checked_at')
    list_filter = ('risk_level', 'is_fraud', 'checked_at', 'user')
    search_fields = ('user__username', 'sender_info', 'message_text')

