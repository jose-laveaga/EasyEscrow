from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from file_security.models import FileSecurityReport, FileSecurityStatus, MalwareScanStatus
from file_security.policies import UploadPolicy
from file_security.services.exceptions import FileSecurityError
from file_security.services.malware import scan_file


PDF_SUSPICIOUS_MARKERS = (
    b"/JS",
    b"/JavaScript",
    b"/AA",
    b"/OpenAction",
    b"/Launch",
    b"/EmbeddedFile",
    b"/RichMedia",
    b"/XFA",
)


@dataclass(frozen=True)
class SecuredUpload:
    stored_file_name: str
    report: FileSecurityReport


def secure_uploaded_file(
    *,
    uploaded_file,
    policy: UploadPolicy,
    uploaded_by=None,
    error_field: str = "file",
) -> SecuredUpload:
    report = FileSecurityReport.objects.create(
        policy_name=policy.name,
        status=FileSecurityStatus.ERROR,
        original_filename=_clean_filename(getattr(uploaded_file, "name", "")),
        client_content_type=(getattr(uploaded_file, "content_type", "") or "")[:255],
    )
    if uploaded_by is not None and getattr(uploaded_by, "is_authenticated", False):
        report.uploaded_by = uploaded_by
        report.save(update_fields=["uploaded_by"])

    temp_path = None
    try:
        temp_path, size_bytes, sha256 = _write_to_temp(uploaded_file)
        report.size_bytes = size_bytes
        report.sha256 = sha256
        report.extension = Path(report.original_filename).suffix.lower()[:20]
        report.save(update_fields=["size_bytes", "sha256", "extension"])

        _validate_size(size_bytes=size_bytes, policy=policy)
        detected_content_type = _detect_content_type(temp_path)
        report.detected_content_type = detected_content_type
        report.save(update_fields=["detected_content_type"])
        _validate_type(
            extension=report.extension,
            client_content_type=report.client_content_type,
            detected_content_type=detected_content_type,
            policy=policy,
        )

        scan_result = scan_file(temp_path)
        report.malware_scan_status = scan_result.status
        report.malware_scan_detail = scan_result.detail
        report.save(update_fields=["malware_scan_status", "malware_scan_detail"])
        if scan_result.status == MalwareScanStatus.INFECTED:
            raise FileSecurityError(
                reason_code="malware_detected",
                reason="Malware scanner detected unsafe content in the uploaded file.",
            )

        sanitized_bytes, sanitized_extension, sanitizer = _sanitize(
            temp_path=temp_path,
            detected_content_type=detected_content_type,
            policy=policy,
        )
        stored_file_name = _store_sanitized_file(
            sanitized_bytes=sanitized_bytes,
            sanitized_extension=sanitized_extension,
            policy=policy,
            sha256=sha256,
        )

        report.status = FileSecurityStatus.ACCEPTED
        report.reason_code = ""
        report.reason = ""
        report.sanitizer = sanitizer
        report.stored_file_name = stored_file_name
        report.save(
            update_fields=[
                "status",
                "reason_code",
                "reason",
                "sanitizer",
                "stored_file_name",
            ]
        )
        return SecuredUpload(stored_file_name=stored_file_name, report=report)
    except FileSecurityError as exc:
        _reject_report(report=report, reason_code=exc.reason_code, reason=exc.reason)
        raise ValidationError({error_field: exc.reason}) from exc
    finally:
        if temp_path:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _write_to_temp(uploaded_file) -> tuple[Path, int, str]:
    digest = hashlib.sha256()
    size_bytes = 0
    fd, raw_path = tempfile.mkstemp(prefix="easyescrow-upload-", suffix=".tmp")
    path = Path(raw_path)
    try:
        with os.fdopen(fd, "wb") as temp_file:
            for chunk in uploaded_file.chunks():
                size_bytes += len(chunk)
                digest.update(chunk)
                temp_file.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path, size_bytes, digest.hexdigest()


def _validate_size(*, size_bytes: int, policy: UploadPolicy) -> None:
    if size_bytes <= 0:
        raise FileSecurityError(reason_code="empty_file", reason="Uploaded file is empty.")
    if size_bytes > policy.max_size_bytes:
        raise FileSecurityError(
            reason_code="file_too_large",
            reason=f"Uploaded file exceeds the {policy.max_size_bytes} byte limit.",
        )


def _validate_type(
    *,
    extension: str,
    client_content_type: str,
    detected_content_type: str,
    policy: UploadPolicy,
) -> None:
    if extension not in policy.allowed_extensions:
        raise FileSecurityError(
            reason_code="extension_not_allowed",
            reason="Uploaded file extension is not allowed for this upload type.",
        )
    if client_content_type and client_content_type not in policy.allowed_content_types:
        raise FileSecurityError(
            reason_code="client_mime_not_allowed",
            reason="Uploaded file MIME type is not allowed for this upload type.",
        )
    if detected_content_type not in policy.allowed_content_types:
        raise FileSecurityError(
            reason_code="magic_bytes_not_allowed",
            reason="Uploaded file content does not match an allowed file type.",
        )


def _detect_content_type(path: Path) -> str:
    with path.open("rb") as file:
        header = file.read(32)
    if header.startswith(b"%PDF-"):
        return "application/pdf"
    if header.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def _sanitize(
    *,
    temp_path: Path,
    detected_content_type: str,
    policy: UploadPolicy,
) -> tuple[bytes, str, str]:
    if detected_content_type == "application/pdf":
        return _sanitize_pdf(temp_path), ".pdf", policy.sanitizer
    if detected_content_type in {"image/jpeg", "image/png", "image/webp"}:
        return _sanitize_image(
            temp_path=temp_path,
            detected_content_type=detected_content_type,
            policy=policy,
        )
    raise FileSecurityError(
        reason_code="sanitizer_not_available",
        reason="No sanitizer is available for this file type.",
    )


def _sanitize_pdf(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise FileSecurityError(reason_code="invalid_pdf", reason="Uploaded PDF is malformed.")
    lowered = data.lower()
    for marker in PDF_SUSPICIOUS_MARKERS:
        if marker.lower() in lowered:
            raise FileSecurityError(
                reason_code="pdf_suspicious_content",
                reason="Uploaded PDF contains active or embedded content that is not allowed.",
            )
    return data


def _sanitize_image(
    *,
    temp_path: Path,
    detected_content_type: str,
    policy: UploadPolicy,
) -> tuple[bytes, str, str]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise FileSecurityError(
            reason_code="image_sanitizer_unavailable",
            reason="Image sanitizer is unavailable.",
        ) from exc

    try:
        with Image.open(temp_path) as image:
            image.verify()
        with Image.open(temp_path) as image:
            width, height = image.size
            if policy.max_image_pixels is not None and width * height > policy.max_image_pixels:
                raise FileSecurityError(
                    reason_code="image_too_large",
                    reason="Uploaded image dimensions exceed the allowed limit.",
                )
            if detected_content_type == "image/png":
                output_format = "PNG"
                output_extension = ".png"
                sanitized = image.convert("RGBA")
            else:
                output_format = "JPEG"
                output_extension = ".jpg"
                sanitized = image.convert("RGB")

            with tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024) as output:
                sanitized.save(output, format=output_format, optimize=True)
                output.seek(0)
                return output.read(), output_extension, policy.sanitizer
    except FileSecurityError:
        raise
    except Exception as exc:
        raise FileSecurityError(
            reason_code="invalid_image",
            reason="Uploaded image could not be decoded and sanitized.",
        ) from exc


def _store_sanitized_file(
    *,
    sanitized_bytes: bytes,
    sanitized_extension: str,
    policy: UploadPolicy,
    sha256: str,
) -> str:
    stored_name = f"{policy.storage_prefix}/{sha256[:2]}/{sha256}{sanitized_extension}"
    return default_storage.save(stored_name, ContentFile(sanitized_bytes))


def _reject_report(*, report: FileSecurityReport, reason_code: str, reason: str) -> None:
    report.status = (
        FileSecurityStatus.ERROR
        if reason_code.endswith("_error") or reason_code.endswith("_unavailable")
        else FileSecurityStatus.REJECTED
    )
    report.reason_code = reason_code
    report.reason = reason
    report.save(update_fields=["status", "reason_code", "reason"])


def _clean_filename(filename: str) -> str:
    filename = Path(filename or "").name
    filename = re.sub(r"[^A-Za-z0-9._ -]", "_", filename).strip()
    return filename[:255]
