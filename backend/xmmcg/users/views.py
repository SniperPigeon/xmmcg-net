from django.contrib.auth import (
    authenticate,
    login as auth_login,
    logout as auth_logout,
    get_user_model,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from .models import UserProfile, identity_id
from .serializers import UserDetailSerializer, UserRegistrationSerializer

User = get_user_model()


class EndpointThrottle(SimpleRateThrottle):
    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class AccountSearchThrottle(EndpointThrottle):
    scope = "account_search"


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf_token_view(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def register(request):
    serializer = UserRegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        user = serializer.save()
    except IntegrityError:
        raise ValidationError("用户名或联系方式已被使用")
    return Response(
        {"success": True, "user": UserDetailSerializer(user).data}, status=201
    )


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([AccountSearchThrottle])
def search_accounts(request):
    query = request.query_params.get("q", "").strip()
    users = (
        User.objects.filter(
            is_active=True,
            profile__main_account__isnull=True,
            username__icontains=query,
        ).order_by("username")[:20]
        if len(query) >= 2
        else []
    )
    return Response([{"id": user.pk, "username": user.username} for user in users])


@api_view(["POST"])
@permission_classes([AllowAny])
@csrf_protect
def login(request):
    user = authenticate(
        request,
        username=request.data.get("username"),
        password=request.data.get("password"),
    )
    if user is None:
        raise ValidationError("用户名或密码错误")
    auth_login(request, user)
    return Response({"success": True, "user": UserDetailSerializer(user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    auth_logout(request)
    return Response({"success": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    return Response(UserDetailSerializer(request.user).data)


@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def update_profile(request):
    if set(request.data) - {"preferred_name", "email"}:
        raise ValidationError("只允许修改谱师名义和邮箱")
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if "preferred_name" in request.data:
        name = request.data["preferred_name"]
        if not isinstance(name, str) or len(name) > 50:
            raise ValidationError("谱师名义最多 50 个字符")
        profile.preferred_name = name.strip()
        profile.save(update_fields=["preferred_name"])
    if "email" in request.data:
        from rest_framework.fields import EmailField

        if identity_id(request.user) != request.user.pk:
            raise ValidationError("小号使用大号邮箱，请在大号中修改")
        email = EmailField().run_validation(request.data["email"]).lower()
        if (
            User.objects.exclude(pk=request.user.pk)
            .filter(email__iexact=email)
            .exists()
        ):
            raise ValidationError("邮箱已使用")
        request.user.email = email
        request.user.save(update_fields=["email"])
    # 清除用户对象可能缓存的旧资料，返回刚保存的中文名义。
    request.user.refresh_from_db()
    return Response(
        {
            "success": True,
            "message": "个人信息已更新",
            "user": UserDetailSerializer(request.user).data,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password(request):
    if not request.user.check_password(request.data.get("old_password", "")):
        raise ValidationError("旧密码错误")
    password = request.data.get("new_password", "")
    if password != request.data.get("new_password_confirm"):
        raise ValidationError("两次密码不一致")
    try:
        validate_password(password, request.user)
    except DjangoValidationError as error:
        raise ValidationError(error.messages)
    request.user.set_password(password)
    request.user.save(update_fields=["password"])
    return Response({"success": True})
