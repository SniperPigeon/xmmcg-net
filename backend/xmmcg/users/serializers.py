from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from .models import UserProfile, identity_id

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    qqid = serializers.RegexField(
        r"^[1-9][0-9]{4,19}$", required=False, write_only=True
    )
    main_account_id = serializers.IntegerField(required=False, write_only=True)
    main_password = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "qqid",
            "password",
            "password_confirm",
            "main_account_id",
            "main_password",
        )

    def validate(self, data):
        if data["password"] != data.pop("password_confirm"):
            raise serializers.ValidationError("两次密码不一致")
        main_id = data.pop("main_account_id", None)
        main_password = data.pop("main_password", "")
        if main_id:
            main = User.objects.filter(pk=main_id, is_active=True).first()
            if (
                not main
                or authenticate(username=main.username, password=main_password) is None
            ):
                raise serializers.ValidationError("大号身份验证失败")
            if identity_id(main) != main.pk:
                raise serializers.ValidationError("请选择大号，不能绑定另一个小号")
            self.main = main
            data.pop("qqid", None)
            data["email"] = ""  # Contacts are inherited, not duplicated.
        else:
            email = data.get("email", "").strip().lower()
            if not email or not data.get("qqid"):
                raise serializers.ValidationError("独立账号需要填写邮箱和 QQ 号")
            if User.objects.filter(email__iexact=email).exists():
                raise serializers.ValidationError("邮箱已注册；同一人请绑定已有大号")
            if UserProfile.objects.filter(qqid=data["qqid"]).exists():
                raise serializers.ValidationError("QQ 号已注册；同一人请绑定已有大号")
            data["email"] = email
        return data

    @transaction.atomic
    def create(self, validated_data):
        main = getattr(self, "main", None)
        if main:
            main = User.objects.select_for_update().get(pk=main.pk)
            if not main.is_active or identity_id(main) != main.pk:
                raise serializers.ValidationError("大号状态已变化，请重新验证")
        qqid = validated_data.pop("qqid", None)
        user = User.objects.create_user(**validated_data)
        UserProfile.objects.create(user=user, qqid=qqid, main_account=main)
        return user


class UserDetailSerializer(serializers.ModelSerializer):
    email = serializers.SerializerMethodField()
    qqid = serializers.SerializerMethodField()
    preferred_name = serializers.CharField(source="profile.preferred_name", default="")
    main_account = serializers.SerializerMethodField()
    songsCount = serializers.IntegerField(source="songs.count", read_only=True)
    chartsCount = serializers.IntegerField(source="charts.count", read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "qqid",
            "preferred_name",
            "main_account",
            "is_staff",
            "date_joined",
            "songsCount",
            "chartsCount",
        )

    def get_email(self, user):
        return User.objects.get(pk=identity_id(user)).email

    def get_qqid(self, user):
        return (
            UserProfile.objects.filter(user_id=identity_id(user))
            .values_list("qqid", flat=True)
            .first()
        )

    def get_main_account(self, user):
        root_id = identity_id(user)
        if root_id == user.pk:
            return None
        main = User.objects.get(pk=root_id)
        return {"id": main.pk, "username": main.username}
