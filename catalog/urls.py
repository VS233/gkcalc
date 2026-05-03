from django.urls import path
from django.http import JsonResponse
from .models import Item

app_name = 'catalog'

def items_by_slot(request):
    slot_type = request.GET.get('slot_type', '')
    items = list(Item.objects.filter(slot_type=slot_type, is_active=True).values('id', 'name'))
    return JsonResponse({'items': items})

urlpatterns = [
    path('items/', items_by_slot, name='items_by_slot'),
]
