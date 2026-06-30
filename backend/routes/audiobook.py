"""
Audiobook workspace API routes.

Manages audiobook projects with chapters, character profiles,
narrator configuration, and text segmentation.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import models
from ..models import audiobook as ab
from ..services import audiobook as ab_service
from ..services import text_analyzer

router = APIRouter(prefix="/projects/audiobook", tags=["audiobook"])


# ── projects ─────────────────────────────────────────────────────────

@router.get("/", response_model=ab.AudiobookProjectsListResponse)
async def list_projects():
    items = ab_service.list_projects()
    return ab.AudiobookProjectsListResponse(projects=items, total=len(items))


@router.post("/", response_model=ab.AudiobookProjectResponse, status_code=201)
async def create_project(payload: ab.AudiobookProjectCreate):
    project = ab_service.create_project(payload)
    return ab.AudiobookProjectResponse(project=project)


@router.get("/{project_id}", response_model=ab.AudiobookProjectResponse)
async def get_project(project_id: str):
    project = ab_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ab.AudiobookProjectResponse(project=project)


@router.patch("/{project_id}", response_model=ab.AudiobookProjectResponse)
async def update_project(project_id: str, payload: ab.AudiobookProjectUpdate):
    project = ab_service.update_project(
        project_id, payload.model_dump(exclude_none=True),
    )
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ab.AudiobookProjectResponse(project=project)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    ok = ab_service.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


# ── chapters ─────────────────────────────────────────────────────────

@router.post(
    "/{project_id}/chapters",
    response_model=ab.AudiobookProjectResponse,
    status_code=201,
)
async def add_chapter(project_id: str, payload: ab.AudiobookChapterCreate):
    project = ab_service.add_chapter(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ab.AudiobookProjectResponse(project=project)


@router.patch(
    "/{project_id}/chapters/{chapter_id}",
    response_model=ab.AudiobookProjectResponse,
)
async def update_chapter(
    project_id: str,
    chapter_id: str,
    payload: ab.AudiobookChapterUpdate,
):
    project = ab_service.update_chapter(project_id, chapter_id, payload)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or chapter not found",
        )
    return ab.AudiobookProjectResponse(project=project)


@router.delete(
    "/{project_id}/chapters/{chapter_id}",
    response_model=ab.AudiobookProjectResponse,
)
async def delete_chapter(project_id: str, chapter_id: str):
    project = ab_service.delete_chapter(project_id, chapter_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or chapter not found",
        )
    return ab.AudiobookProjectResponse(project=project)


@router.post(
    "/{project_id}/chapters/reorder",
    response_model=ab.AudiobookProjectResponse,
)
async def reorder_chapters(project_id: str, payload: models.ReorderRequest):
    project = ab_service.reorder_chapters(project_id, payload.scene_ids)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ab.AudiobookProjectResponse(project=project)


@router.post(
    "/{project_id}/chapters/{chapter_id}/segment",
    response_model=ab.AudiobookProjectResponse,
)
async def segment_chapter(project_id: str, chapter_id: str):
    """Auto-segment a chapter into TTS batches based on project strategy."""
    project = ab_service.segment_chapter(project_id, chapter_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or chapter not found",
        )
    return ab.AudiobookProjectResponse(project=project)


# ── characters ───────────────────────────────────────────────────────

@router.post(
    "/{project_id}/characters",
    response_model=ab.AudiobookProjectResponse,
    status_code=201,
)
async def add_character(project_id: str, payload: ab.CharacterProfileCreate):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Character name required")
    project = ab_service.add_character(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return ab.AudiobookProjectResponse(project=project)


@router.patch(
    "/{project_id}/characters/{character_id}",
    response_model=ab.AudiobookProjectResponse,
)
async def update_character(
    project_id: str,
    character_id: str,
    payload: ab.CharacterProfileUpdate,
):
    project = ab_service.update_character(project_id, character_id, payload)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or character not found",
        )
    return ab.AudiobookProjectResponse(project=project)


@router.delete(
    "/{project_id}/characters/{character_id}",
    response_model=ab.AudiobookProjectResponse,
)
async def delete_character(project_id: str, character_id: str):
    project = ab_service.delete_character(project_id, character_id)
    if project is None:
        raise HTTPException(
            status_code=404, detail="Project or character not found",
        )
    return ab.AudiobookProjectResponse(project=project)


# ── text analysis ────────────────────────────────────────────────────

@router.post(
    "/{project_id}/analyze",
    response_model=ab.TextAnalysisResponse,
)
async def analyze_text(project_id: str):
    """Analyze full text: detect chapters and characters."""
    project = ab_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    all_text = "\n\n".join(ch.text for ch in project.chapters) or project.raw_text
    if not all_text.strip():
        raise HTTPException(status_code=400, detail="No text content to analyze.")

    chapters_data = text_analyzer.detect_chapters(all_text)
    characters_data = text_analyzer.extract_character_names(all_text)

    return ab.TextAnalysisResponse(
        chapters=[
            {"title": cd["title"], "start_pos": cd["start_pos"], "end_pos": cd["end_pos"]}
            for cd in chapters_data
        ],
        characters=characters_data,
        total_words=len(all_text.split()),
    )


@router.post("/{project_id}/auto-detect-characters")
async def auto_detect_characters(project_id: str):
    """Auto-detect characters from chapter texts and return candidates."""
    result = ab_service.auto_detect_characters(project_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
