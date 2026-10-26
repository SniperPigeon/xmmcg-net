from .settings import *  # noqa: F403

DATABASES = {"default": {**DATABASES["default"], "NAME": ":memory:"}}  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "songs.tests.storage.ObjectStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
ENABLE_CHART_FORWARD_TO_MAJDATA = False
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
REST_FRAMEWORK = {**REST_FRAMEWORK, "DEFAULT_THROTTLE_CLASSES": []}  # noqa: F405

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"]},
    "loggers": {"django": {"handlers": ["null"], "propagate": False}},
}
