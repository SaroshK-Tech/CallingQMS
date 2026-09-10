from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.counter_dashboard, name='counter_dashboard'),
    path('display/<int:counter_id>/', views.counter_display, name='counter_display'),
    path('api/ticket/<int:ticket_id>/', views.api_ticket_status, name='api_ticket_status'),
]
