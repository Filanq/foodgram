"""
URL configuration for foodgram project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf.urls.static import static
from django.conf import settings
from rest_framework.routers import DefaultRouter
import re
from urllib.parse import urlsplit
from django.views.static import serve

from app.views import (UsersList, login, logout, RecipesList, get_ingredient, get_ingredients)

router = DefaultRouter()
router.register('users', UsersList)
router.register('recipes', RecipesList)

urlpatterns = ([
    path('api/', include(router.urls)),
    path('api/auth/token/login/', login),
    path('api/auth/token/logout/', logout),
    path('api/ingredients/', get_ingredients),
    path('api/ingredients/<int:pk>/', get_ingredient),
    path('admin/', admin.site.urls),
    re_path(r"^%s(?P<path>.*)$" % re.escape(settings.MEDIA_URL.lstrip("/")), serve, kwargs={'document_root':
                                                                                                settings.MEDIA_ROOT}),
    re_path(r"^%s(?P<path>.*)$" % re.escape(settings.STATIC_URL.lstrip("/")), serve, kwargs={'document_root':
                                                                                                 settings.STATIC_ROOT}),
])
