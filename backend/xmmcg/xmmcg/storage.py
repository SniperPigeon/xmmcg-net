"""R2-backed Django storage. No local path is required by application code."""

from urllib.parse import quote, urlparse

from botocore.config import Config
from django.core.exceptions import ImproperlyConfigured
from django.conf import settings
from storages.backends.s3 import S3Storage


def r2_storage_options(config, prefix):
    account = config("R2_ACCOUNT_ID", default="")
    domain = config("R2_PUBLIC_DOMAIN", default="").strip().rstrip("/")
    if domain:
        domain = urlparse(domain if "://" in domain else "https://" + domain).netloc
    return {
        "access_key": config("R2_ACCESS_KEY_ID", default=""),
        "secret_key": config("R2_SECRET_ACCESS_KEY", default=""),
        "bucket_name": config("R2_BUCKET_NAME", default=""),
        "endpoint_url": config("R2_ENDPOINT_URL", default="")
        or f"https://{account}.r2.cloudflarestorage.com",
        "region_name": "auto",
        "location": prefix,
        "default_acl": None,
        "custom_domain": domain or None,
        "querystring_auth": not bool(domain),
        "querystring_expire": config("R2_URL_EXPIRY", default=3600, cast=int),
        "file_overwrite": False,
        "max_memory_size": 8 * 1024 * 1024,
        "client_config": Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    }


class R2Storage(S3Storage):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.access_key or not self.secret_key or not self.bucket_name:
            raise ImproperlyConfigured(
                "请配置 R2_ACCESS_KEY_ID、R2_SECRET_ACCESS_KEY 和 R2_BUCKET_NAME"
            )
        if (
            not self.endpoint_url
            or self.endpoint_url == "https://.r2.cloudflarestorage.com"
        ):
            raise ImproperlyConfigured("请配置 R2_ACCOUNT_ID 或 R2_ENDPOINT_URL")


class R2StaticStorage(R2Storage):
    def url(self, name, **kwargs):
        # CSS relative URLs and JavaScript module imports cannot inherit a signed query.
        # A small read-through endpoint serves private-bucket admin assets at stable URLs.
        if self.custom_domain:
            return super().url(name, **kwargs)
        return settings.STATIC_URL.rstrip("/") + "/" + quote(name)


def cors_policy(origins):
    if not origins or any(
        urlparse(origin).scheme not in ("http", "https")
        or not urlparse(origin).netloc
        or urlparse(origin).path not in ("", "/")
        for origin in origins
    ):
        raise ImproperlyConfigured(
            "R2_CORS_ORIGINS 必须为完整的网站源，例如 https://contest.example.com"
        )
    # Uploads go through the authenticated backend; browsers only read objects.
    return {
        "CORSRules": [
            {
                "AllowedOrigins": [origin.rstrip("/") for origin in origins],
                "AllowedMethods": ["GET", "HEAD"],
                "AllowedHeaders": ["Range", "Content-Type"],
                "ExposeHeaders": [
                    "ETag",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                ],
                "MaxAgeSeconds": 3600,
            }
        ]
    }
