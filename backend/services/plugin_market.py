"""
Plugin marketplace service — manages plugin registry, installation,
uninstallation, ratings, reviews, and search.

Plugins stored as JSON under data_dir/plugins/registry.json.
Installed plugins live in data_dir/plugins/installed/<plugin_id>/.
"""

from __future__ import annotations

import json
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .. import config
from ..models.plugin import (
    PluginCategory,
    PluginInfo,
    PluginRateRequest,
    PluginReview,
    PluginSearchRequest,
    VALID_PLUGIN_CATEGORIES,
)

logger = logging.getLogger(__name__)

# ── paths ────────────────────────────────────────────────────────────


def _data_dir() -> Path:
    return config.get_data_dir()


def _registry_path() -> Path:
    d = _data_dir() / "plugins"
    d.mkdir(parents=True, exist_ok=True)
    return d / "registry.json"


def _installed_dir() -> Path:
    d = _data_dir() / "plugins" / "installed"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _reviews_path(plugin_id: str) -> Path:
    d = _data_dir() / "plugins" / "reviews"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{plugin_id}.json"


# ── registry persistence ─────────────────────────────────────────────


def _load_registry() -> list[PluginInfo]:
    path = _registry_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [PluginInfo(**item) for item in data]
    except Exception as exc:
        logger.warning("Failed to load plugin registry: %s", exc)
        return []


def _save_registry(plugins: list[PluginInfo]) -> None:
    path = _registry_path()
    data = [p.model_dump(mode="json") for p in plugins]
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── built-in placeholder marketplace ─────────────────────────────────


BUILTIN_PLUGINS: list[PluginInfo] = [
    PluginInfo(
        id="tts_coqui",
        name="Coqui TTS Plugin",
        version="1.0.0",
        author="Movabel",
        description="Open-source Coqui TTS engine with multi-language support",
        category="tts_engine",
        tags=["tts", "coqui", "opensource", "multilingual"],
        rating=4.5,
        rating_count=128,
        installs=1024,
        size_bytes=2048000,
    ),
    PluginInfo(
        id="reverb_pro",
        name="Reverb Pro",
        version="1.2.0",
        author="AudioFX Studio",
        description="Professional-grade reverb effects with 50+ presets",
        category="audio_effect",
        tags=["reverb", "effect", "studio", "presets"],
        rating=4.2,
        rating_count=89,
        installs=756,
        size_bytes=512000,
    ),
    PluginInfo(
        id="podcast_intro_templates",
        name="Podcast Intro Templates",
        version="1.0.0",
        author="Movabel Community",
        description="15 professional podcast intro/outro templates with music",
        category="workflow_template",
        tags=["podcast", "template", "intro", "outro"],
        rating=4.7,
        rating_count=56,
        installs=340,
        size_bytes=3072000,
    ),
    PluginInfo(
        id="cinematic_sfx",
        name="Cinematic SFX Pack",
        version="2.1.0",
        author="SoundForge",
        description="200+ cinematic sound effects: whooshes, risers, impacts, drones",
        category="sfx_pack",
        tags=["cinematic", "sfx", "whoosh", "impact", "drone"],
        rating=4.8,
        rating_count=215,
        installs=1890,
        size_bytes=51200000,
    ),
    PluginInfo(
        id="anime_voice_profiles",
        name="Anime Voice Profiles",
        version="1.0.1",
        author="VoiceCraft",
        description="10 anime-style voice profiles with Japanese support",
        category="voice_profile",
        tags=["anime", "japanese", "voice", "profiles"],
        rating=4.0,
        rating_count=72,
        installs=512,
        size_bytes=40960000,
    ),
    PluginInfo(
        id="lofi_music_styles",
        name="Lo-Fi Music Style Pack",
        version="1.0.0",
        author="ChillBeats",
        description="20 lo-fi hip hop music generation style presets",
        category="music_style",
        tags=["lofi", "hiphop", "chill", "music", "style"],
        rating=4.3,
        rating_count=45,
        installs=230,
        size_bytes=102400,
    ),
    PluginInfo(
        id="live2d_chibi",
        name="Chibi Live2D Models",
        version="1.0.0",
        author="MascotStudio",
        description="3 chibi-style Live2D avatar models for streaming",
        category="live2d_model",
        tags=["live2d", "chibi", "avatar", "streaming"],
        rating=4.6,
        rating_count=38,
        installs=180,
        size_bytes=8192000,
    ),
]


# ── registry CRUD ────────────────────────────────────────────────────


def list_plugins(search: Optional[PluginSearchRequest] = None) -> tuple[list[PluginInfo], int]:
    """
    List plugins from the registry with optional search/filter.
    Returns (plugins, total).
    """
    plugins = list(BUILTIN_PLUGINS)

    # Merge with installed status from registry
    registry = _load_registry()
    installed_map = {p.id: p for p in registry}

    for plugin in plugins:
        if plugin.id in installed_map:
            plugin.installed = installed_map[plugin.id].installed
            plugin.enabled = installed_map[plugin.id].enabled
            plugin.installed_version = installed_map[plugin.id].installed_version
            plugin.installed_at = installed_map[plugin.id].installed_at

    if search:
        # Filter
        if search.query:
            q = search.query.lower()
            plugins = [
                p for p in plugins
                if q in p.name.lower()
                or q in p.description.lower()
                or any(q in t.lower() for t in p.tags)
            ]
        if search.category:
            plugins = [p for p in plugins if p.category == search.category]
        if search.tags:
            plugins = [
                p for p in plugins
                if any(t in p.tags for t in search.tags)
            ]
        if search.author:
            plugins = [p for p in plugins if p.author == search.author]

        # Sort
        sort_key = search.sort_by or "popularity"
        if sort_key == "popularity":
            plugins.sort(key=lambda p: p.installs, reverse=True)
        elif sort_key == "rating":
            plugins.sort(key=lambda p: p.rating, reverse=True)
        elif sort_key == "newest":
            plugins.sort(key=lambda p: p.created_at, reverse=True)
        elif sort_key == "name":
            plugins.sort(key=lambda p: p.name.lower())

        total = len(plugins)

        # Paginate
        start = (search.page - 1) * search.page_size
        end = start + search.page_size
        plugins = plugins[start:end]

        return plugins, total

    return plugins, len(plugins)


def get_plugin(plugin_id: str) -> PluginInfo | None:
    """Get plugin details by ID."""
    for p in BUILTIN_PLUGINS:
        if p.id == plugin_id:
            # Merge installed status
            installed = get_installed_plugin(plugin_id)
            if installed:
                p.installed = True
                p.enabled = installed.enabled
                p.installed_version = installed.installed_version
                p.installed_at = installed.installed_at
            return p
    return None


def install_plugin(plugin_id: str, version: str = "latest") -> PluginInfo:
    """
    Install a plugin from the marketplace.

    In production this would download from download_url.
    Here we register it in the local registry.
    """
    plugin = get_plugin(plugin_id)
    if plugin is None:
        raise ValueError(f"Plugin not found: {plugin_id}")

    registry = _load_registry()
    existing = None
    for p in registry:
        if p.id == plugin_id:
            existing = p
            break

    plugin.installed = True
    plugin.enabled = True
    plugin.installed_version = version if version != "latest" else plugin.version
    plugin.installed_at = datetime.now(timezone.utc)

    if existing:
        for i, p in enumerate(registry):
            if p.id == plugin_id:
                registry[i] = plugin
                break
    else:
        registry.append(plugin)

    _save_registry(registry)

    # Ensure installed directory exists
    install_path = _installed_dir() / plugin_id
    install_path.mkdir(parents=True, exist_ok=True)

    logger.info("Plugin installed: %s v%s", plugin_id, plugin.installed_version)
    return plugin


def uninstall_plugin(plugin_id: str, remove_data: bool = True) -> bool:
    """Uninstall a plugin."""
    registry = _load_registry()
    found = False
    for i, p in enumerate(registry):
        if p.id == plugin_id:
            registry.pop(i)
            found = True
            break

    if not found:
        return False

    _save_registry(registry)

    # Remove installed directory
    if remove_data:
        install_path = _installed_dir() / plugin_id
        if install_path.exists():
            shutil.rmtree(install_path)

    logger.info("Plugin uninstalled: %s", plugin_id)
    return True


def toggle_plugin(plugin_id: str) -> PluginInfo | None:
    """Toggle a plugin's enabled state."""
    registry = _load_registry()
    for p in registry:
        if p.id == plugin_id:
            p.enabled = not p.enabled
            _save_registry(registry)
            logger.info("Plugin %s %s", plugin_id, "enabled" if p.enabled else "disabled")
            return p

    # Check built-in
    for p in BUILTIN_PLUGINS:
        if p.id == plugin_id:
            p.installed = True
            p.enabled = not p.enabled
            p.installed_version = p.version
            p.installed_at = datetime.now(timezone.utc)
            registry.append(p)
            _save_registry(registry)
            return p

    return None


def get_installed_plugin(plugin_id: str) -> PluginInfo | None:
    """Get installed plugin info."""
    registry = _load_registry()
    for p in registry:
        if p.id == plugin_id:
            return p
    return None


# ── ratings & reviews ────────────────────────────────────────────────


def rate_plugin(plugin_id: str, rating_request: PluginRateRequest) -> PluginReview:
    """Submit a rating and optional review for a plugin."""
    reviews = _load_reviews(plugin_id)
    review = PluginReview(
        id=str(uuid.uuid4()),
        plugin_id=plugin_id,
        user_name=rating_request.user_name,
        rating=rating_request.rating,
        title=rating_request.title,
        body=rating_request.body,
        created_at=datetime.now(timezone.utc),
    )
    reviews.append(review)
    _save_reviews(plugin_id, reviews)
    logger.info("Review added for plugin %s: rating %.1f", plugin_id, rating_request.rating)
    return review


def get_reviews(plugin_id: str) -> tuple[list[PluginReview], float]:
    """Get reviews and average rating for a plugin."""
    reviews = _load_reviews(plugin_id)
    if not reviews:
        return [], 0.0
    avg = sum(r.rating for r in reviews) / len(reviews)
    return reviews, round(avg, 1)


def _load_reviews(plugin_id: str) -> list[PluginReview]:
    path = _reviews_path(plugin_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [PluginReview(**item) for item in data]
    except Exception:
        return []


def _save_reviews(plugin_id: str, reviews: list[PluginReview]) -> None:
    path = _reviews_path(plugin_id)
    data = [r.model_dump(mode="json") for r in reviews]
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


# ── updates ──────────────────────────────────────────────────────────


def check_updates() -> list[dict]:
    """Check for available updates for installed plugins."""
    registry = _load_registry()
    updates = []
    for installed in registry:
        if not installed.installed:
            continue
        # Find market version
        for market in BUILTIN_PLUGINS:
            if market.id == installed.id and market.version != installed.installed_version:
                updates.append({
                    "plugin_id": installed.id,
                    "installed_version": installed.installed_version,
                    "latest_version": market.version,
                    "has_update": True,
                    "update_url": market.download_url,
                })
    return updates


# ── categories ───────────────────────────────────────────────────────


def list_categories() -> list[PluginCategory]:
    """List all plugin categories with counts."""
    categories = []
    for cat_id in VALID_PLUGIN_CATEGORIES:
        count = sum(1 for p in BUILTIN_PLUGINS if p.category == cat_id)
        name_map = {
            "tts_engine": "TTS Engines",
            "voice_profile": "Voice Profiles",
            "audio_effect": "Audio Effects",
            "workflow_template": "Workflow Templates",
            "sfx_pack": "SFX Packs",
            "live2d_model": "Live2D Models",
            "music_style": "Music Styles",
        }
        categories.append(PluginCategory(
            id=cat_id,
            name=name_map.get(cat_id, cat_id),
            description=f"Browse {name_map.get(cat_id, cat_id).lower()} plugins",
            plugin_count=count,
        ))
    return categories
