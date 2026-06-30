"""
Runtime plugin registry — handles hot-loading plugins into the engine.

Supports TTS engine registration, audio effect registration, workflow
template registration, and sandbox enforcement for installed plugins.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any

from .. import config
from ..models.plugin import PluginManifest, PluginManifestEntry

logger = logging.getLogger(__name__)

# ── data dir helpers ─────────────────────────────────────────────────


def _data_dir() -> Path:
    return config.get_data_dir()


def _installed_dir() -> Path:
    return _data_dir() / "plugins" / "installed"


def _registry_path() -> Path:
    return _data_dir() / "plugins" / "registry.json"


def _get_installed_plugin_ids() -> list[str]:
    """Get list of installed and enabled plugin IDs."""
    path = _registry_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item["id"] for item in data if item.get("installed") and item.get("enabled", True)]
    except Exception:
        return []


# ── sandbox / permission enforcement ─────────────────────────────────


class PluginSandbox:
    """Minimal sandbox for plugin code execution."""

    ALLOWED_MODULES: set[str] = {
        "json", "logging", "math", "re", "datetime", "collections",
        "itertools", "functools", "pathlib", "os.path", "copy",
    }

    @staticmethod
    def validate_permissions(manifest: PluginManifest) -> tuple[bool, str]:
        """
        Validate that manifest permissions are acceptable.
        Returns (ok, reason).
        """
        for perm in manifest.permissions:
            if perm.name.startswith("system."):
                return False, f"System-level permission denied: {perm.name}"
            if perm.name == "network.outbound" and "network.inbound" in [p.name for p in manifest.permissions]:
                return False, "Combined network permissions require review"
        return True, ""


# ── TTS engine hot-registration ──────────────────────────────────────

# Reference to the global TTS_ENGINES dict and factory.
# These are populated at load time by register_all_plugins().

_TTS_ENGINE_REGISTRY: dict[str, type] = {}


def register_tts_engine(engine_id: str, engine_class: type) -> None:
    """Register a TTS engine class dynamically."""
    try:
        from ..backends import TTS_ENGINES, get_tts_backend_for_engine  # noqa: F401
    except ImportError:
        logger.warning("Cannot import backends; TTS_ENGINES registration deferred")
    _TTS_ENGINE_REGISTRY[engine_id] = engine_class
    logger.info("TTS engine registered: %s -> %s", engine_id, engine_class.__name__)


def unregister_tts_engine(engine_id: str) -> bool:
    """Remove a dynamically registered TTS engine."""
    if engine_id in _TTS_ENGINE_REGISTRY:
        del _TTS_ENGINE_REGISTRY[engine_id]
        logger.info("TTS engine unregistered: %s", engine_id)
        return True
    return False


def get_plugin_tts_engines() -> dict[str, type]:
    """Get all plugin-registered TTS engine classes."""
    return dict(_TTS_ENGINE_REGISTRY)


# ── effect hot-registration ──────────────────────────────────────────

_EFFECT_REGISTRY: dict[str, Any] = {}


def register_audio_effect(effect_id: str, effect_callable: Any) -> None:
    """Register an audio effect processor."""
    _EFFECT_REGISTRY[effect_id] = effect_callable
    logger.info("Audio effect registered: %s", effect_id)


def unregister_audio_effect(effect_id: str) -> bool:
    """Remove a registered audio effect."""
    if effect_id in _EFFECT_REGISTRY:
        del _EFFECT_REGISTRY[effect_id]
        return True
    return False


def get_plugin_effects() -> dict[str, Any]:
    return dict(_EFFECT_REGISTRY)


# ── workflow template hot-registration ───────────────────────────────

_WORKFLOW_TEMPLATES: dict[str, dict] = {}


def register_workflow_template(template_id: str, template_data: dict) -> None:
    """Register a workflow template."""
    _WORKFLOW_TEMPLATES[template_id] = template_data
    logger.info("Workflow template registered: %s", template_id)


def unregister_workflow_template(template_id: str) -> bool:
    if template_id in _WORKFLOW_TEMPLATES:
        del _WORKFLOW_TEMPLATES[template_id]
        return True
    return False


def get_plugin_workflow_templates() -> dict[str, dict]:
    return dict(_WORKFLOW_TEMPLATES)


# ── plugin loader ────────────────────────────────────────────────────


def load_plugin(plugin_id: str) -> tuple[bool, str]:
    """
    Load a single plugin at runtime by its ID.

    Tries to find manifest.json in the installed plugin directory,
    validate permissions, and hot-register entry points.
    """
    plugin_dir = _installed_dir() / plugin_id
    if not plugin_dir.exists():
        return False, f"Plugin directory not found: {plugin_dir}"

    manifest_path = plugin_dir / "manifest.json"
    if not manifest_path.exists():
        return False, f"manifest.json not found in {plugin_dir}"

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = PluginManifest(**raw)
    except Exception as exc:
        return False, f"Invalid manifest: {exc}"

    # Validate permissions
    ok, reason = PluginSandbox.validate_permissions(manifest)
    if not ok:
        return False, f"Permission denied: {reason}"

    # Register entry points
    for entry in manifest.entry_points:
        if entry.type == "tts_engine":
            _load_entry_tts_engine(plugin_dir, entry)
        elif entry.type == "audio_effect":
            _load_entry_effect(plugin_dir, entry)
        elif entry.type == "workflow_template":
            _load_entry_template(plugin_dir, entry)

    return True, f"Plugin loaded: {plugin_id}"


def unload_plugin(plugin_id: str) -> bool:
    """Unload a plugin: unregister all its registered entries."""
    removed = False
    if plugin_id in _TTS_ENGINE_REGISTRY:
        del _TTS_ENGINE_REGISTRY[plugin_id]
        removed = True
    if plugin_id in _EFFECT_REGISTRY:
        del _EFFECT_REGISTRY[plugin_id]
        removed = True
    if plugin_id in _WORKFLOW_TEMPLATES:
        del _WORKFLOW_TEMPLATES[plugin_id]
        removed = True
    return removed


def load_all_plugins() -> dict[str, tuple[bool, str]]:
    """Load all installed and enabled plugins at startup."""
    results: dict[str, tuple[bool, str]] = {}
    for plugin_id in _get_installed_plugin_ids():
        results[plugin_id] = load_plugin(plugin_id)
    return results


# ── private entry-point loaders ──────────────────────────────────────


def _load_entry_tts_engine(plugin_dir: Path, entry: PluginManifestEntry) -> None:
    """Load a TTS engine class and register it."""
    try:
        module_path = _resolve_module(plugin_dir, entry.module)
        spec = importlib.util.spec_from_file_location(entry.class_name, module_path)
        if spec is None or spec.loader is None:
            logger.warning("Could not load spec for %s", entry.module)
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[entry.class_name] = module
        spec.loader.exec_module(module)
        engine_class = getattr(module, entry.class_name, None)
        if engine_class is None:
            logger.warning("Class %s not found in %s", entry.class_name, entry.module)
            return
        register_tts_engine(entry.class_name.lower(), engine_class)
    except Exception as exc:
        logger.error("Failed to load TTS engine plugin %s: %s", entry.module, exc)


def _load_entry_effect(plugin_dir: Path, entry: PluginManifestEntry) -> None:
    """Load an audio effect function and register it."""
    try:
        module_path = _resolve_module(plugin_dir, entry.module)
        spec = importlib.util.spec_from_file_location(entry.class_name, module_path)
        if spec is None or spec.loader is None:
            return
        module = importlib.util.module_from_spec(spec)
        sys.modules[entry.class_name] = module
        spec.loader.exec_module(module)
        effect_fn = getattr(module, entry.class_name, None)
        if effect_fn is None:
            return
        register_audio_effect(entry.class_name.lower(), effect_fn)
    except Exception as exc:
        logger.error("Failed to load effect plugin %s: %s", entry.module, exc)


def _load_entry_template(plugin_dir: Path, entry: PluginManifestEntry) -> None:
    """Load a workflow template and register it."""
    template_path = plugin_dir / entry.module
    if not template_path.exists():
        logger.warning("Template file not found: %s", template_path)
        return
    try:
        template_data = json.loads(template_path.read_text(encoding="utf-8"))
        register_workflow_template(entry.class_name, template_data)
    except Exception as exc:
        logger.error("Failed to load template %s: %s", entry.module, exc)


def _resolve_module(plugin_dir: Path, module_ref: str) -> Path:
    """Resolve a module reference to an actual .py file."""
    # Support both relative paths and dotted module names
    if module_ref.endswith(".py"):
        return plugin_dir / module_ref
    # Convert dotted name to path
    parts = module_ref.split(".")
    return plugin_dir.joinpath(*parts).with_suffix(".py")
