from django.urls import path

from . import views

urlpatterns = [
    path('<str:ticket_number>/', views.public_feedback, name='public_feedback'),
]
