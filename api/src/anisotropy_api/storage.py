"""Durable outputs (ADR-0056, ADR-0050 amendment 2): the files a coupon job makes go to an object store through the S3 API, R2 in
the hosted tier, when the settings name a bucket; a browser gets them from the store by a short-lived link. Nothing here computes.

The layout, under one prefix per coupon:

    coupons/<coupon>/<attempt>/files/<key>/<file name>     every file the tool reported, by its key (fields, decks, the record, ...)
    coupons/<coupon>/<attempt>/package.zip                  the package folder as the zip the API hands out
    coupons/<coupon>/folder/<path under .local/fea/<coupon>/>   the coupon's whole folder, so a new container restores it at
                                                            startup and the coupon list, a coupon's values and the next attempt's
                                                            number are what they were; the latest job's copy wins

Without the settings nothing is stored or restored: the files stay where the tool wrote them, as before.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Protocol

from .settings import StorageSettings

COUPONS = "coupons"
FOLDER = "folder"
LINK_SECONDS = 600  # a download link lives ten minutes: long enough to open, short enough not to be worth passing around
MEDIA_TYPES = {".json": "application/json", ".txt": "text/plain; charset=utf-8", ".inp": "text/plain; charset=utf-8", ".toml": "text/plain; charset=utf-8",
               ".md": "text/markdown; charset=utf-8", ".tex": "text/plain; charset=utf-8", ".csv": "text/csv; charset=utf-8", ".vtu": "application/xml",
               ".pdf": "application/pdf", ".frd": "text/plain; charset=utf-8", ".dat": "text/plain; charset=utf-8", ".zip": "application/zip",
               ".png": "image/png", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
ATTACHMENTS = {".pdf", ".zip", ".xlsx", ".inp", ".frd", ".vtu"}  # what a browser should save rather than show


def content_type(path: Path) -> str:
    return MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")


def disposition(path: Path) -> str | None:
    """`attachment` for the files a browser should save; None lets the browser decide (the viewer fetches the JSON ones)."""
    return f'attachment; filename="{path.name}"' if path.suffix.lower() in ATTACHMENTS else None


class ObjectStore(Protocol):
    """What the jobs need of a store: upload a file, download one, list a prefix, and make a short-lived link."""

    def put(self, key: str, path: Path, content_type: str, disposition: str | None = None) -> None: ...

    def get(self, key: str, path: Path) -> None: ...

    def keys(self, prefix: str) -> list[str]: ...

    def link(self, key: str, seconds: int = LINK_SECONDS) -> str: ...


class R2Store:
    """R2, or any S3-compatible store such as a local MinIO, through boto3: path-style addresses, SigV4, and checksums only where
    the API requires them (R2 lists the newer checksum headers as unsupported). Credentials never leave the settings."""

    def __init__(self, settings: StorageSettings):
        import boto3
        from botocore.config import Config

        if not settings.on:
            raise ValueError("the object store is off: no bucket in the settings")
        self.bucket = settings.bucket
        self.client = boto3.client("s3", endpoint_url=settings.endpoint, aws_access_key_id=settings.access_key_id,
                                   aws_secret_access_key=settings.secret_access_key, region_name="auto",
                                   config=Config(signature_version="s3v4", s3={"addressing_style": "path"}, request_checksum_calculation="when_required",
                                                 response_checksum_validation="when_required", retries={"max_attempts": 3, "mode": "standard"}))

    def put(self, key: str, path: Path, content_type: str, disposition: str | None = None) -> None:
        extra = {"ContentType": content_type}
        if disposition is not None:
            extra["ContentDisposition"] = disposition
        self.client.upload_file(str(path), self.bucket, key, ExtraArgs=extra)

    def get(self, key: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(path))

    def keys(self, prefix: str) -> list[str]:
        pages = self.client.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=prefix)
        return [item["Key"] for page in pages for item in page.get("Contents", [])]

    def link(self, key: str, seconds: int = LINK_SECONDS) -> str:
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=seconds)


# ------------------------------------------------------------------------------------------------------------- the layout

def attempt_prefix(coupon: str, attempt: str) -> str:
    return f"{COUPONS}/{coupon}/{attempt}"


def file_key(coupon: str, attempt: str, key: str, filename: str) -> str:
    return f"{attempt_prefix(coupon, attempt)}/files/{key}/{filename}"


def package_key(coupon: str, attempt: str) -> str:
    return f"{attempt_prefix(coupon, attempt)}/package.zip"


def folder_key(coupon: str, relative: PurePosixPath) -> str:
    return f"{COUPONS}/{coupon}/{FOLDER}/{relative.as_posix()}"


def store_job(store: ObjectStore, coupon: str, attempt: str, outputs: dict[str, Path], package_zip: Path | None) -> dict[str, str]:
    """Upload every file the tool reported, by its key, and the package zip; returns key -> object key, what the status keeps so a
    later process can hand out links. A reported folder (the package itself) is left out: the zip stands for it."""
    stored: dict[str, str] = {}
    for key, path in sorted(outputs.items()):
        if path.is_file():
            object_key = file_key(coupon, attempt, key, path.name)
            store.put(object_key, path, content_type(path), disposition(path))
            stored[key] = object_key
    if package_zip is not None and package_zip.is_file():
        object_key = package_key(coupon, attempt)
        store.put(object_key, package_zip, "application/zip", disposition(package_zip))
        stored["package"] = object_key
    return stored


def store_folder(store: ObjectStore, folder: Path, coupon: str) -> int:
    """Upload the coupon's whole folder (specs, decks, runs, verification, documents, the case page) under its `folder/` prefix;
    returns the number of files."""
    count = 0
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        store.put(folder_key(coupon, PurePosixPath(path.relative_to(folder).as_posix())), path, content_type(path))
        count += 1
    return count


def restore(store: ObjectStore, root: Path) -> tuple[int, int]:
    """Every coupon's folder from the store into root/<coupon>/, downloading only the files the disk lacks; returns the number of
    files downloaded and of coupons seen. A key that would leave its coupon's folder is skipped."""
    marker = f"/{FOLDER}/"
    files, coupons = 0, set()
    for key in store.keys(f"{COUPONS}/"):
        head, found, relative = key.partition(marker)
        coupon = head.removeprefix(f"{COUPONS}/")
        parts = relative.split("/") if found else []
        if not coupon or "/" in coupon or not parts or any(part in ("", ".", "..") for part in parts):
            continue
        coupons.add(coupon)
        target = root.joinpath(coupon, *parts)
        if target.is_file():
            continue
        store.get(key, target)
        files += 1
    return files, len(coupons)
