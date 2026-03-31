from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from functools import lru_cache
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from backend.app.core.config import get_settings

CHUNK_SIZE = 1024 * 1024


class BaseStorageProvider(ABC):
    @abstractmethod
    async def save(self, file: UploadFile, subpath: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_stream(self, path: str) -> AsyncGenerator[bytes, None]:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, path: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def exists(self, path: str) -> bool:
        raise NotImplementedError


class LocalStorageProvider(BaseStorageProvider):
    def __init__(self, root_path: str | Path) -> None:
        self.root_path = Path(root_path).expanduser().resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _resolve_relative_path(self, relative_path: str) -> Path:
        normalized = PurePosixPath(relative_path)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError("Invalid storage path")

        resolved = (self.root_path / Path(*normalized.parts)).resolve()
        if resolved != self.root_path and self.root_path not in resolved.parents:
            raise ValueError("Storage path escapes root")
        return resolved

    async def save(self, file: UploadFile, subpath: str) -> str:
        original_name = file.filename or "file"
        extension = Path(original_name).suffix.lower()
        filename = f"{uuid.uuid4().hex}{extension}"
        relative_path = str(PurePosixPath(subpath) / filename)
        target_path = self._resolve_relative_path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        await file.seek(0)
        with target_path.open("wb") as output:
            while chunk := await file.read(CHUNK_SIZE):
                output.write(chunk)
        await file.seek(0)
        return relative_path

    async def get_stream(self, path: str) -> AsyncGenerator[bytes, None]:
        source_path = self._resolve_relative_path(path)

        with source_path.open("rb") as handle:
            while True:
                chunk = await asyncio.to_thread(handle.read, CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    async def delete(self, path: str) -> bool:
        target_path = self._resolve_relative_path(path)
        try:
            await asyncio.to_thread(target_path.unlink)
        except FileNotFoundError:
            return False
        return True

    async def exists(self, path: str) -> bool:
        target_path = self._resolve_relative_path(path)
        return await asyncio.to_thread(target_path.is_file)


@lru_cache
def get_storage_provider() -> BaseStorageProvider:
    settings = get_settings()
    backend = settings.storage_backend.strip().lower()
    if backend != "local":
        raise ValueError(f"Unsupported storage backend: {settings.storage_backend}")
    return LocalStorageProvider(settings.storage_path)
