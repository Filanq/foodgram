import base64
import binascii
import random
import tempfile
from django.core.files.base import ContentFile
from django.db import models
from django.contrib.auth.models import AbstractBaseUser
import os
from django.core.validators import MinValueValidator


class User(AbstractBaseUser):
    username = models.CharField(max_length=150, unique=True)
    email = models.EmailField(max_length=254, unique=True)
    password = models.CharField(max_length=2000)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    avatar = models.ImageField(upload_to="img/avatar", null=True)
    REQUIRED_FIELDS = ('email', 'password', 'first_name', 'last_name')
    USERNAME_FIELD = 'username'

    class Meta:
        verbose_name_plural = 'Пользователи'
        verbose_name = 'пользователь'

    def save_base64_image(self, base64_string):
        ext = base64_string.strip().split('data:image/')[1].split(';')[0]
        old_filename = str(self.avatar).split('/')[-1]
        if old_filename and os.path.exists('/home/app/backend/media/img/avatar/' + old_filename):
            os.remove('/home/app/backend/media/img/avatar/' + old_filename)

        base64_string = base64_string.split(';base64,')[1]
        decoded_img = base64.b64decode(base64_string)

        self.avatar.save(f'{random.randint(100000, 999999999999)}.' + ext, ContentFile(decoded_img), save=True)

    def __str__(self):
        return self.first_name + ' ' + self.last_name + ' (' + self.username + ')'


class Favorite(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name="fav_us")
    recipe = models.ForeignKey('Recipe', on_delete=models.CASCADE, related_name="fav_recipe")

    class Meta:
        verbose_name_plural = 'Избранные'
        verbose_name = 'избранное'

    def __str__(self):
        return (self.user.first_name + ' ' + self.user.last_name + ' (' + self.user.username + ')' + ' | ' +
                self.recipe.name)


class Recipe(models.Model):
    author = models.ForeignKey(to=User, on_delete=models.CASCADE)
    ingredients = models.TextField(default='{}')
    name = models.CharField(max_length=256)
    image = models.ImageField(upload_to="img/recipes", null=True)
    cooking_time = models.IntegerField(validators=[MinValueValidator(1)])
    text = models.TextField()

    class Meta:
        verbose_name_plural = 'Рецепты'
        verbose_name = 'рецепт'

    def save_base64_image(self, base64_string):
        ext = base64_string.strip().split('data:image/')[1].split(';')[0]
        old_filename = str(self.image).split('/')[-1]
        if old_filename and os.path.exists('/home/app/backend/media/img/recipes/' + old_filename):
            os.remove('/home/app/backend/media/img/recipes/' + old_filename)

        base64_string = base64_string.split(';base64,')[1]
        decoded_img = base64.b64decode(base64_string)

        self.image.save(f'{random.randint(100000, 999999999999)}.' + ext, ContentFile(decoded_img), save=True)

    def __str__(self):
        return self.name + ' | ' + self.author.first_name + ' ' + self.author.last_name


class Cart(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name="cart_us")
    recipe = models.ForeignKey(to=Recipe, on_delete=models.CASCADE, related_name="cart_recipe")

    class Meta:
        verbose_name_plural = 'Корзины пользователей'
        verbose_name = 'корзина пользователя'

    def __str__(self):
        return (self.user.first_name + ' ' + self.user.last_name + ' (' + self.user.username + ')' + ' | ' +
                self.recipe.name)


class Ingredient(models.Model):
    name = models.CharField(max_length=150)
    measurement_unit = models.CharField(max_length=150)

    class Meta:
        verbose_name_plural = 'Ингредиенты'
        verbose_name = 'ингредиент'

    def __str__(self):
        return self.name + ' | ' + self.measurement_unit


class Subscribe(models.Model):
    user = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name="subscribe_us")
    subscribe = models.ForeignKey(to=User, on_delete=models.CASCADE, related_name="subscribe_sub")

    class Meta:
        verbose_name_plural = 'Подписки'
        verbose_name = 'подписка'

    def __str__(self):
        return ('Пользователь: ' + self.user.first_name + ' ' + self.user.last_name +
                ' (' + self.user.username + ')' + ' | Подписка: ' + self.subscribe.first_name +
                ' ' + self.subscribe.last_name + ' (' + self.subscribe.username + ')')


class Token(models.Model):
    key = models.CharField(max_length=40, primary_key=True)
    user = models.OneToOneField(
        User, related_name='auth_token',
        on_delete=models.CASCADE
    )
    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super().save(*args, **kwargs)

    @classmethod
    def generate_key(cls):
        return binascii.hexlify(os.urandom(20)).decode()

    def __str__(self):
        return self.key
