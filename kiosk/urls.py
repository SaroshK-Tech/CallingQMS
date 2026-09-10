from django.urls import path
from . import views

urlpatterns = [
    path('', views.kiosk_screen, name='kiosk'),
    path('api/generate/', views.generate_ticket, name='generate_ticket'),
]
