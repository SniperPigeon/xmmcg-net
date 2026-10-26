import logging
from django.db.models import FileField

logger = logging.getLogger(__name__)


def store_new_assets(instance):
    """先保存对象文件，避免在网络请求期间占用 SQLite 写锁。"""
    for field in instance._meta.fields:
        if isinstance(field, FileField):
            asset = getattr(instance, field.name)
            if asset and not asset._committed:
                asset.save(asset.name, asset.file, save=False)


def discard_new_assets(instance):
    """创建失败时清理刚上传的对象；仅用于包含新文件的记录。"""
    for field in instance._meta.fields:
        if not isinstance(field, FileField):
            continue
        asset = getattr(instance, field.name)
        if asset and asset._committed:
            try:
                asset.delete(save=False)
            except Exception:
                logger.exception("上传失败后的对象清理失败：%s", asset.name)
