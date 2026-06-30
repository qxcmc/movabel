"""
Commercial workspace API routes.

Manages commercial/advertisement voice-over projects with emotion presets,
speed curves, and multi-language mixing.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import models
from ..models import commercial as cm
from ..services import commercial as com_service
from ..services import emotion_presets

router = APIRouter(prefix="/projects/commercial", tags=["commercial"])


# ── emotion presets ──────────────────────────────────────────────────

@router.get("/presets", response_model=cm.EmotionPresetsListResponse)
async def list_presets():
    return cm.EmotionPresetsListResponse(presets=emotion_presets.list_presets())


# ── projects ─────────────────────────────────────────────────────────

@router.get("/", response_model=cm.CommercialProjectsListResponse)
async def list_commercial_projects():
    items = com_service.list_projects()
    return cm.CommercialProjectsListResponse(projects=items, total=len(items))


@router.post("/", response_model=cm.CommercialProjectResponse, status_code=201)
async def create_commercial_project(payload: cm.CommercialProjectCreate):
    project = com_service.create_project(payload)
    return cm.CommercialProjectResponse(project=project)


@router.get("/{project_id}", response_model=cm.CommercialProjectResponse)
async def get_commercial_project(project_id: str):
    project = com_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return cm.CommercialProjectResponse(project=project)


@router.patch("/{project_id}", response_model=cm.CommercialProjectResponse)
async def update_commercial_project(
    project_id: str,
    payload: cm.CommercialProjectUpdate,
):
    project = com_service.update_project(
        project_id, payload.model_dump(exclude_none=True),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return cm.CommercialProjectResponse(project=project)


@router.delete("/{project_id}")
async def delete_commercial_project(project_id: str):
    ok = com_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


# ── segments ─────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/segments",
    response_model=cm.CommercialProjectResponse,
    status_code=201,
)
async def add_segment(project_id: str, payload: cm.CommercialSegmentCreate):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Segment text is required")
    project = com_service.add_segment(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return cm.CommercialProjectResponse(project=project)


@router.patch(
    "/{project_id}/segments/{segment_id}",
    response_model=cm.CommercialProjectResponse,
)
async def update_segment(
    project_id: str,
    segment_id: str,
    payload: cm.CommercialSegmentUpdate,
):
    project = com_service.update_segment(project_id, segment_id, payload)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or segment not found",
        )
    return cm.CommercialProjectResponse(project=project)


@router.delete(
    "/{project_id}/segments/{segment_id}",
    response_model=cm.CommercialProjectResponse,
)
async def delete_segment(project_id: str, segment_id: str):
    project = com_service.delete_segment(project_id, segment_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or segment not found",
        )
    return cm.CommercialProjectResponse(project=project)


@router.post(
    "/{project_id}/segments/reorder",
    response_model=cm.CommercialProjectResponse,
)
async def reorder_segments(
    project_id: str,
    payload: models.ReorderRequest,
):
    project = com_service.reorder_segments(project_id, payload.scene_ids)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return cm.CommercialProjectResponse(project=project)
