"""
Plugin marketplace routes.

GET    /plugins                — Browse plugin marketplace
GET    /plugins/{id}           — Plugin details
POST   /plugins/install        — Install plugin
DELETE /plugins/{id}           — Uninstall plugin
POST   /plugins/{id}/toggle    — Enable / disable plugin
POST   /plugins/{id}/rate      — Rate & review plugin
GET    /plugins/{id}/reviews   — List reviews
GET    /plugins/search         — Search plugins
GET    /plugins/categories     — List categories
GET    /plugins/updates        — Check for updates
GET    /plugins/installed      — List installed plugins
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.plugin import (
    PluginCategoriesResponse,
    PluginInstallRequest,
    PluginListResponse,
    PluginRateRequest,
    PluginReviewsResponse,
    PluginSearchRequest,
    PluginUninstallRequest,
    PluginUpdatesResponse,
)
from ..services import plugin_market

router = APIRouter(prefix="/plugins", tags=["plugins"])


# ── marketplace browsing ─────────────────────────────────────────────


@router.get("", response_model=PluginListResponse)
async def browse_plugins(
    query: str = Query(""),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("popularity"),
):
    """Browse the plugin marketplace with optional filters."""
    search = PluginSearchRequest(
        query=query,
        category=category,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
    )
    plugins, total = plugin_market.list_plugins(search)
    return PluginListResponse(
        plugins=plugins,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/installed", response_model=PluginListResponse)
async def list_installed_plugins():
    """List only installed plugins."""
    all_plugins, _ = plugin_market.list_plugins()
    installed = [p for p in all_plugins if p.installed]
    return PluginListResponse(
        plugins=installed,
        total=len(installed),
    )


@router.get("/search", response_model=PluginListResponse)
async def search_plugins(
    query: str = Query(..., min_length=1),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("popularity"),
):
    """Search plugins by name, description, or tags."""
    search = PluginSearchRequest(
        query=query,
        category=category,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
    )
    plugins, total = plugin_market.list_plugins(search)
    return PluginListResponse(
        plugins=plugins,
        total=total,
        page=page,
        page_size=page_size,
    )


# ── plugin details ───────────────────────────────────────────────────


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    """Get detailed info for a specific plugin."""
    plugin = plugin_market.get_plugin(plugin_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return {"plugin": plugin}


# ── installation ─────────────────────────────────────────────────────


@router.post("/install")
async def install_plugin(request: PluginInstallRequest):
    """Install a plugin from the marketplace."""
    try:
        plugin = plugin_market.install_plugin(request.plugin_id, request.version or "latest")
        return {"status": "installed", "plugin": plugin}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{plugin_id}")
async def uninstall_plugin(
    plugin_id: str,
    remove_data: bool = Query(True),
):
    """Uninstall a plugin."""
    success = plugin_market.uninstall_plugin(plugin_id, remove_data=remove_data)
    if not success:
        raise HTTPException(status_code=404, detail="Plugin not found or not installed")
    return {"status": "uninstalled", "plugin_id": plugin_id}


@router.post("/{plugin_id}/toggle")
async def toggle_plugin(plugin_id: str):
    """Enable or disable a plugin."""
    plugin = plugin_market.toggle_plugin(plugin_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    state = "enabled" if plugin.enabled else "disabled"
    return {"status": state, "plugin": plugin}


# ── ratings & reviews ────────────────────────────────────────────────


@router.post("/{plugin_id}/rate")
async def rate_plugin(plugin_id: str, request: PluginRateRequest):
    """Rate and optionally review a plugin."""
    plugin = plugin_market.get_plugin(plugin_id)
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    review = plugin_market.rate_plugin(plugin_id, request)
    return {"status": "rated", "review": review}


@router.get("/{plugin_id}/reviews", response_model=PluginReviewsResponse)
async def get_reviews(plugin_id: str):
    """Get all reviews for a plugin."""
    reviews, avg = plugin_market.get_reviews(plugin_id)
    return PluginReviewsResponse(reviews=reviews, average_rating=avg, total=len(reviews))


# ── categories ───────────────────────────────────────────────────────


@router.get("/categories", response_model=PluginCategoriesResponse)
async def list_categories():
    """List all plugin categories with counts."""
    cats = plugin_market.list_categories()
    return PluginCategoriesResponse(categories=cats, total=len(cats))


# ── updates ──────────────────────────────────────────────────────────


@router.get("/updates", response_model=PluginUpdatesResponse)
async def check_for_updates():
    """Check for available updates for installed plugins."""
    updates = plugin_market.check_updates()
    return PluginUpdatesResponse(updates=updates, total=len(updates))
