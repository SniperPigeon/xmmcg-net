from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserProfile(models.Model):
    """用户扩展信息模型。"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="用户",
    )
    qqid = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="小号留空，使用大号联系方式",
        verbose_name="QQ号",
    )
    preferred_name = models.CharField(
        max_length=50,
        blank=True,
        default="",
        verbose_name="谱师名义",
        help_text="谱师名义（展示用名称）",
    )
    main_account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="alternate_profiles",
        verbose_name="绑定大号",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = verbose_name_plural = "用户资料"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(main_account=models.F("user")),
                name="no_self_account_link",
            )
        ]

    def clean(self):
        if self.main_account_id:
            if self.main_account_id == self.user_id:
                raise ValidationError("不能绑定自己")
            if UserProfile.objects.filter(
                user_id=self.main_account_id, main_account__isnull=False
            ).exists():
                raise ValidationError("必须绑定大号，不能绑定另一个小号")
            if UserProfile.objects.filter(main_account_id=self.user_id).exists():
                raise ValidationError("已有小号的大号不能改成小号")

    def __str__(self):
        return self.user.username


def identity_id(user):
    """同一人的绑定账号共用评分身份；登录账号和管理员权限仍然独立。"""
    try:
        return user.profile.main_account_id or user.pk
    except UserProfile.DoesNotExist:
        return user.pk
