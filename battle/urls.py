from django.urls import path
from . import views

app_name = 'battle'

urlpatterns = [
    path('api/simulate/', views.api_simulate, name='api_simulate'),
]