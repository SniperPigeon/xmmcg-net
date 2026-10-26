from urllib.parse import quote
from django.core.files.base import ContentFile
from django.core.files.storage import Storage


class ObjectStorage(Storage):
    """A test object store whose path() is deliberately unsupported."""

    def __init__(self):
        self.objects = {}

    def _save(self, name, content):
        self.objects[name] = b"".join(content.chunks())
        return name

    def _open(self, name, mode="rb"):
        return ContentFile(self.objects[name], name=name)

    def exists(self, name):
        return name in self.objects

    def delete(self, name):
        self.objects.pop(name, None)

    def size(self, name):
        return len(self.objects[name])

    def url(self, name):
        return "https://objects.example.test/" + quote(name)
