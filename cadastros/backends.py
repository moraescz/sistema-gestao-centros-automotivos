from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q

class EmailOrUsernameBackend(ModelBackend):
    """
    Este é um backend de autenticação customizado.
    Ele permite que os usuários façam login usando seu nome de usuário OU seu endereço de e-mail.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Tenta encontrar um usuário que corresponda ao nome de usuário OU ao e-mail
        # A busca por e-mail é case-insensitive (não diferencia maiúsculas de minúsculas)
        # Filtra apenas usuários ativos e usa first() para evitar MultipleObjectsReturned
        user = User.objects.filter(
            Q(username__iexact=username) | Q(email__iexact=username),
            is_active=True
        ).first()

        if user and user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None