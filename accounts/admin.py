from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'is_premium', 'is_staff', 'date_joined']
    list_editable = ['is_premium']
    ordering = ['-date_joined']
    fieldsets = (        
        (None, {'fields': ('email', 'password')}),
        ('Личные данные', {'fields': ('username',)}),
        ('Премиум', {'fields': ('is_premium', 'premium_until')}),
        ('Права', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'password1', 'password2')}),
    )
    search_fields = ['email', 'username']
    filter_horizontal = ['groups', 'user_permissions']
