"""
Storytelling workspace API routes.

Manages story projects with characters, paragraphs (dialogue detection),
and sound effect cues.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import models
from ..models import storytelling as st
from ..services import sfx_library
from ..services import storytelling as st_service

router = APIRouter(prefix="/projects/storytelling", tags=["storytelling"])


# ── projects ─────────────────────────────────────────────────────────

@router.get("/", response_model=st.StoryProjectsListResponse)
async def list_story_projects():
    items = st_service.list_projects()
    return st.StoryProjectsListResponse(projects=items, total=len(items))


@router.post("/", response_model=st.StoryProjectResponse, status_code=201)
async def create_story_project(payload: st.StoryProjectCreate):
    project = st_service.create_project(payload)
    return st.StoryProjectResponse(project=project)


@router.get("/{project_id}", response_model=st.StoryProjectResponse)
async def get_story_project(project_id: str):
    project = st_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return st.StoryProjectResponse(project=project)


@router.patch("/{project_id}", response_model=st.StoryProjectResponse)
async def update_story_project(
    project_id: str,
    payload: st.StoryProjectUpdate,
):
    project = st_service.update_project(
        project_id, payload.model_dump(exclude_none=True),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return st.StoryProjectResponse(project=project)


@router.delete("/{project_id}")
async def delete_story_project(project_id: str):
    ok = st_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


# ── characters ───────────────────────────────────────────────────────

@router.post(
    "/{project_id}/characters",
    response_model=st.StoryProjectResponse,
    status_code=201,
)
async def add_character(project_id: str, payload: st.StoryCharacterCreate):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Character name is required")
    project = st_service.add_character(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return st.StoryProjectResponse(project=project)


@router.patch(
    "/{project_id}/characters/{character_id}",
    response_model=st.StoryProjectResponse,
)
async def update_character(
    project_id: str,
    character_id: str,
    payload: st.StoryCharacterUpdate,
):
    project = st_service.update_character(project_id, character_id, payload)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or character not found",
        )
    return st.StoryProjectResponse(project=project)


@router.delete(
    "/{project_id}/characters/{character_id}",
    response_model=st.StoryProjectResponse,
)
async def delete_character(project_id: str, character_id: str):
    project = st_service.delete_character(project_id, character_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or character not found",
        )
    return st.StoryProjectResponse(project=project)


# ── paragraphs ───────────────────────────────────────────────────────

@router.post(
    "/{project_id}/paragraphs",
    response_model=st.StoryProjectResponse,
    status_code=201,
)
async def add_paragraph(project_id: str, payload: st.StoryParagraphCreate):
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Paragraph text is required")
    project = st_service.add_paragraph(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return st.StoryProjectResponse(project=project)


@router.patch(
    "/{project_id}/paragraphs/{paragraph_id}",
    response_model=st.StoryProjectResponse,
)
async def update_paragraph(
    project_id: str,
    paragraph_id: str,
    payload: st.StoryParagraphUpdate,
):
    project = st_service.update_paragraph(project_id, paragraph_id, payload)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or paragraph not found",
        )
    return st.StoryProjectResponse(project=project)


@router.delete(
    "/{project_id}/paragraphs/{paragraph_id}",
    response_model=st.StoryProjectResponse,
)
async def delete_paragraph(project_id: str, paragraph_id: str):
    project = st_service.delete_paragraph(project_id, paragraph_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or paragraph not found",
        )
    return st.StoryProjectResponse(project=project)


@router.post(
    "/{project_id}/paragraphs/reorder",
    response_model=st.StoryProjectResponse,
)
async def reorder_paragraphs(
    project_id: str,
    payload: models.ReorderRequest,
):
    project = st_service.reorder_paragraphs(project_id, payload.scene_ids)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return st.StoryProjectResponse(project=project)


@router.post(
    "/{project_id}/auto-assign",
    response_model=st.StoryProjectResponse,
)
async def auto_assign(project_id: str):
    """Auto-assign characters to paragraphs based on speaker name matching."""
    result = st_service.auto_assign_characters(project_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    project = st_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return st.StoryProjectResponse(project=project)


# ── SFX cues ─────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/sfx",
    response_model=st.StoryProjectResponse,
    status_code=201,
)
async def add_sfx_cue(project_id: str, payload: dict):
    if not payload.get("file_path"):
        raise HTTPException(status_code=400, detail="SFX file_path is required")
    project = st_service.add_sfx_cue(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return st.StoryProjectResponse(project=project)


@router.delete(
    "/{project_id}/sfx/{cue_id}",
    response_model=st.StoryProjectResponse,
)
async def delete_sfx_cue(project_id: str, cue_id: str):
    project = st_service.delete_sfx_cue(project_id, cue_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or cue not found",
        )
    return st.StoryProjectResponse(project=project)


# ── SFX library ──────────────────────────────────────────────────────

@router.get("/sfx-library")
async def list_sfx_library(category: str | None = None, search: str | None = None):
    sfx = sfx_library.list_sfx(category=category, search=search)
    return {"sfx": sfx, "total": len(sfx)}


@router.get("/sfx-library/categories")
async def list_sfx_categories():
    return {"categories": sfx_library.get_sfx_categories()}


@router.get("/sfx-library/user")
async def list_user_sfx_files():
    sfx = sfx_library.list_user_sfx()
    return {"user_sfx": sfx, "total": len(sfx)}


@router.post("/sfx-library/import")
async def import_sfx(payload: dict):
    source_dir = payload.get("source_dir")
    if not source_dir:
        raise HTTPException(status_code=400, detail="source_dir is required")
    try:
        result = sfx_library.import_sfx_folder(source_dir)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result
