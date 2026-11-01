"""An object store in a dictionary: what the tests use in place of R2 (the protocol in api/src/anisotropy_api/storage.py)."""

from pathlib import Path


class MemoryStore:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str, str | None]] = {}  # key -> (bytes, content type, disposition)
        self.linked: list[str] = []

    def put(self, key: str, path: Path, content_type: str, disposition: str | None = None) -> None:
        self.objects[key] = (path.read_bytes(), content_type, disposition)

    def get(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.objects[key][0])

    def keys(self, prefix: str) -> list[str]:
        return sorted(key for key in self.objects if key.startswith(prefix))

    def link(self, key: str, seconds: int = 600) -> str:
        self.linked.append(key)
        return f"https://store.test/{key}?expires={seconds}"


class FailingStore(MemoryStore):
    """A store whose uploads fail, as a bucket that is gone or a key that no longer opens it would."""

    def put(self, key: str, path: Path, content_type: str, disposition: str | None = None) -> None:
        raise OSError("the bucket refused the upload: AccessDenied")
