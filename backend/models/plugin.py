"""
Pydantic models for the plugin marketplace system.

Defines plugin metadata, installation requests, search, ratings,
category taxonomy, and plugin manifest schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── plugin categories ────────────────────────────────────────────────

VALID_PLUGIN_CATEGORIES = [
    "tts_engine",
    "voice_profile",
    "audio_effect",
    "workflow_template",
    "sfx_pack",
    "live2d_model",
    "music_style",
]


class PluginCategory(BaseModel):
    """A category taxonomy entry for the plugin marketplace."""
    id: str = Field(..., description="Category slug")
    name: str = Field(..., description="Display name")
    description: str = Field("")
    icon: str = Field("", description="Icon class or emoji")
    plugin_count: int = Field(0)


# ── plugin manifest ──────────────────────────────────────────────────


class PluginManifestEntry(BaseModel):
    """Entry-point definition for a plugin."""
    type: str = Field(..., description="Entry type: tts_engine / effect / template / etc.")
    module: str = Field(..., description="Python module path to load")
    class_name: str = Field(..., description="Class name within the module")


class PluginPermission(BaseModel):
    """A permission declaration for sandbox enforcement."""
    name: str = Field(..., description="Permission identifier")
    description: str = Field("")


class PluginManifest(BaseModel):
    """Plugin manifest embedded in the plugin package."""
    id: str = Field(..., description="Unique plugin ID")
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field(..., description="Semver version string")
    min_app_version: str = Field("0.0.0", description="Minimum required Movabel version")
    author: str = Field("")
    description: str = Field("", max_length=2000)
    license: str = Field("MIT")
    homepage: str = Field("")
    repository: str = Field("")
    entry_points: list[PluginManifestEntry] = Field(default_factory=list)
    permissions: list[PluginPermission] = Field(default_factory=list)
    dependencies: dict[str, str] = Field(
        default_factory=dict,
        description="Plugin ID → version constraint mapping"
    )


# ── plugin info ──────────────────────────────────────────────────────


class PluginInfo(BaseModel):
    """Full metadata for a plugin in the marketplace."""
    id: str = Field(..., description="Unique plugin ID")
    name: str = Field(..., min_length=1, max_length=200)
    version: str = Field("1.0.0")
    author: str = Field("")
    description: str = Field("", max_length=2000)
    category: str = Field("tts_engine", description="One of VALID_PLUGIN_CATEGORIES")
    tags: list[str] = Field(default_factory=list)
    download_url: str = Field("")
    icon_url: str = Field("")
    screenshots: list[str] = Field(default_factory=list)
    rating: float = Field(0.0, ge=0.0, le=5.0, description="Average rating 0-5")
    rating_count: int = Field(0)
    installs: int = Field(0)
    size_bytes: int = Field(0, description="Download size in bytes")
    installed_size_bytes: int = Field(0, description="Uncompressed size in bytes")
    dependencies: dict[str, str] = Field(default_factory=dict)
    manifest: Optional[PluginManifest] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    installed: bool = Field(False)
    enabled: bool = Field(True)
    installed_version: Optional[str] = Field(None)
    installed_at: Optional[datetime] = Field(None)


# ── installation ─────────────────────────────────────────────────────


class PluginInstallRequest(BaseModel):
    """Request to install a plugin from the marketplace."""
    plugin_id: str = Field(..., description="Plugin ID to install")
    version: Optional[str] = Field(None, description="Specific version, latest if omitted")


class PluginUpdateRequest(BaseModel):
    """Request to update a plugin to a specific version."""
    plugin_id: str
    version: Optional[str] = Field(None)


class PluginUninstallRequest(BaseModel):
    """Request to uninstall a plugin."""
    plugin_id: str
    remove_data: bool = Field(True, description="Also delete plugin data/config")


# ── search ───────────────────────────────────────────────────────────


class PluginSearchRequest(BaseModel):
    """Search filters for the plugin marketplace."""
    query: str = Field("", description="Free-text search across name/description/tags")
    category: Optional[str] = Field(None, description="Filter by category slug")
    tags: list[str] = Field(default_factory=list)
    author: Optional[str] = Field(None)
    sort_by: str = Field("popularity", description="popularity / rating / newest / name")
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ── ratings & reviews ────────────────────────────────────────────────


class PluginReview(BaseModel):
    """A user review for a plugin."""
    id: str = Field(...)
    plugin_id: str
    user_name: str = Field("Anonymous")
    rating: float = Field(..., ge=0.0, le=5.0)
    title: str = Field("")
    body: str = Field("", max_length=2000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class PluginRateRequest(BaseModel):
    """Request to rate and optionally review a plugin."""
    rating: float = Field(..., ge=1.0, le=5.0)
    title: str = Field("", max_length=200)
    body: str = Field("", max_length=2000)
    user_name: str = Field("Anonymous", max_length=100)


# ── response wrappers ────────────────────────────────────────────────


class PluginListResponse(BaseModel):
    plugins: list[PluginInfo]
    total: int
    page: int = 1
    page_size: int = 20


class PluginCategoriesResponse(BaseModel):
    categories: list[PluginCategory]
    total: int


class PluginReviewsResponse(BaseModel):
    reviews: list[PluginReview]
    average_rating: float
    total: int


class PluginUpdateInfo(BaseModel):
    """Update check result for a single plugin."""
    plugin_id: str
    installed_version: str
    latest_version: str
    has_update: bool
    update_url: str = ""


class PluginUpdatesResponse(BaseModel):
    updates: list[PluginUpdateInfo]
    total: int
