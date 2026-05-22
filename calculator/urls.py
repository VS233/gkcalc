from django.urls import path
from . import views

app_name = 'calculator'

urlpatterns = [
    path('', views.index, name='index'),
    path('guide/', views.guide, name='guide'),
    path('share/<uuid:uuid>/', views.doll_public, name='doll_public'),
    path('api/slot/select/', views.api_select_item, name='api_select_item'),
    path('api/slot/stats/', views.api_get_slot_stats, name='api_get_slot_stats'),
    path('api/slot/save/', views.api_save_slot_stats, name='api_save_slot_stats'),
    path('api/skill/update/', views.api_update_skill, name='api_update_skill'),
    path('api/skill/reset/', views.api_reset_skills, name='api_reset_skills'),
    path('api/doll/save/', views.api_save_doll, name='api_save_doll'),
    path('api/doll/load/', views.api_load_doll, name='api_load_doll'),
    path('api/doll/snapshot/', views.api_create_snapshot, name='api_create_snapshot'),
    path('api/doll/level/', views.api_set_level, name='api_set_level'),
    path('api/doll/detailed/', views.api_get_detailed_stats, name='api_get_detailed_stats'),
    path('api/set/equip/', views.api_equip_set, name='api_equip_set'),
    path('api/item/stats/', views.api_get_item_stats, name='api_get_item_stats'),
    path('api/comp/doll/', views.api_get_comparison_doll, name='api_get_comparison_doll'),
    path('api/comp/copy/', views.api_copy_to_comparison, name='api_copy_to_comparison'),
    path('api/doll/copy/', views.api_copy_doll, name='api_copy_doll'),
]