import logging
from django.db.models import FileField

logger = logging.getLogger(__name__)


def discard_new_assets(instance):
    """Compensate a failed creation; use only for records with newly uploaded files."""
    for field in instance._meta.fields:
        if not isinstance(field, FileField):
            continue
        asset = getattr(instance, field.name)
        if asset and asset._committed:
            try:
                asset.delete(save=False)
            except Exception:
                logger.exception("上传失败后的对象清理失败：%s", asset.name)
