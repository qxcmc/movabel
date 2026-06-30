"""Shared request models for workspace reorder operations."""

from pydantic import BaseModel


class ReorderRequest(BaseModel):
    scene_ids: list[str]
