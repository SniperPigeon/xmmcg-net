from unittest.mock import patch, MagicMock
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.core.management import call_command
from django.core.exceptions import ImproperlyConfigured
from songs.majdata_service import upload_chart
from xmmcg.storage import cors_policy, R2Storage
from .test_peer_review_allocation import make_user, make_chart


class StorageConfigurationTests(SimpleTestCase):
    def test_private_signed_url_and_no_path(self):
        storage = R2Storage(
            access_key="example",
            secret_key="example-secret",
            bucket_name="test-bucket",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            region_name="auto",
            location="media",
            querystring_auth=True,
            signature_version="s3v4",
        )
        url = storage.url("charts/example.txt")
        self.assertIn("X-Amz-Signature=", url)
        self.assertIn("/media/charts/example.txt", url)
        with self.assertRaises(NotImplementedError):
            storage.path("charts/example.txt")

    def test_missing_credentials_fail_without_local_fallback(self):
        with self.assertRaises(ImproperlyConfigured):
            R2Storage(access_key="", secret_key="", bucket_name="")

    def test_cors_explicit_origins_and_get_head(self):
        rules = cors_policy(["https://contest.example.com"])["CORSRules"][0]
        self.assertEqual(rules["AllowedMethods"], ["GET", "HEAD"])
        self.assertIn("Content-Range", rules["ExposeHeaders"])
        with self.assertRaises(ImproperlyConfigured):
            cors_policy(["*"])

    @override_settings(R2_CORS_ORIGINS=["https://contest.example.com"])
    def test_cors_preview_does_not_contact_bucket(self):
        from io import StringIO

        output = StringIO()
        call_command("configure_r2_cors", stdout=output)
        self.assertIn("https://contest.example.com", output.getvalue())


class NetStreamTests(TestCase):
    @override_settings(MAJDATA_USERNAME="test", MAJDATA_PASSWD_HASHED="test")
    def test_net_receives_exact_original_bytes_from_storage_stream(self):
        chart = make_chart(make_user("u"))
        original = b"\xef\xbb\xbf&title=original\r\n&inote_5=1,2,E\r\n"
        chart.chart_file.save("maidata.txt", ContentFile(original))
        chart.audio_file.save("track.ogg", ContentFile(b"audio"))
        chart.cover_image.save("bg.png", ContentFile(b"cover"))
        login_response = MagicMock(status_code=200)
        login_response.json.return_value = {"code": 114514, "message": "ok"}
        upload_response = MagicMock(status_code=200)
        upload_response.json.return_value = {
            "success": True,
            "url": "https://majdata.net/test",
        }

        def post(url, **kwargs):
            if "files" not in kwargs:
                return login_response
            files = kwargs["files"]
            self.assertEqual(files[0][1][1].read(), original)
            self.assertEqual(files[2][1][0], "track.mp3")
            return upload_response

        with patch("songs.majdata_service.requests.Session") as session:
            session.return_value.__enter__.return_value.post.side_effect = post
            with patch.object(
                chart.chart_file.storage,
                "path",
                side_effect=AssertionError("local path used"),
            ):
                self.assertEqual(upload_chart(chart)["success"], True)


class PrivateStaticTests(TestCase):
    @override_settings(
        STORAGES={
            "default": {"BACKEND": "songs.tests.storage.ObjectStorage"},
            "staticfiles": {"BACKEND": "songs.tests.storage.ObjectStorage"},
        }
    )
    def test_static_proxy_serves_only_static_storage(self):
        from django.core.files.storage import storages
        from rest_framework.test import APIClient

        storages["staticfiles"].save(
            "admin/css/base.css", ContentFile(b"body { color: red; }")
        )
        storages["default"].save("private.txt", ContentFile(b"private"))
        client = APIClient()
        response = client.get("/static/admin/css/base.css")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"body { color: red; }")
        self.assertEqual(client.get("/static/private.txt").status_code, 404)
        self.assertEqual(client.get("/static/../media/private.txt").status_code, 404)

    def test_private_static_url_is_stable_for_relative_css_imports(self):
        from xmmcg.storage import R2StaticStorage

        storage = R2StaticStorage(
            access_key="example",
            secret_key="example-secret",
            bucket_name="test",
            endpoint_url="https://example.r2.cloudflarestorage.com",
            region_name="auto",
            location="static",
        )
        self.assertEqual(
            storage.url("admin/css/base.css"), "/static/admin/css/base.css"
        )


class NetProtocolTests(TestCase):
    @override_settings(MAJDATA_USERNAME="test", MAJDATA_PASSWD_HASHED="test")
    def test_current_net_plain_text_success(self):
        chart = make_chart(make_user("net-protocol"))
        login = MagicMock(status_code=200)
        login.json.return_value = {"code": 114514, "message": "ok"}
        response = MagicMock(status_code=200, text="上传成功！")
        response.json.side_effect = ValueError("plain text")
        with patch("songs.majdata_service.requests.Session") as session:
            session.return_value.__enter__.return_value.post.side_effect = [
                login,
                response,
            ]
            self.assertTrue(upload_chart(chart)["success"])

    @override_settings(MAJDATA_USERNAME="test", MAJDATA_PASSWD_HASHED="test")
    def test_unrecognized_response_is_not_marked_success(self):
        chart = make_chart(make_user("net-uncertain"))
        login = MagicMock(status_code=200)
        login.json.return_value = {"code": 114514, "message": "ok"}
        response = MagicMock(status_code=200)
        response.json.return_value = {"message": "unexpected error"}
        with patch("songs.majdata_service.requests.Session") as session:
            session.return_value.__enter__.return_value.post.side_effect = [
                login,
                response,
            ]
            with self.assertRaises(ValueError):
                upload_chart(chart)
