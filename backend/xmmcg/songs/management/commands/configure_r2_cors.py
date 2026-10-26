import json

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from xmmcg.storage import cors_policy


def merge_cors_rules(existing, desired):
    """保留桶上已有规则，只补充网站所需的读取规则。"""
    result = list(existing)
    for rule in desired:
        if rule not in result:
            result.append(rule)
    return result


class Command(BaseCommand):
    help = "预览 R2 CORS 配置；添加 --apply 后合并写入，保留桶上已有规则"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        policy = cors_policy(settings.R2_CORS_ORIGINS)
        self.stdout.write(json.dumps(policy, indent=2))
        if options["apply"]:
            client = default_storage.connection.meta.client
            try:
                existing = client.get_bucket_cors(
                    Bucket=default_storage.bucket_name
                ).get("CORSRules", [])
            except ClientError as error:
                if error.response["Error"]["Code"] != "NoSuchCORSConfiguration":
                    raise
                existing = []
            merged = merge_cors_rules(existing, policy["CORSRules"])
            if merged != existing:
                client.put_bucket_cors(
                    Bucket=default_storage.bucket_name,
                    CORSConfiguration={"CORSRules": merged},
                )
            self.stdout.write(self.style.SUCCESS("R2 CORS 已配置，原有规则保持不变"))
