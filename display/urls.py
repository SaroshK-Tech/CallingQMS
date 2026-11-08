from django.urls import path
from . import views

urlpatterns = [
    path('', views.full_display, name='full_display'),
    path('api/calls/', views.api_now_serving, name='api_now_serving'),
    path('api/ads/', views.api_advertisements, name='api_advertisements'),
]
