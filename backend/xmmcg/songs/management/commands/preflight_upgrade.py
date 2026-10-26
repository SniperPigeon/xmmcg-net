"""Fail before migrating if the live schema does not match its recorded migration state."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.loader import MigrationLoader


class Command(BaseCommand):
    help = "只读检查迁移记录与实际表/字段是否一致；不自动修补历史数据库"

    def handle(self, *args, **options):
        loader = MigrationLoader(connection)
        applied = set(loader.applied_migrations)
        known = set(loader.disk_migrations)
        unknown = sorted(
            node for node in applied - known if node[0] in ("songs", "users")
        )
        if unknown:
            raise CommandError(
                f"发现当前代码不认识的迁移记录：{unknown}。请先核对线上版本。"
            )
        targets = sorted(applied & known)
        if not targets:
            self.stdout.write("空数据库，可以执行首次迁移。")
            return
        state = loader.project_state(targets)
        missing = []
        with connection.cursor() as cursor:
            tables = set(connection.introspection.table_names(cursor))
            for model in state.apps.get_models(include_auto_created=True):
                if model._meta.app_label not in ("songs", "users"):
                    continue
                table = model._meta.db_table
                if table not in tables:
                    missing.append(table)
                    continue
                columns = {
                    column.name
                    for column in connection.introspection.get_table_description(
                        cursor, table
                    )
                }
                missing.extend(
                    f"{table}.{field.column}"
                    for field in model._meta.local_fields
                    if field.column not in columns
                )
        if missing:
            raise CommandError(
                "迁移记录与实际结构不一致，尚未修改数据。请使用与线上版本匹配的数据库备份。缺少："
                + ", ".join(missing)
            )
        self.stdout.write(self.style.SUCCESS("表和字段与已执行的迁移记录一致。"))
