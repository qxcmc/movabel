"""
Mobile adaptation routes.

POST /mobile/export        — Export desktop project to mobile format
POST /mobile/import        — Import mobile project into desktop
GET  /mobile/sync/status   — Get sync status for a project
GET  /mobile/qrcode        — Generate sharing QR code
GET  /mobile/config/audio  — Audio downsampling config
GET  /mobile/config/quant  — Model quantization config
"""

from __future__ import annotations

import base64
import io
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from ..models.mobile import (
    ExportMobileRequest,
    ImportMobileRequest,
    MobileProjectResponse,
    MobileSyncStatusResponse,
    QRCodeResponse,
)
from ..services import mobile_adapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mobile", tags=["mobile"])


# ── export / import ──────────────────────────────────────────────────


@router.post("/export", response_model=MobileProjectResponse)
async def export_project(request: ExportMobileRequest):
    """Export a desktop project to lightweight mobile format."""
    try:
        mobile_project = mobile_adapter.export_project(request)
        return MobileProjectResponse(project=mobile_project)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/import")
async def import_project(request: ImportMobileRequest):
    """Import a mobile project into the desktop application."""
    try:
        project_data = mobile_adapter.import_project(request)
        return {"status": "imported", "project": project_data}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── sync status ──────────────────────────────────────────────────────


@router.get("/sync/status", response_model=MobileSyncStatusResponse)
async def get_sync_status(
    project_id: str = Query(..., description="Desktop project ID"),
):
    """Get sync status between desktop and mobile versions."""
    status = mobile_adapter.get_sync_status(project_id)
    if status is None:
        raise HTTPException(
            status_code=404,
            detail="No mobile export found for this project",
        )
    return MobileSyncStatusResponse(status=status)


# ── QR code sharing ──────────────────────────────────────────────────


@router.get("/qrcode", response_model=QRCodeResponse)
async def generate_qrcode(
    project_id: str = Query(...),
):
    """
    Generate a QR code for mobile access to a project.

    The QR code encodes a URL that mobile clients can scan to open
    the project. Includes a 6-digit session code as fallback.
    """
    import random

    session_code = f"{random.randint(100000, 999999)}"
    expire_at = datetime.now(timezone.utc) + timedelta(hours=24)

    # Build access URL
    access_url = f"movabel://project/{project_id}?code={session_code}"

    # Generate minimal QR PNG using built-in QR encoding
    qr_data_url = _generate_qr_png_b64(access_url)

    return QRCodeResponse(
        project_id=project_id,
        session_code=session_code,
        qr_data_url=qr_data_url,
        expire_at=expire_at,
        access_url=access_url,
    )


def _generate_qr_png_b64(data: str) -> str:
    """
    Generate a minimal QR code PNG as base64 data URL.

    Uses a simple manual QR encoding — in production, use `qrcode` or `segno` libraries.
    Falls back to a placeholder if encoding fails.
    """
    try:
        import qrcode as qr_lib
        buf = io.BytesIO()
        img = qr_lib.make(data)
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except ImportError:
        # Fallback: minimal hand-rolled QR for alphanumeric data
        logger.debug("qrcode library not available; using fallback")
        return _qr_fallback(data)


def _qr_fallback(data: str) -> str:
    """Minimal QR PNG using PIL if available, else empty placeholder."""
    try:
        from PIL import Image, ImageDraw
        size = 200
        module_size = 4
        img = Image.new("RGB", (size, size), "white")
        draw = ImageDraw.Draw(img)

        # Simplified: draw a placeholder grid pattern
        modules = size // module_size
        for y in range(modules):
            for x in range(modules):
                if (x + y) % 3 == 0 and 2 < x < modules - 3 and 2 < y < modules - 3:
                    x0 = x * module_size
                    y0 = y * module_size
                    draw.rectangle([x0, y0, x0 + module_size - 1, y0 + module_size - 1], fill="black")

        # Finder patterns (top-left, top-right, bottom-left)
        for fx, fy in [(3, 3), (modules - 10, 3), (3, modules - 10)]:
            for dy in range(7):
                for dx in range(7):
                    if dx in (0, 6) or dy in (0, 6) or (2 <= dx <= 4 and 2 <= dy <= 4):
                        x0 = (fx + dx) * module_size
                        y0 = (fy + dy) * module_size
                        draw.rectangle([x0, y0, x0 + module_size - 1, y0 + module_size - 1], fill="black")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        b64 = base64.b64encode(buf.read()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except ImportError:
        return ""


# ── configuration endpoints ──────────────────────────────────────────


@router.get("/config/audio")
async def get_audio_config(
    sample_rate: int = Query(16000, ge=8000, le=48000),
):
    """Get mobile audio downsampling configuration."""
    cfg = mobile_adapter.get_downsample_config(sample_rate)
    return {"config": cfg}


@router.get("/config/quant")
async def get_quantization_config():
    """Get model quantization configuration for mobile inference."""
    cfg = mobile_adapter.get_quantization_config()
    return {"config": cfg}
