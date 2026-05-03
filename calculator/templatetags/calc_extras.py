from django import template
register = template.Library()

@register.filter
def get_item(dictionary, key):
    """{{ my_dict|get_item:key }} — получить значение по ключу в шаблоне."""
    if dictionary is None:
        return None
    return dictionary.get(key)
