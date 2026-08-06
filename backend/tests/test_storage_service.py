from pathlib import Path

import pytest

from app.services.storage_service import StorageService


@pytest.fixture
def storage(tmp_path: Path) -> StorageService:
    return StorageService(base_path=tmp_path / "attachments")


def test_creates_storage_directory_if_missing(tmp_path: Path) -> None:
    target = tmp_path / "does-not-exist-yet"
    assert not target.exists()
    StorageService(base_path=target)
    assert target.is_dir()


def test_generate_stored_filename_preserves_extension(storage: StorageService) -> None:
    name = storage.generate_stored_filename("report.PDF")
    assert name.endswith(".pdf")
    assert name != "report.PDF"


def test_generate_stored_filename_is_unique(storage: StorageService) -> None:
    first = storage.generate_stored_filename("photo.png")
    second = storage.generate_stored_filename("photo.png")
    assert first != second


def test_save_and_load_roundtrip(storage: StorageService) -> None:
    name = storage.generate_stored_filename("notes.txt")
    storage.save(name, b"hello world")
    assert storage.load(name) == b"hello world"


def test_delete_removes_file(storage: StorageService, tmp_path: Path) -> None:
    name = storage.generate_stored_filename("notes.txt")
    storage.save(name, b"content")
    storage.delete(name)
    with pytest.raises(FileNotFoundError):
        storage.load(name)


def test_delete_missing_file_does_not_raise(storage: StorageService) -> None:
    storage.delete("never-existed.txt")  # should be a silent no-op


def test_rejects_path_traversal_on_save(storage: StorageService) -> None:
    with pytest.raises(ValueError):
        storage.save("../../evil.txt", b"malicious")


def test_rejects_path_traversal_on_load(storage: StorageService) -> None:
    with pytest.raises(ValueError):
        storage.load("../../etc/passwd")


def test_rejects_path_traversal_on_delete(storage: StorageService) -> None:
    with pytest.raises(ValueError):
        storage.delete("../outside.txt")


def test_path_traversal_attempt_does_not_escape_storage_root(
    storage: StorageService, tmp_path: Path
) -> None:
    outside_file = tmp_path / "outside.txt"
    try:
        storage.save("../outside.txt", b"malicious")
    except ValueError:
        pass
    assert not outside_file.exists()
