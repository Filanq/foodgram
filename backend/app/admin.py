from django.contrib import admin
from django.contrib.admin import register
from .models import User, Recipe, Subscribe, Cart, Favorite, Ingredient


@register(User)
class UserAdmin(admin.ModelAdmin):
    search_fields = ['email', 'username']


@register(Recipe)
class RecipesAdmin(admin.ModelAdmin):
    search_fields = ['author', 'name']

    def change_view(self, request, object_id, form_url='', extra_context=None):
        recipe = self.get_object(request, object_id)
        if recipe:
            recipe_info = f"Кол-во в избранных: {len(Favorite.objects.filter(recipe=recipe))}"
            extra_context = extra_context or {}
            extra_context['recipe_info'] = recipe_info

        return super().change_view(request, object_id, form_url, extra_context=extra_context)


@register(Ingredient)
class IngredientsAdmin(admin.ModelAdmin):
    search_fields = ['name']


admin.site.register(Subscribe)
admin.site.register(Cart)
admin.site.register(Favorite)
