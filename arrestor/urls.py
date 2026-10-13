from django.urls import path
from . import views

urlpatterns = [
    # Main Arrestor Dashboard (With & Without Login)
    path('', views.arrestor_home, name='arrestor_home'),

    # File a Case / Incident Report
    path('submit/', views.submit_case, name='submit_case'),

    # Track Case Status (Public & Logged In)
    path('track/', views.track_case, name='track_case'),

    # Update Priority in Action column (High, Medium, Low)
    path('update-priority/<int:case_id>/', views.update_case_priority, name='update_case_priority'),

    # Delete Case Fallback
    path('delete/<int:case_id>/', views.delete_case, name='delete_case'),

    # REST APIs
    path('api/cases/', views.CaseListCreateAPIView.as_view(), name='arrestor_api_cases'),
]
