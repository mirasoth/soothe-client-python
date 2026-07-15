"""Image attachment compaction for appkit (RFC-629 Layer 1).

Downscales ``image/*`` payloads when either dimension exceeds a max size.
Non-images and decode failures pass through unchanged. Requires Pillow when
compaction is requested; without Pillow, inputs are returned unchanged.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class CompactImageOptions:
    """Controls ``compact_image_attachment``. Zero / unset fields use defaults."""

    max_dim: int = 768
    jpeg_quality: int = 85


def _compact_defaults(opts: CompactImageOptions | None) -> tuple[int, int]:
    max_dim, quality = 768, 85
    if opts is None:
        return max_dim, quality
    if opts.max_dim > 0:
        max_dim = opts.max_dim
    if opts.jpeg_quality > 0:
        quality = opts.jpeg_quality
    return max_dim, quality


def compact_image_attachment(
    mime_type: str,
    data_b64: str,
    opts: CompactImageOptions | None = None,
) -> tuple[str, str]:
    """Downscale an image attachment when either dimension exceeds ``max_dim``.

    Args:
        mime_type: Attachment MIME type (e.g. ``image/png``).
        data_b64: Base64-encoded image bytes.
        opts: Optional size / JPEG quality overrides.

    Returns:
        ``(out_mime, out_b64)``. Non-images and failures return inputs unchanged.
    """
    if not data_b64 or not mime_type.startswith("image/"):
        return mime_type, data_b64
    try:
        from PIL import Image
    except ImportError:
        return mime_type, data_b64

    try:
        raw = base64.b64decode(data_b64, validate=False)
    except Exception:
        return mime_type, data_b64
    if not raw:
        return mime_type, data_b64

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            w, h = img.size
            max_dim, quality = _compact_defaults(opts)
            if w <= max_dim and h <= max_dim:
                return mime_type, data_b64
            if w >= h:
                nw = max_dim if w > max_dim else w
                nh = max(1, h * nw // w) if w > max_dim else h
            else:
                nh = max_dim if h > max_dim else h
                nw = max(1, w * nh // h) if h > max_dim else w
            resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            out_mime = mime_type
            if mime_type == "image/png":
                if resized.mode not in ("RGB", "RGBA", "L", "P"):
                    resized = resized.convert("RGBA")
                resized.save(buf, format="PNG")
            else:
                if resized.mode != "RGB":
                    resized = resized.convert("RGB")
                resized.save(buf, format="JPEG", quality=quality)
                out_mime = "image/jpeg"
            return out_mime, base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return mime_type, data_b64


def compact_attachments(
    atts: list[dict[str, Any]] | None,
    opts: CompactImageOptions | None = None,
) -> list[dict[str, Any]]:
    """Apply ``compact_image_attachment`` to each ``mime_type`` + ``data`` map."""
    if not atts:
        return atts or []
    out: list[dict[str, Any]] = []
    for att in atts:
        cp = dict(att)
        mime = cp.get("mime_type")
        data = cp.get("data")
        if isinstance(mime, str) and isinstance(data, str) and mime and data:
            out_mime, out_data = compact_image_attachment(mime, data, opts)
            cp["mime_type"] = out_mime
            cp["data"] = out_data
        out.append(cp)
    return out


__all__ = [
    "CompactImageOptions",
    "compact_attachments",
    "compact_image_attachment",
]
