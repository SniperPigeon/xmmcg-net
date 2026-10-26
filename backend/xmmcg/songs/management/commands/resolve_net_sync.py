from django.core.management.base import BaseCommand, CommandError
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from songs.models import Chart


class Command(BaseCommand):
    help = "人工核对 Net 后，标记不确定的同步已完成或允许重试。不会自动上传。"

    def add_arguments(self, parser):
        parser.add_argument("chart_id", type=int)
        actions = parser.add_mutually_exclusive_group(required=True)
        actions.add_argument("--synced", action="store_true")
        actions.add_argument("--allow-retry", action="store_true")
        parser.add_argument("--url", default="")

    def handle(self, *args, **options):
        records = Chart.objects.filter(
            pk=options["chart_id"], net_sync_status__in=["unknown", "syncing"]
        )
        if options["synced"]:
            url = options["url"]
            if url:
                try:
                    URLValidator(schemes=["https"])(url)
                except ValidationError:
                    raise CommandError("请填写有效的 HTTPS Net 地址")
            changed = records.update(
                net_sync_status="synced",
                net_url=url,
                net_sync_error="",
                net_synced_at=timezone.now(),
            )
        else:
            changed = records.update(
                net_sync_status="failed", net_sync_error="管理员已核对远端，允许重试"
            )
        if not changed:
            raise CommandError("谱面不存在，或当前不是需人工核对的同步状态")
        self.stdout.write(self.style.SUCCESS("同步状态已更新；未向 Net 发送文件"))
