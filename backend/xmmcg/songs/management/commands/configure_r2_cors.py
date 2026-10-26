import json

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from xmmcg.storage import cors_policy


class Command(BaseCommand):
    help = "预览 R2 CORS 配置；添加 --apply 后写入配置的桶（替换该桶现有 CORS）"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        policy = cors_policy(settings.R2_CORS_ORIGINS)
        self.stdout.write(json.dumps(policy, indent=2))
        if options["apply"]:
            default_storage.connection.meta.client.put_bucket_cors(
                Bucket=default_storage.bucket_name, CORSConfiguration=policy
            )
            self.stdout.write(self.style.SUCCESS("R2 CORS 已更新"))
