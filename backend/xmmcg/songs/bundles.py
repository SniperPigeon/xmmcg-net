"""从对象存储打包谱面；仅使用可自动清理的临时缓冲，不依赖资产本地路径。"""

from pathlib import PurePosixPath
from shutil import copyfileobj
from tempfile import SpooledTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from botocore.exceptions import BotoCoreError, ClientError
from django.http import FileResponse
from rest_framework.exceptions import APIException


class BundleError(APIException):
    status_code = 503
    default_detail = "谱面资源暂时无法读取，请稍后重试"


def write_chart(archive, chart, prefix="", *, original_names=False):
    written = 0
    for name, stem, label in (
        ("chart_file", "maidata", "谱面文件"),
        ("audio_file", "track", "音频"),
        ("cover_image", "bg", "封面"),
        ("background_video", "bg", "背景视频"),
    ):
        field = getattr(chart, name)
        if not field:
            continue
        filename = PurePosixPath(field.name)
        if name == "background_video" and filename.name.lower().startswith("pv"):
            stem = "pv"
        suffix = filename.suffix.lower()
        if name == "cover_image":
            # 与 Net 协议一致，播放器只查找 bg.jpg / bg.png；不重编码原图。
            suffix = ".jpg" if suffix in (".jpg", ".jpeg") else ".png"
        archive_name = filename.name if original_names else stem + suffix
        try:
            with (
                field.open("rb") as source,
                archive.open(prefix + archive_name, "w", force_zip64=True) as target,
            ):
                copyfileobj(source, target, length=1024 * 1024)
        except (OSError, BotoCoreError, ClientError) as error:
            raise BundleError(
                f"谱面 #{chart.pk} 的{label}读取失败，请确认 R2 中的资源存在且可访问"
            ) from error
        written += 1
    if not written:
        raise BundleError(f"谱面 #{chart.pk} 没有可下载的文件")


def chart_bundle_response(charts, *, filename, batch=False):
    output = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    try:
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            manifest = []
            for chart in charts:
                folder = str(chart.guid)
                write_chart(
                    archive,
                    chart,
                    prefix=folder + "/" if batch else "",
                    original_names=batch,
                )
                if batch:
                    manifest.append(f"{folder}：{chart.title} — {chart.designer}")
            if batch:
                archive.writestr("谱面列表.txt", "\n".join(manifest).encode("utf-8"))
        output.seek(0)
        return FileResponse(
            output,
            as_attachment=True,
            filename=filename,
            content_type="application/zip",
        )
    except Exception:
        output.close()
        raise
