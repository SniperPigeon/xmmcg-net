"""Forward stored assets to Net without opening a local filesystem path."""

from contextlib import ExitStack
import logging
import mimetypes
from pathlib import PurePosixPath

import requests
from django.conf import settings
from django.utils import timezone
from .models import Chart

logger = logging.getLogger(__name__)


class UploadRejected(Exception):
    pass


def upload_chart(chart):
    if not settings.MAJDATA_USERNAME or not settings.MAJDATA_PASSWD_HASHED:
        raise UploadRejected("未配置 Net 登录凭证")
    with requests.Session() as session:
        login = session.post(
            settings.MAJDATA_LOGIN_URL,
            data={
                "username": settings.MAJDATA_USERNAME,
                "password": settings.MAJDATA_PASSWD_HASHED,
            },
            timeout=15,
        )
        if login.status_code != 200:
            raise UploadRejected(f"Net 登录失败（HTTP {login.status_code}）")
        try:
            result = login.json()
        except ValueError:
            raise UploadRejected("Net 登录响应无法识别")
        if not isinstance(result, dict) or (
            result.get("message", result.get("Message")) != "ok"
            and result.get("code", result.get("Code")) != 114514
        ):
            raise UploadRejected("Net 登录未成功")
        with ExitStack() as stack:
            files = []
            for field, stem in (
                (chart.chart_file, "maidata"),
                (chart.cover_image, "bg"),
                (chart.audio_file, "track"),
                (chart.background_video, "bg"),
            ):
                if not field:
                    continue
                suffix = PurePosixPath(field.name).suffix.lower()
                if (
                    stem == "bg"
                    and suffix == ".mp4"
                    and PurePosixPath(field.name).name.lower().startswith("pv")
                ):
                    stem = "pv"
                # Net's multipart protocol identifies assets by these exact names.
                if stem == "track":
                    name = "track.mp3"
                elif stem == "maidata":
                    name = "maidata.txt"
                elif field == chart.cover_image:
                    name = "bg.jpg" if suffix in (".jpg", ".jpeg") else "bg.png"
                else:
                    name = stem + suffix
                stream = stack.enter_context(field.open("rb"))
                files.append(
                    (
                        "formfiles",
                        (
                            name,
                            stream,
                            mimetypes.guess_type(field.name)[0]
                            or "application/octet-stream",
                        ),
                    )
                )
            response = session.post(
                settings.MAJDATA_UPLOAD_URL, files=files, timeout=(15, 120)
            )
            # A timeout, gateway error or unrecognized response might follow a successful write.
            if response.status_code >= 500:
                raise requests.RequestException("Net 暂不可用，需核对是否已收到文件")
            if response.status_code >= 400:
                raise UploadRejected(f"Net 拒绝上传（HTTP {response.status_code}）")
            try:
                result = response.json()
            except ValueError:
                result = response.text.strip()
            # The current Net uploader returns Ok("上传成功！"), not a JSON object.
            if result == "上传成功！":
                return {"success": True, "message": result}
            if not isinstance(result, dict):
                raise ValueError("无法识别 Net 返回结果")
            code = result.get("code", result.get("Code"))
            if result.get("success") is False or (
                code is not None and code not in (0, 200, 114514)
            ):
                raise UploadRejected("Net 返回上传失败")
            if not (
                result.get("success") is True
                or code in (0, 200, 114514)
                or result.get("url")
                or result.get("chart_url")
            ):
                raise ValueError("Net 返回结果未确认上传成功")
            return result


def sync_chart(chart):
    if not settings.ENABLE_CHART_FORWARD_TO_MAJDATA:
        Chart.objects.filter(pk=chart.pk, net_sync_status="pending").update(
            net_sync_status="disabled"
        )
        chart.refresh_from_db()
        return chart
    # Compare-and-set prevents concurrent retries and never automatically resends uncertain requests.
    claimed = Chart.objects.filter(
        pk=chart.pk, net_sync_status__in=["pending", "failed", "disabled"]
    ).update(net_sync_status="syncing", net_sync_error="")
    if claimed:
        try:
            result = upload_chart(chart)
            url = result.get("url") or result.get("chart_url") or ""
            Chart.objects.filter(pk=chart.pk).update(
                net_sync_status="synced",
                net_response=result,
                net_url=url
                if isinstance(url, str) and url.startswith("https://")
                else "",
                net_synced_at=timezone.now(),
            )
        except UploadRejected as error:
            Chart.objects.filter(pk=chart.pk).update(
                net_sync_status="failed", net_sync_error=str(error)
            )
        except Exception:
            logger.exception("Net 同步结果不确定：chart=%s", chart.pk)
            Chart.objects.filter(pk=chart.pk).update(
                net_sync_status="unknown",
                net_sync_error="请核对 Net 是否已收到文件，再由管理员决定是否重试",
            )
    chart.refresh_from_db()
    return chart
