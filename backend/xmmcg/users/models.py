from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    qqid = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        help_text="小号留空，使用大号联系方式",
    )
    preferred_name = models.CharField(max_length=50, blank=True, default="")
    main_account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="alternate_profiles",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    """One person has one review identity; login and staff permissions remain separate."""
    try:
        return user.profile.main_account_id or user.pk
    except UserProfile.DoesNotExist:
        return user.pk
