from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from backend.app.modules.documents.service import validate_document_upload


def test_validate_document_upload_accepts_pdf_signature() -> None:
    result = validate_document_upload(
        filename="contract.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        sample=b"%PDF-1.4\nsample",
    )

    assert result.extension == ".pdf"
    assert result.mime_type == "application/pdf"


def test_validate_document_upload_rejects_spoofed_extension() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_document_upload(
            filename="malware.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            sample=b"MZ\x90\x00fake-executable",
        )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_validate_document_upload_rejects_bad_extension() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_document_upload(
            filename="installer.exe",
            content_type="application/octet-stream",
            size_bytes=1024,
            sample=b"MZ\x90\x00fake-executable",
        )

    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


def test_validate_document_upload_rejects_oversized_payload() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_document_upload(
            filename="large.txt",
            content_type="text/plain",
            size_bytes=52 * 1024 * 1024,
            sample=b"hello",
        )

    assert exc_info.value.status_code == status.HTTP_413_CONTENT_TOO_LARGE
