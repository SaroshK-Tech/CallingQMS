from django.urls import path
from . import views

urlpatterns = [
    path('', views.full_display, name='full_display'),
    path('api/calls/', views.api_recent_calls, name='api_recent_calls'),
    path('api/ads/', views.api_advertisements, name='api_advertisements'),
]
