from __future__ import annotations

from io import BytesIO

from starlette.datastructures import UploadFile

from backend.app.core.storage import LocalStorageProvider


async def test_local_storage_provider_roundtrip(tmp_path) -> None:
    provider = LocalStorageProvider(tmp_path)
    payload = b"hello documents"
    upload = UploadFile(filename="report.txt", file=BytesIO(payload))

    relative_path = await provider.save(upload, "documents/test")

    assert (tmp_path / relative_path).exists()

    chunks = [chunk async for chunk in provider.get_stream(relative_path)]
    assert b"".join(chunks) == payload

    assert await provider.delete(relative_path) is True
    assert await provider.delete(relative_path) is False
