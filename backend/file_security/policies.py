from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UploadPolicy:
    name: str
    allowed_extensions: frozenset[str]
    allowed_content_types: frozenset[str]
    max_size_bytes: int
    sanitizer: str
    storage_prefix: str
    max_image_pixels: int | None = None


PURCHASE_AGREEMENT_PDF_POLICY = UploadPolicy(
    name="purchase_agreement_pdf",
    allowed_extensions=frozenset({".pdf"}),
    allowed_content_types=frozenset({"application/pdf"}),
    max_size_bytes=25 * 1024 * 1024,
    sanitizer="pdf_safe_copy_v1",
    storage_prefix="private/uploads/purchase-agreements",
)


IDENTITY_IMAGE_POLICY = UploadPolicy(
    name="identity_image",
    allowed_extensions=frozenset({".jpg", ".jpeg", ".png", ".webp"}),
    allowed_content_types=frozenset({"image/jpeg", "image/png", "image/webp"}),
    max_size_bytes=10 * 1024 * 1024,
    sanitizer="pillow_reencode_v1",
    storage_prefix="private/uploads/identity-images",
    max_image_pixels=12_000_000,
)
