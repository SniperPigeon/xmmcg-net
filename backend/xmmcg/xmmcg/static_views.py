from pathlib import PurePosixPath
import mimetypes

from django.core.files.storage import storages
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe


@require_safe
def static_asset(request, name):
    if ".." in PurePosixPath(name).parts or name.startswith("/") or "\\" in name:
        raise Http404
    storage = storages["staticfiles"]
    # This alias is scoped to static/, never media/ or user uploads.
    if not storage.exists(name):
        raise Http404
    response = FileResponse(
        storage.open(name, "rb"),
        content_type=mimetypes.guess_type(name)[0] or "application/octet-stream",
    )
    response["Cache-Control"] = "public, max-age=3600"
    response["X-Content-Type-Options"] = "nosniff"
    return response
