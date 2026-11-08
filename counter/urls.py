from django.urls import path

from . import views

urlpatterns = [
    path('dashboard/', views.counter_dashboard, name='counter_dashboard'),
    path('display/<int:counter_id>/', views.counter_display, name='counter_display'),
    path('api/state/', views.dashboard_state, name='counter_dashboard_state'),
    path('api/feedback/', views.submit_feedback, name='counter_submit_feedback'),
    path('api/ticket/<int:ticket_id>/', views.api_ticket_status, name='api_ticket_status'),
]
