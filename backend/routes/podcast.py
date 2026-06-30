"""
Podcast workspace API routes.

Manages podcast projects with speaker turns, templates, Intro/Outro,
and post-processing configuration.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import models
from ..models import podcast as pc
from ..services import podcast as pc_service
from ..services import podcast_templates

router = APIRouter(prefix="/projects/podcast", tags=["podcast"])


# ── projects ─────────────────────────────────────────────────────────

@router.get("/", response_model=pc.PodcastProjectsListResponse)
async def list_projects():
    items = pc_service.list_projects()
    return pc.PodcastProjectsListResponse(projects=items, total=len(items))


@router.post("/", response_model=pc.PodcastProjectResponse, status_code=201)
async def create_project(payload: pc.PodcastProjectCreate):
    project = pc_service.create_project(payload)
    return pc.PodcastProjectResponse(project=project)


@router.get("/{project_id}", response_model=pc.PodcastProjectResponse)
async def get_project(project_id: str):
    project = pc_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return pc.PodcastProjectResponse(project=project)


@router.patch("/{project_id}", response_model=pc.PodcastProjectResponse)
async def update_project(project_id: str, payload: pc.PodcastProjectUpdate):
    project = pc_service.update_project(
        project_id, payload.model_dump(exclude_none=True),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return pc.PodcastProjectResponse(project=project)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    ok = pc_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


# ── templates ────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    choices = podcast_templates.list_template_choices()
    return {"templates": choices, "total": len(choices)}


@router.get("/templates/{template_id}")
async def get_template(template_id: str):
    tpl = podcast_templates.get_template(template_id)
    if tpl is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"template": tpl.model_dump()}


@router.post(
    "/{project_id}/templates/{template_id}/apply",
    response_model=pc.PodcastProjectResponse,
)
async def apply_template(project_id: str, template_id: str):
    project = pc_service.apply_template(project_id, template_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or template not found",
        )
    return pc.PodcastProjectResponse(project=project)


# ── speaker turns ────────────────────────────────────────────────────

@router.post(
    "/{project_id}/turns",
    response_model=pc.PodcastProjectResponse,
    status_code=201,
)
async def add_turn(project_id: str, payload: pc.SpeakerTurnCreate):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Turn text is required")
    project = pc_service.add_turn(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return pc.PodcastProjectResponse(project=project)


@router.patch(
    "/{project_id}/turns/{turn_id}",
    response_model=pc.PodcastProjectResponse,
)
async def update_turn(
    project_id: str,
    turn_id: str,
    payload: pc.SpeakerTurnUpdate,
):
    project = pc_service.update_turn(project_id, turn_id, payload)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or turn not found",
        )
    return pc.PodcastProjectResponse(project=project)


@router.delete(
    "/{project_id}/turns/{turn_id}",
    response_model=pc.PodcastProjectResponse,
)
async def delete_turn(project_id: str, turn_id: str):
    project = pc_service.delete_turn(project_id, turn_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or turn not found",
        )
    return pc.PodcastProjectResponse(project=project)


@router.post(
    "/{project_id}/turns/reorder",
    response_model=pc.PodcastProjectResponse,
)
async def reorder_turns(project_id: str, payload: models.ReorderRequest):
    project = pc_service.reorder_turns(project_id, payload.scene_ids)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return pc.PodcastProjectResponse(project=project)


# ── post-processing ─────────────────────────────────────────────────

@router.get("/{project_id}/post-processing")
async def get_post_processing(project_id: str):
    config = pc_service.get_post_processing(project_id)
    if config is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"config": config.model_dump()}


@router.put("/{project_id}/post-processing", response_model=pc.PodcastProjectResponse)
async def update_post_processing(project_id: str, payload: dict[str, object]):
    project = pc_service.update_post_processing(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return pc.PodcastProjectResponse(project=project)
