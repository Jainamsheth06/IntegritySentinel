from django.urls import path
from . import views

urlpatterns = [
    # Dashboard Home
    path('', views.home, name='home'),


    # Update Action Risk Level (High / Medium / Low)
    path('update-risk-level/<str:log_type>/<int:item_id>/', views.update_risk_level, name='update_risk_level'),

    # Delete Log Item (Admin / Superuser fallback)
    path('delete/<str:log_type>/<int:item_id>/', views.delete_log, name='delete_log'),

    # Form Submission Endpoints
    path('submit/', views.form_submit, name='form_submit'),
    path('submit/transaction/', views.form_submit, name='submit_transaction'),
    path('submit/email/', views.submit_email, name='submit_email'),
    path('submit/call/', views.submit_call, name='submit_call'),
    path('submit/message/', views.submit_message, name='submit_message'),

    # REST APIs
    path('api/check-fraud/', views.FraudCheckAPIView.as_view(), name='check_fraud_api'),
    path('api/check/fraud/', views.FraudCheckAPIView.as_view(), name='check_fraud_api_alt'),
    path('api/check/email/', views.EmailFraudAPIView.as_view(), name='check_email_api'),
    path('api/check/call/', views.CallFraudAPIView.as_view(), name='check_call_api'),
    path('api/check/message/', views.MessageFraudAPIView.as_view(), name='check_message_api'),
]
