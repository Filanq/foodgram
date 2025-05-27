import json
import os
import re

from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import render, HttpResponse, HttpResponseRedirect, redirect
from rest_framework import viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from .serializers import UserSerializer, RecipeSerializer, IngredientSerializer
from .models import User, Subscribe, Recipe, Ingredient, Cart, Favorite, Token
from django.http import Http404
from rest_framework import status
from django.core.exceptions import RequestDataTooBig, ValidationError


def get_user(request, throw_exception=True):
    if request.META.get('HTTP_AUTHORIZATION'):
        token = request.META.get('HTTP_AUTHORIZATION').split('Token ')[1]
    else:
        if throw_exception:
            return Response({"detail": "Учетные данные не были предоставлены."}, 401)
        else:
            return None
    if not token:
        if throw_exception:
            return Response({"detail": "Учетные данные не были предоставлены."}, 401)
        else:
            return None
    elif not Token.objects.filter(key=token).exists():
        if throw_exception:
            return Response({"detail": "Учетные данные не были предоставлены."}, 401)
        return None
    token = Token.objects.get(key=token)
    return token.user


class RecipesList(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer

    def list(self, request, *args, **kwargs):
        curr_user = get_user(request, throw_exception=False)
        page = request.GET.get('page', 1)
        limit = request.GET.get('limit', 3)
        is_favorited = request.GET.get('is_favorited', 0)
        is_in_shopping_cart = request.GET.get('is_in_shopping_cart', 0)
        author = request.GET.get('author', 0)
        page = int(page)
        limit = int(limit)
        is_favorited = int(is_favorited)
        is_in_shopping_cart = int(is_in_shopping_cart)
        author = int(author)
        recipes = Recipe.objects.all()
        recipes_count = Recipe.objects.count()

        if is_favorited and not isinstance(curr_user, Response):
            favorite = list(map(lambda x: x.recipe, Favorite.objects.filter(user=curr_user)))
            recipes = list(filter(lambda recipe: recipe in favorite, recipes))
            recipes_count = len(recipes)
        if is_in_shopping_cart and not isinstance(curr_user, Response):
            cart = list(map(lambda x: x.recipe, Cart.objects.filter(user=curr_user)))
            recipes = list(filter(lambda recipe: recipe in cart, recipes))
            recipes_count = len(recipes)
        if author:
            recipes = list(filter(lambda recipe: recipe.author_id == author, recipes))
            recipes_count = len(recipes)
        recipes = recipes[::-1][limit * (page - 1):limit + (limit * (page - 1))]

        serializer = self.get_serializer(recipes, many=True)
        recipes = serializer.data
        for key in range(0, len(recipes)):
            rec_user = User.objects.filter(pk=int(recipes[key]['author']))
            if rec_user.exists():
                rec_user = rec_user[0]
            else:
                Recipe.objects.get(pk=int(recipes[key]['id'])).delete()
                del recipes[key]
                continue
            user_ser = UserSerializer(rec_user).data
            del user_ser['password']
            del user_ser['last_login']
            recipes[key]['author'] = user_ser
            if not (curr_user is None):
                if Subscribe.objects.filter(user=curr_user, subscribe_id=recipes[key]['author']['id']).exists():
                    recipes[key]['author']['is_subscribed'] = True
                if Cart.objects.filter(user=curr_user, recipe_id=recipes[key]['id']).exists():
                    recipes[key]['is_in_shopping_cart'] = True
                if Favorite.objects.filter(user=curr_user, recipe_id=recipes[key]['id']).exists():
                    recipes[key]['is_favorited'] = True
            if "is_subscribed" not in recipes[key]['author']:
                recipes[key]['author']['is_subscribed'] = False
            if "is_in_shopping_cart" not in recipes[key]:
                recipes[key]['is_in_shopping_cart'] = False
            if "is_favorited" not in recipes[key]:
                recipes[key]['is_favorited'] = False
            ingredients_data = []
            ingredients_string = recipes[key]['ingredients']
            ingredients = json.loads(ingredients_string)
            for (pk, value) in zip(ingredients.keys(), ingredients.values()):
                ingredient = Ingredient.objects.filter(pk=int(pk))
                if ingredient.exists():
                    ingredient = ingredient[0]
                    in_serializer = IngredientSerializer(ingredient)
                    in_data = in_serializer.data
                    in_data['amount'] = int(value)
                    ingredients_data.append(in_data)
                else:
                    ingr = json.loads(ingredients_string)
                    del ingr[pk]
                    ingredients_string = json.dumps(ingr)
            recipes[key]['ingredients'] = ingredients_data

        next_page = page + 1 if recipes_count - (page + 1) * limit >= 0 else page
        prev_page = page - 1 if page > 1 else 1
        return Response({"count": recipes_count,
                         "next": request.get_host() + "/api/recipes/?page=" + str(next_page) +
                                 '&limit=' + str(limit) + "&is_favorited=" + str(is_favorited) +
                                 "&is_in_shopping_cart=" + str(is_in_shopping_cart) + "&author=" + str(author),
                         "previous": request.get_host() + "/api/recipes/?page=" + str(prev_page) +
                                     '&limit=' + str(limit) + "&is_favorited=" + str(is_favorited) +
                                     "&is_in_shopping_cart=" + str(is_in_shopping_cart) + "&author=" + str(author),
                         "results": recipes}, 200)

    def retrieve(self, request, *args, **kwargs):
        user = get_user(request, throw_exception=False)

        try:
            instance = self.get_object()
        except Http404:
            return Response(json.dumps({"detail": "Страница не найдена."}), 401)

        recipe = instance
        serializer = self.get_serializer(recipe)
        recipe = serializer.data
        rec_user = User.objects.filter(pk=recipe['author'])
        if not rec_user.exists():
            instance.delete()
            return Response({"detail": 'Страница не найдена.'}, 404)
        rec_user = rec_user[0]
        user_ser = UserSerializer(rec_user).data
        del user_ser['password']
        del user_ser['last_login']
        user_ser['is_subscribed'] = Subscribe.objects.filter(user=user, subscribe=rec_user).exists()
        recipe['author'] = user_ser
        if not (user is None):
            if Subscribe.objects.filter(user=user, subscribe_id=recipe['author']['id']).exists():
                recipe['author']['is_subscribed'] = True
            if Cart.objects.filter(user=user, recipe_id=recipe['id']).exists():
                recipe['is_in_shopping_cart'] = True
            if Favorite.objects.filter(user=user, recipe_id=recipe['id']).exists():
                recipe['is_favorited'] = True
        if "is_subscribed" not in recipe['author']:
            recipe['author']['is_subscribed'] = False
        if "is_in_shopping_cart" not in recipe:
            recipe['is_in_shopping_cart'] = False
        if "is_favorited" not in recipe:
            recipe['is_favorited'] = False
        ingredients_data = []
        ingredients_string = recipe['ingredients']
        ingredients = json.loads(ingredients_string)
        for (pk, value) in zip(ingredients.keys(), ingredients.values()):
            ingredient = Ingredient.objects.filter(pk=int(pk))
            if ingredient.exists():
                ingredient = ingredient[0]
                in_serializer = IngredientSerializer(ingredient)
                in_data = in_serializer.data
                in_data['amount'] = int(value)
                ingredients_data.append(in_data)
            else:
                ingr = json.loads(ingredients_string)
                del ingr[pk]
                ingredients_string = json.dumps(ingr)
        recipe['ingredients'] = ingredients_data

        return Response(recipe, 200)

    def create(self, request, *args, **kwargs):
        user = get_user(request)
        if isinstance(user, Response):
            return user
        data = request.data
        image = ''
        try:
            image = data['image'].strip()
            del data['image']
        except KeyError:
            image = None
        data['author'] = user.pk
        try:
            data['ingredients'] = json.dumps(data['ingredients'])
        except KeyError:
            return Response({'ingredients': ['Ингредиенты отсутствуют']}, 400)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        s_data = serializer.data
        ingredients = json.loads(data['ingredients'])
        if not ingredients:
            return Response({'ingredients': ['Ингредиенты отсутствуют']}, 400)
        ingredients_res = {}
        ing_errors = []
        ing_errors_flag = False
        for i in range(0, len(ingredients)):
            if int(ingredients[i]['amount']) < 1:
                ing_errors_flag = True
                ing_errors.append({"amount": ["Убедитесь, что это значение больше либо равно 1."]})
            elif not Ingredient.objects.filter(pk=int(ingredients[i]['id'])).exists():
                ing_errors_flag = True
                ing_errors.append({"name": ["Ингредиента не существует."]})
            elif str(ingredients[i]['id']) in ingredients_res:
                ing_errors_flag = True
                ing_errors.append({"name": ["Повторение ингредиента."]})
            else:
                ingredients_res[str(ingredients[i]['id'])] = str(ingredients[i]['amount'])
                ing_errors.append({})
        if ing_errors_flag:
            return Response({'ingredients': ing_errors}, 400)
        s_data['ingredients'] = json.dumps(ingredients_res)

        if not image:
            return Response({'image': ['Загрузите изображение']}, 400)

        s_data['author'] = user
        recipe = Recipe(**s_data)
        recipe.save_base64_image(image)
        recipe.author_id = user.pk
        recipe.save()

        serializer = self.get_serializer(recipe)
        recipe = serializer.data
        user_ser = UserSerializer(user).data
        user_ser['is_subscribed'] = False
        del user_ser['password']
        del user_ser['last_login']
        recipe['author'] = user_ser
        if not (user is None):
            if Subscribe.objects.filter(user=user, subscribe_id=recipe['author']['id']).exists():
                recipe['author']['is_subscribed'] = True
            if Cart.objects.filter(user=user, recipe_id=recipe['id']).exists():
                recipe['is_in_shopping_cart'] = True
            if Favorite.objects.filter(user=user, recipe_id=recipe['id']).exists():
                recipe['is_favorited'] = True
        if "is_subscribed" not in recipe['author']:
            recipe['author']['is_subscribed'] = False
        if "is_in_shopping_cart" not in recipe:
            recipe['is_in_shopping_cart'] = False
        if "is_favorited" not in recipe:
            recipe['is_favorited'] = False
        ingredients_data = []
        ingredients_string = recipe['ingredients']
        ingredients = json.loads(ingredients_string)
        for (pk, value) in zip(ingredients.keys(), ingredients.values()):
            ingredient = Ingredient.objects.filter(pk=int(pk))
            if ingredient.exists():
                ingredient = ingredient[0]
                in_serializer = IngredientSerializer(ingredient)
                in_data = in_serializer.data
                in_data['amount'] = int(value)
                ingredients_data.append(in_data)
            else:
                ingr = json.loads(ingredients_string)
                del ingr[pk]
                ingredients_string = json.dumps(ingr)
        recipe['ingredients'] = ingredients_data

        return Response(recipe, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        user = get_user(request)
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if isinstance(user, Response):
            return user
        if user.pk != instance.author.pk:
            return Response({"detail": 'У вас недостаточно прав для выполнения данного действия.'}, 403)
        data = request.data
        try:
            data['ingredients'] = json.dumps(data['ingredients'])
        except KeyError:
            return Response({'ingredients': ['Ингредиенты отсутствуют']}, 400)
        image = None
        try:
            if data['image'].strip():
                image = data['image']
                del data['image']
        except KeyError:
            image = None
        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        ingredients = json.loads(data['ingredients'])
        if not ingredients:
            return Response({'ingredients': ['Ингредиенты отсутствуют']}, 400)
        ingredients_res = {}
        ing_errors = []
        ing_errors_flag = False
        for i in range(0, len(ingredients)):
            if int(ingredients[i]['amount']) < 1:
                ing_errors_flag = True
                ing_errors.append({"amount": ["Убедитесь, что это значение больше либо равно 1."]})
            elif not Ingredient.objects.filter(pk=int(ingredients[i]['id'])).exists():
                ing_errors_flag = True
                ing_errors.append({"name": ["Ингредиента не существует."]})
            elif str(ingredients[i]['id']) in ingredients_res:
                ing_errors_flag = True
                ing_errors.append({"name": ["Повторение ингредиента."]})
            else:
                ingredients_res[str(ingredients[i]['id'])] = str(ingredients[i]['amount'])
                ing_errors.append({})
        if ing_errors_flag:
            return Response({'ingredients': ing_errors}, 400)
        data['ingredients'] = json.dumps(ingredients_res)

        if image:
            instance.save_base64_image(image)

        instance.text = data['text']
        instance.ingredients = data['ingredients']
        instance.name = data['name']
        instance.cooking_time = data['cooking_time']
        instance.save()

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        recipe = self.get_serializer(instance).data
        user_ser = UserSerializer(user).data
        user_ser['is_subscribed'] = False
        del user_ser['password']
        del user_ser['last_login']
        recipe['author'] = user_ser
        if not (user is None):
            if Subscribe.objects.filter(user=user, subscribe_id=recipe['author']['id']).exists():
                recipe['author']['is_subscribed'] = True
            if Cart.objects.filter(user=user, recipe_id=recipe['id']).exists():
                recipe['is_in_shopping_cart'] = True
            if Favorite.objects.filter(user=user, recipe_id=recipe['id']).exists():
                recipe['is_favorited'] = True
        if "is_subscribed" not in recipe['author']:
            recipe['author']['is_subscribed'] = False
        if "is_in_shopping_cart" not in recipe:
            recipe['is_in_shopping_cart'] = False
        if "is_favorited" not in recipe:
            recipe['is_favorited'] = False
        ingredients_data = []
        ingredients_string = recipe['ingredients']
        ingredients = json.loads(ingredients_string)
        for (pk, value) in zip(ingredients.keys(), ingredients.values()):
            ingredient = Ingredient.objects.filter(pk=int(pk))
            if ingredient.exists():
                ingredient = ingredient[0]
                in_serializer = IngredientSerializer(ingredient)
                in_data = in_serializer.data
                in_data['amount'] = int(value)
                ingredients_data.append(in_data)
            else:
                ingr = json.loads(ingredients_string)
                del ingr[pk]
                ingredients_string = json.dumps(ingr)
        recipe['ingredients'] = ingredients_data

        return Response(recipe, 200)

    def destroy(self, request, *args, **kwargs):
        user = get_user(request)
        if isinstance(user, Response):
            return user
        instance = self.get_object()
        if user.pk != instance.author_id:
            return Response({"detail": "У вас недостаточно прав для выполнения данного действия."}, 403)

        old_filename = str(instance.image).split('/')[-1]
        if old_filename and os.path.exists('/home/app/backend/media/img/recipes/' + old_filename):
            os.remove('/home/app/backend/media/img/recipes/' + old_filename)
        self.perform_destroy(instance)
        return Response({}, 204)

    @action(methods=['get'], detail=False, url_path=r"(?P<pk>\d+)/get-link")
    def get_link(self, request, *args, **kwargs):
        recipe = self.get_object()
        return Response({"short-link": request.get_host() + "/s/" + str(recipe.pk)}, 200)

    @action(methods=['get'], detail=False)
    def download_shopping_cart(self, request, *args, **kwargs):
        user = get_user(request)
        if isinstance(user, Response):
            return user
        recipes = Cart.objects.filter(user=user)
        ings = {}
        for i in recipes:
            ing_data = json.loads(i.recipe.ingredients)
            ings_rec = []
            for (key, value) in zip(ing_data.keys(), ing_data.values()):
                ing = Ingredient.objects.get(pk=int(key))
                if ing.name + ' (' + ing.measurement_unit + ')' in ings:
                    ings[ing.name + ' (' + ing.measurement_unit + ')'] += int(value)
                else:
                    ings[ing.name + ' (' + ing.measurement_unit + ')'] = int(value)
        str_res = ""
        for (key, value) in zip(ings.keys(), ings.values()):
            str_res += "· " + str(key) + ' — ' + str(value) + '\n'
        return HttpResponse(str_res, status=200, headers={"Content-Type": 'text/plain'})

    @action(methods=['post', 'delete'], detail=False, url_path=r"(?P<pk>\d+)/shopping_cart")
    def add_shopping_cart(self, request, *args, **kwargs):
        if request.method == 'POST':
            user = get_user(request)
            if isinstance(user, Response):
                return user
            recipe = self.get_object()
            if Cart.objects.filter(user=user, recipe=recipe).exists():
                return Response({
                    "detail": "Рецепт уже добавлен"
                }, 400)
            cart = Cart(user=user, recipe=recipe)
            cart.save()

            data = self.get_serializer(recipe).data

            return Response({
                "id": data['id'],
                "name": data['name'],
                "image": data['image'],
                "cooking_time": int(data['cooking_time'])
            }, 201)
        elif request.method == 'DELETE':
            user = get_user(request)
            if isinstance(user, Response):
                return user
            recipe = self.get_object()
            if not Cart.objects.filter(user=user, recipe=recipe).exists():
                return Response({
                    "detail": "Рецепт не был добавлен"
                }, 400)

            Cart.objects.get(user=user, recipe=recipe).delete()
            return Response({}, 204)

    @action(methods=['post', 'delete'], detail=False, url_path=r"(?P<pk>\d+)/favorite")
    def favorite(self, request, *args, **kwargs):
        if request.method == 'POST':
            user = get_user(request)
            if isinstance(user, Response):
                return user
            recipe = self.get_object()
            if Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response({
                    "detail": "Рецепт уже добавлен"
                }, 400)
            favorite = Favorite(user=user, recipe=recipe)
            favorite.save()

            data = self.get_serializer(recipe).data

            return Response({
                "id": data['id'],
                "name": data['name'],
                "image": data['image'],
                "cooking_time": int(data['cooking_time'])
            }, 201)
        elif request.method == 'DELETE':
            user = get_user(request)
            if isinstance(user, Response):
                return user
            recipe = self.get_object()
            if not Favorite.objects.filter(user=user, recipe=recipe).exists():
                return Response({
                    "detail": "Рецепт не был добавлен"
                }, 400)

            Favorite.objects.get(user=user, recipe=recipe).delete()
            return Response({}, 204)


class UsersList(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def list(self, request, *args, **kwargs):
        curr_user = get_user(request, throw_exception=False)
        page = request.GET.get('page', 1)
        limit = request.GET.get('limit', 3)
        page = int(page)
        limit = int(limit)
        users = User.objects.all()
        users_count = User.objects.count()
        users = users[limit * (page - 1):limit + (limit * (page - 1))]

        serializer = self.get_serializer(users, many=True)
        users = serializer.data
        for key in range(0, len(users)):
            if not (curr_user is None):
                if Subscribe.objects.filter(user=curr_user, subscribe_id=users[key]['id']).exists():
                    users[key]['is_subscribed'] = True
            if "is_subscribed" not in users[key]:
                users[key]['is_subscribed'] = False
            del users[key]['password']
            del users[key]['last_login']

        next_page = page + 1 if users_count - (page + 1) * limit >= 0 else page
        prev_page = page - 1 if page > 1 else 1
        return Response({"count": users_count,
                         "next": request.get_host() + "/api/users/?page=" + str(next_page) +
                                 '&limit=' + str(limit),
                         "previous": request.get_host() + "/api/users/?page=" + str(prev_page) +
                                     '&limit=' + str(limit),
                         "results": users}, 200)

    def retrieve(self, request, *args, **kwargs):
        curr_user = get_user(request, throw_exception=False)
        subscribes = None

        try:
            instance = self.get_object()
        except Http404:
            return Response({"detail": "Страница не найдена."}, 404)

        serializer = self.get_serializer(instance)
        data = serializer.data

        if not (curr_user is None):
            if Subscribe.objects.filter(user=curr_user, subscribe=instance).exists():
                data["is_subscribed"] = True
        if "is_subscribed" not in data:
            data["is_subscribed"] = False


        del data['password']
        del data['last_login']

        return Response(data, 200)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.data)
        if not re.match(r'^[\w.@+-]+\Z', data['username']):
            return Response({"username": ["Имя пользователя не должно содержать спец. символов"]}, status=400)
        try:
            validate_password(data['password'], data['username'])
        except ValidationError as e:
            return Response({"password": e}, status=400)

        data['password'] = make_password(data['password'])
        user = User(**data)
        user.save()
        data['id'] = user.pk
        del data['password']
        del data['last_login']
        del data['avatar']
        return Response(data, status=status.HTTP_201_CREATED)

    @action(methods=['get'], detail=False, url_path='me')
    def me(self, request):
        user = get_user(request)
        if isinstance(user, Response):
            return user
        serializer = self.get_serializer(user)
        data = serializer.data
        data['is_subscribed'] = False
        del data['password']
        del data['last_login']
        return Response(data, 200)

    @action(methods=['put', 'delete'], detail=False, url_path='me/avatar')
    def avatar(self, request):
        if request.method == 'PUT':
            try:
                data = json.loads(request.body)
            except RequestDataTooBig:
                return Response({"avatar": ['Слишком большой вес фото']}, 400)
            try:
                avatar = data['avatar']
            except KeyError:
                return Response({"avatar": ["Загрузите аватар"]}, 400)
            if not avatar:
                return Response({"avatar": ["Загрузите аватар"]}, 400)

            ext = avatar.strip().split('data:image/')[1].split(';')[0]
            if not (ext == 'png' or ext == 'jpg' or ext == 'jpeg'):
                return Response({"avatar": ['Аватар должен быть в формате png или jpg']}, 400)

            user = get_user(request)
            if isinstance(user, Response):
                return user
            user.save_base64_image(avatar)

            serializer = self.get_serializer(user)

            return Response({"avatar": serializer.data['avatar']}, 200)
        elif request.method == 'DELETE':
            user = get_user(request)
            if isinstance(user, Response):
                return user
            old_filename = str(user.avatar).split('/')[-1]
            if os.path.exists('/home/app/backend/media/img/avatar/' + old_filename) and old_filename:
                os.remove('/home/app/backend/media/img/avatar/' + old_filename)

            user.avatar = None
            user.save()

            return Response({}, 204)

    @action(methods=['post'], detail=False)
    def set_password(self, request):
        user = get_user(request)
        if isinstance(user, Response):
            return user

        data = json.loads(request.body)
        new_password = data['new_password']
        current_password = data['current_password']

        if not current_password:
            return Response({"current_password": ["Введите текущий пароль"]}, 400)

        if not check_password(current_password, user.password):
            return Response({"current_password": ["Текущий пароль отличается от введенного"]}, 400)

        try:
            validate_password(new_password, user.username)
        except ValidationError as e:
            return Response({"new_password": e}, status=400)

        user.password = make_password(new_password)
        user.save()

        return Response({}, 204)

    @action(methods=['post', 'delete'], detail=False, url_path=r"(?P<pk>\d+)/subscribe")
    def subscribe(self, request, *args, **kwargs):
        if request.method == 'POST':
            user = get_user(request)
            if isinstance(user, Response):
                return user
            limit = int(request.GET.get('recipes_limit', 3))
            sub_user = self.get_object()
            if Subscribe.objects.filter(user=user, subscribe=sub_user).exists():
                return Response({
                    "detail": "Вы уже подписаны на этого пользователя"
                }, 400)
            if sub_user.pk == user.pk:
                return Response({
                    "detail": "Вы не можете подписаться на себя."
                }, 400)
            subscribe = Subscribe(user=user, subscribe=sub_user)
            subscribe.save()

            data = self.get_serializer(sub_user).data
            data['is_subscribed'] = True
            recipes = Recipe.objects.filter(author=sub_user)[::-1]
            recipes_count = len(recipes)
            if len(recipes) > limit:
                recipes = recipes[:limit]
            for i in range(len(recipes)):
                recipe_data = RecipeSerializer(recipes[i]).data
                recipes[i] = {
                    "id": recipe_data['id'],
                    "name": recipe_data['name'],
                    "image": recipe_data['image'],
                    "cooking_time": recipe_data['cooking_time']
                }
            data['recipes_count'] = recipes_count
            data['recipes'] = recipes

            del data['password']
            del data['last_login']

            return Response(data, 201)
        elif request.method == 'DELETE':
            user = get_user(request)
            if isinstance(user, Response):
                return user
            sub_user = self.get_object()
            if not Subscribe.objects.filter(user=user, subscribe=sub_user).exists():
                return Response({
                    "detail": "Вы не были подписаны на этого пользователя"
                }, 400)

            Subscribe.objects.get(user=user, subscribe=sub_user).delete()
            return Response({}, 204)

    @action(methods=['get'], detail=False)
    def subscriptions(self, request, *args, **kwargs):
        curr_user = get_user(request)
        if isinstance(curr_user, Response):
            return curr_user
        page = request.GET.get('page', 1)
        limit = request.GET.get('limit', 3)
        recipes_limit = request.GET.get('recipes_limit', 3)
        page = int(page)
        limit = int(limit)
        recipes_limit = int(recipes_limit)
        users = [i.subscribe for i in Subscribe.objects.filter(user=curr_user)]
        users_count = len(users)
        users = users[limit * (page - 1):limit + (limit * (page - 1))]

        serializer = self.get_serializer(users, many=True)
        users = serializer.data
        for key in range(0, len(users)):
            users[key]['is_subscribed'] = True
            del users[key]['password']
            del users[key]['last_login']
            recipes = Recipe.objects.filter(author_id=users[key]['id'])[::-1]
            recipes_count = len(recipes)
            if len(recipes) > recipes_limit:
                recipes = recipes[:recipes_limit]
            for i in range(len(recipes)):
                recipe_data = RecipeSerializer(recipes[i]).data
                recipes[i] = {
                    "id": recipe_data['id'],
                    "name": recipe_data['name'],
                    "image": recipe_data['image'],
                    "cooking_time": recipe_data['cooking_time']
                }
            users[key]['recipes_count'] = recipes_count
            users[key]['recipes'] = recipes

        next_page = page + 1 if users_count - (page + 1) * limit >= 0 else page
        prev_page = page - 1 if page > 1 else 1
        return Response({"count": users_count,
                         "next": request.get_host() + "/api/users/subscriptions/?page=" + str(next_page) +
                                 '&limit=' + str(limit) + '&recipes_limit=' + str(recipes_limit),
                         "previous": request.get_host() + "/api/users/subscriptions/?page=" + str(prev_page) +
                                     '&limit=' + str(limit) + '&recipes_limit=' + str(recipes_limit),
                         "results": users}, 200)


@api_view(['POST'])
def login(request):
    data = request.data
    try:
        email = data['email']
    except KeyError:
        return Response({"email": ["Введите почту."]}, 400)
    try:
        password = data['password']
    except KeyError:
        return Response({"password": ["Введите пароль."]}, 400)

    if User.objects.filter(email=email).exists():
        user = User.objects.get(email=email)
        if check_password(password, user.password):
            if Token.objects.filter(user=user).exists():
                Token.objects.get(user=user).delete()
            token = Token.objects.create(user=user)
            return Response({"auth_token": token.key}, 200)
    return Response({"detail": "Неверные данные"}, 400)


@api_view(['POST'])
def logout(request):
    token = request.META.get('HTTP_AUTHORIZATION').split('Token ')[1]
    if not token:
        return Response({"detail": "Пользователь не авторизован."}, 401)
    elif not Token.objects.filter(key=token).exists():
        return Response({"detail": "Учетные данные не были предоставлены."}, 401)
    token = Token.objects.get(key=token).delete()
    return Response({}, 204)


@api_view(['get'])
def get_ingredients(request):
    name = request.GET.get('name', '')
    ingredients = Ingredient.objects.filter(name__istartswith=name)
    data = IngredientSerializer(ingredients, many=True).data
    return Response(data, 200)


@api_view(['get'])
def get_ingredient(request, pk):
    ingredient = Ingredient.objects.filter(pk=pk)
    if ingredient.exists():
        data = IngredientSerializer(ingredient[0]).data
        return Response(data, 200)
    return Response({"detail": 'Ингредиент не найден'}, 404)
