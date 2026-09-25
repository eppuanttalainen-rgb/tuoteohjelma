import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.config import get_settings


class EvidenceTooLargeError(ValueError):
    pass


class InvalidStorageKeyError(ValueError):
    pass


@dataclass(frozen=True)
class StoredObject:
    key: str
    sha256: str
    size_bytes: int


class LocalObjectStorage:
    def __init__(self, root: Path, max_upload_bytes: int) -> None:
        self.root = root
        self.max_upload_bytes = max_upload_bytes

    def _path_for_key(self, key: str) -> Path:
        root = self.root.resolve()
        target = (self.root / key).resolve()
        if not target.is_relative_to(root):
            raise InvalidStorageKeyError("Storage key escapes configured root")
        return target

    async def save(
        self,
        file: UploadFile,
        organization_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> StoredObject:
        relative_path = (
            Path(str(organization_id))
            / str(project_id)
            / f"{uuid.uuid4()}.pdf"
        )
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)

        digest = hashlib.sha256()
        size_bytes = 0

        try:
            with target.open("wb") as output:
                while chunk := await file.read(1024 * 1024):
                    size_bytes += len(chunk)
                    if size_bytes > self.max_upload_bytes:
                        raise EvidenceTooLargeError(
                            f"File exceeds {self.max_upload_bytes} byte upload limit"
                        )
                    digest.update(chunk)
                    output.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        return StoredObject(
            key=relative_path.as_posix(),
            sha256=digest.hexdigest(),
            size_bytes=size_bytes,
        )

    def read_bytes(self, key: str) -> bytes:
        return self._path_for_key(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path_for_key(key).unlink(missing_ok=True)


def get_storage() -> LocalObjectStorage:
    settings = get_settings()
    return LocalObjectStorage(
        root=settings.storage_root,
        max_upload_bytes=settings.max_upload_mb * 1024 * 1024,
    )
