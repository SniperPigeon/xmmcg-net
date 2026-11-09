from django import forms
from rest_framework.exceptions import ValidationError

from .models import Chart
from .serializers import ChartUploadSerializer


class ChartAdminForm(forms.ModelForm):
    class Meta:
        model = Chart
        fields = (
            "title",
            "designer",
            "status",
            "chart_file",
            "audio_file",
            "cover_image",
            "background_video",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("chart_file", "audio_file", "cover_image"):
            if name in self.fields:
                self.fields[name].required = True

    def clean(self):
        cleaned = super().clean()
        if self.instance.net_sync_status == "syncing":
            raise forms.ValidationError("谱面正在同步到 Net，请稍后再编辑")
        # Validate only replacements, leaving stored assets untouched. The same
        # serializer enforces upload sizes, extensions, UTF-8 and required names.
        validator = ChartUploadSerializer()
        for name in (
            "title",
            "designer",
            "chart_file",
            "audio_file",
            "cover_image",
            "background_video",
        ):
            if name not in cleaned:
                continue
            value = cleaned[name]
            if name not in ("title", "designer") and name not in self.files:
                continue
            try:
                value = validator.fields[name].run_validation(value)
                validate = getattr(validator, f"validate_{name}", None)
                cleaned[name] = validate(value) if validate else value
            except ValidationError as error:
                self.add_error(
                    name, forms.ValidationError([str(item) for item in error.detail])
                )
        return cleaned
