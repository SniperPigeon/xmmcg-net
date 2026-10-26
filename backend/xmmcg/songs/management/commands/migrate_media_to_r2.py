"""Explicit, repeatable import of pre-refactor media. Never changes or deletes local files."""

import hashlib
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError
from songs.models import Chart, Song


def digest(storage, name):
    value = hashlib.sha256()
    with storage.open(name, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


class Command(BaseCommand):
    help = "将旧媒体目录导入 R2，保持数据库文件名不变；默认仅检查本地文件，--apply 执行并验证"

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True)
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        source = FileSystemStorage(location=options["source"])
        names = set()
        for model in (Chart, Song):
            fields = [
                field.name
                for field in model._meta.fields
                if field.get_internal_type() in ("FileField", "ImageField")
            ]
            for row in model.objects.values_list(*fields):
                names.update(name for name in row if name)
        missing = [name for name in names if not source.exists(name)]
        if missing:
            raise CommandError(
                f"{len(missing)} 个源文件缺失，未执行导入。示例：{missing[:5]}"
            )
        self.stdout.write(f"需要导入 {len(names)} 个文件")
        if not options["apply"]:
            return
        for name in sorted(names):
            if default_storage.exists(name):
                if digest(default_storage, name) != digest(source, name):
                    raise CommandError(f"R2 中已有不同内容，未覆盖：{name}")
                continue
            with source.open(name, "rb") as stream:
                saved_name = default_storage.save(name, stream)
            if saved_name != name:
                default_storage.delete(saved_name)
                raise CommandError(f"目标名称冲突，请检查：{name}")
            if digest(default_storage, name) != digest(source, name):
                raise CommandError(f"上传后校验失败：{name}")
        self.stdout.write(
            self.style.SUCCESS("所有文件已上传并通过 SHA256 校验；本地文件保持不变")
        )
