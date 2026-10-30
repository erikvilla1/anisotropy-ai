"""Durable outputs (ADR-0050 amendment 2): a done job's files by key, its package zip and the coupon's folder in an object store,
and the folder back from the store into a new container. A dictionary stands in for R2; the live round trip against a real
S3-compatible store (a local MinIO, or R2) runs only when TEST_S3_ENDPOINT, TEST_S3_BUCKET, TEST_S3_ACCESS_KEY_ID and
TEST_S3_SECRET_ACCESS_KEY are set."""

import os
import urllib.request
import uuid
from pathlib import Path, PurePosixPath

import pytest

from anisotropy_api import storage
from anisotropy_api.settings import StorageSettings
from memory_store import MemoryStore

LIVE = {name: os.environ.get(f"TEST_S3_{name}", "").strip() for name in ("ENDPOINT", "BUCKET", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")}
needs_live_store = pytest.mark.skipif(not all(LIVE.values()), reason="TEST_S3_ENDPOINT, TEST_S3_BUCKET, TEST_S3_ACCESS_KEY_ID and TEST_S3_SECRET_ACCESS_KEY not all set")


def test_content_types_and_what_a_browser_saves():
    assert storage.content_type(Path("a/fields.json")) == "application/json"
    assert storage.content_type(Path("a/report.PDF")) == "application/pdf"
    assert storage.content_type(Path("a/deck.inp")).startswith("text/plain")
    assert storage.content_type(Path("a/unknown.bin")) == "application/octet-stream"
    assert storage.disposition(Path("a/report.pdf")) == 'attachment; filename="report.pdf"'
    assert storage.disposition(Path("a/fields.json")) is None  # the viewer fetches it


def test_the_layout_under_one_prefix_per_coupon():
    assert storage.file_key("IM7-UNT-L1", "attempt-02_2026-10-30", "fields", "IM7-UNT-L1-fields.json") == \
        "coupons/IM7-UNT-L1/attempt-02_2026-10-30/files/fields/IM7-UNT-L1-fields.json"
    assert storage.package_key("IM7-UNT-L1", "attempt-02_2026-10-30") == "coupons/IM7-UNT-L1/attempt-02_2026-10-30/package.zip"
    assert storage.folder_key("IM7-UNT-L1", PurePosixPath("ours/IM7-UNT-L1.toml")) == "coupons/IM7-UNT-L1/folder/ours/IM7-UNT-L1.toml"


def test_a_jobs_files_go_by_key_and_the_zip_stands_for_the_package_folder(tmp_path):
    fields = tmp_path / "IM7-UNT-L1-fields.json"
    fields.write_text('{"a": 1}', encoding="utf-8")
    pdf = tmp_path / "IM7-UNT-L1.pdf"
    pdf.write_bytes(b"%PDF")
    package = tmp_path / "2026-10-30_IM7-UNT-L1"
    package.mkdir()
    archive = tmp_path / "2026-10-30_IM7-UNT-L1.zip"
    archive.write_bytes(b"PK\x03\x04")
    store = MemoryStore()
    stored = storage.store_job(store, "IM7-UNT-L1", "attempt-02", {"fields": fields, "document": pdf, "package": package, "gone": tmp_path / "gone.txt"}, archive)
    assert stored == {"document": "coupons/IM7-UNT-L1/attempt-02/files/document/IM7-UNT-L1.pdf",
                      "fields": "coupons/IM7-UNT-L1/attempt-02/files/fields/IM7-UNT-L1-fields.json",
                      "package": "coupons/IM7-UNT-L1/attempt-02/package.zip"}
    assert store.objects[stored["fields"]] == (b'{"a": 1}', "application/json", None)
    assert store.objects[stored["document"]][1:] == ("application/pdf", 'attachment; filename="IM7-UNT-L1.pdf"')
    assert store.objects[stored["package"]] == (b"PK\x03\x04", "application/zip", 'attachment; filename="2026-10-30_IM7-UNT-L1.zip"')


def test_the_coupon_folder_round_trips_and_a_restore_fills_only_what_the_disk_lacks(tmp_path):
    folder = tmp_path / "fea" / "IM7-UNT-L1"
    (folder / "ours" / "runs" / "attempt-01").mkdir(parents=True)
    (folder / "README.md").write_text("# IM7-UNT-L1\n", encoding="utf-8")
    (folder / "ours" / "IM7-UNT-L1.toml").write_text("[coupon]\n", encoding="utf-8")
    (folder / "ours" / "runs" / "attempt-01" / "summary.txt").write_text("ok\n", encoding="utf-8")
    store = MemoryStore()
    assert storage.store_folder(store, folder, "IM7-UNT-L1") == 3
    assert store.keys("coupons/IM7-UNT-L1/folder/") == ["coupons/IM7-UNT-L1/folder/README.md", "coupons/IM7-UNT-L1/folder/ours/IM7-UNT-L1.toml",
                                                          "coupons/IM7-UNT-L1/folder/ours/runs/attempt-01/summary.txt"]
    # a second coupon, and a few keys that are not a coupon's folder or would leave it
    other = tmp_path / "other.toml"
    other.write_text("x", encoding="utf-8")
    store.put("coupons/OTHER-1/folder/ours/OTHER-1.toml", other, "text/plain")
    store.put("coupons/IM7-UNT-L1/attempt-02/files/fields/f.json", other, "application/json")
    store.put("coupons/IM7-UNT-L1/folder/../escape.txt", other, "text/plain")
    store.put("coupons/a/b/folder/deep.txt", other, "text/plain")
    store.put("coupons//folder/x.txt", other, "text/plain")
    fresh = tmp_path / "fresh"
    (fresh / "IM7-UNT-L1").mkdir(parents=True)
    (fresh / "IM7-UNT-L1" / "README.md").write_text("kept as it is\n", encoding="utf-8")  # already on the disk: not overwritten
    files, coupons = storage.restore(store, fresh)
    assert (files, coupons) == (3, 2)
    assert (fresh / "IM7-UNT-L1" / "README.md").read_text(encoding="utf-8") == "kept as it is\n"
    assert (fresh / "IM7-UNT-L1" / "ours" / "runs" / "attempt-01" / "summary.txt").read_text(encoding="utf-8") == "ok\n"
    assert (fresh / "OTHER-1" / "ours" / "OTHER-1.toml").is_file()
    assert not (fresh / "escape.txt").exists() and not (tmp_path / "escape.txt").exists() and not (fresh / "a").exists()
    assert storage.restore(store, fresh) == (0, 2)  # everything there now


def test_the_r2_client_is_built_from_the_settings_without_the_network():
    client = storage.R2Store(StorageSettings("coupons", "https://account.r2.cloudflarestorage.com", "id", "secret"))
    assert client.bucket == "coupons" and client.client.meta.endpoint_url == "https://account.r2.cloudflarestorage.com"
    assert client.client.meta.config.s3["addressing_style"] == "path" and client.client.meta.config.signature_version == "s3v4"
    assert client.client.meta.config.request_checksum_calculation == "when_required"
    with pytest.raises(ValueError, match="off"):
        storage.R2Store(StorageSettings(None, None, None, None))


@needs_live_store
def test_the_live_store_round_trips_and_its_link_serves_the_file(tmp_path):
    client = storage.R2Store(StorageSettings(LIVE["BUCKET"], LIVE["ENDPOINT"], LIVE["ACCESS_KEY_ID"], LIVE["SECRET_ACCESS_KEY"]))
    key = f"coupons/TEST-{uuid.uuid4().hex[:8]}/attempt-01/files/fields/fields.json"
    source = tmp_path / "fields.json"
    source.write_text('{"reaction": 1.0}', encoding="utf-8")
    client.put(key, source, "application/json")
    assert key in client.keys(key.rsplit("/", 3)[0])
    back = tmp_path / "back" / "fields.json"
    client.get(key, back)
    assert back.read_bytes() == source.read_bytes()
    with urllib.request.urlopen(client.link(key, seconds=60), timeout=30) as response:
        assert response.status == 200 and response.headers.get("Content-Type", "").startswith("application/json")
        assert response.read() == source.read_bytes()
