"""
Sound Effects (SFX) library service.

Provides a built-in catalog of 50+ categorized free SFX descriptions
and supports importing user-provided local sound effect folders.

SFX files are indexed by category and tag; actual audio files are stored
in data_dir/sfx/ (imported) or referenced from their original locations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import config

SFX_DIR_NAME = "sfx"

# ── built-in catalog (descriptions only — audio must be user-provided) ──

BUILTIN_SFX: list[dict[str, Any]] = [
    # --- ambient ---
    {"id": "ambient_forest", "name": "Forest Ambience", "category": "ambient", "tags": ["nature", "birds", "wind"]},
    {"id": "ambient_rain", "name": "Rain", "category": "ambient", "tags": ["weather", "storm", "drizzle"]},
    {"id": "ambient_thunder", "name": "Thunder", "category": "ambient", "tags": ["weather", "storm", "lightning"]},
    {"id": "ambient_wind", "name": "Wind Howl", "category": "ambient", "tags": ["weather", "cold", "desert"]},
    {"id": "ambient_city", "name": "City Street", "category": "ambient", "tags": ["urban", "traffic", "crowd"]},
    {"id": "ambient_cafe", "name": "Cafe Chatter", "category": "ambient", "tags": ["indoor", "crowd", "drinks"]},
    {"id": "ambient_ocean", "name": "Ocean Waves", "category": "ambient", "tags": ["water", "beach", "nature"]},
    {"id": "ambient_fire", "name": "Campfire", "category": "ambient", "tags": ["fire", "outdoor", "warmth"]},
    {"id": "ambient_night", "name": "Night Crickets", "category": "ambient", "tags": ["night", "insects", "nature"]},
    {"id": "ambient_underground", "name": "Underground Cave", "category": "ambient", "tags": ["drip", "echo", "dark"]},

    # --- actions ---
    {"id": "action_door_open", "name": "Door Open", "category": "actions", "tags": ["door", "wood", "creak"]},
    {"id": "action_door_close", "name": "Door Close", "category": "actions", "tags": ["door", "slam", "wood"]},
    {"id": "action_footsteps", "name": "Footsteps (Walking)", "category": "actions", "tags": ["walk", "floor", "pace"]},
    {"id": "action_footsteps_run", "name": "Footsteps (Running)", "category": "actions", "tags": ["run", "floor", "pace"]},
    {"id": "action_glass_break", "name": "Glass Breaking", "category": "actions", "tags": ["glass", "shatter", "impact"]},
    {"id": "action_page_turn", "name": "Page Turn", "category": "actions", "tags": ["paper", "book", "flip"]},
    {"id": "action_knock", "name": "Knock on Door", "category": "actions", "tags": ["knock", "door", "wood"]},
    {"id": "action_bell", "name": "Doorbell", "category": "actions", "tags": ["bell", "ring", "door"]},
    {"id": "action_typing", "name": "Keyboard Typing", "category": "actions", "tags": ["keyboard", "typing", "office"]},
    {"id": "action_phone_ring", "name": "Phone Ringing", "category": "actions", "tags": ["phone", "ring", "call"]},

    # --- combat ---
    {"id": "combat_sword_clash", "name": "Sword Clash", "category": "combat", "tags": ["metal", "sword", "fight"]},
    {"id": "combat_punch", "name": "Punch", "category": "combat", "tags": ["hit", "impact", "fight"]},
    {"id": "combat_gunshot", "name": "Gunshot", "category": "combat", "tags": ["gun", "shot", "loud"]},
    {"id": "combat_explosion", "name": "Explosion", "category": "combat", "tags": ["boom", "blast", "war"]},
    {"id": "combat_bow", "name": "Bow Release", "category": "combat", "tags": ["arrow", "twang", "bow"]},
    {"id": "combat_shield_hit", "name": "Shield Hit", "category": "combat", "tags": ["shield", "metal", "block"]},

    # --- creatures ---
    {"id": "creature_dog_bark", "name": "Dog Bark", "category": "creatures", "tags": ["dog", "bark", "animal"]},
    {"id": "creature_cat_meow", "name": "Cat Meow", "category": "creatures", "tags": ["cat", "meow", "animal"]},
    {"id": "creature_horse_gallop", "name": "Horse Gallop", "category": "creatures", "tags": ["horse", "hooves", "run"]},
    {"id": "creature_bird_chirp", "name": "Bird Chirping", "category": "creatures", "tags": ["bird", "chirp", "nature"]},
    {"id": "creature_wolf_howl", "name": "Wolf Howl", "category": "creatures", "tags": ["wolf", "howl", "night"]},
    {"id": "creature_dragon_roar", "name": "Dragon Roar", "category": "creatures", "tags": ["dragon", "roar", "fantasy"]},
    {"id": "creature_crow_caw", "name": "Crow Caw", "category": "creatures", "tags": ["crow", "bird", "dark"]},

    # --- fantasy ---
    {"id": "fantasy_magic_cast", "name": "Magic Spell Cast", "category": "fantasy", "tags": ["magic", "spell", "whoosh"]},
    {"id": "fantasy_portal", "name": "Portal Opening", "category": "fantasy", "tags": ["portal", "whoosh", "magic"]},
    {"id": "fantasy_fairy", "name": "Fairy Dust", "category": "fantasy", "tags": ["fairy", "chime", "sparkle"]},
    {"id": "fantasy_potion", "name": "Potion Bubble", "category": "fantasy", "tags": ["potion", "bubble", "liquid"]},

    # --- mechanical ---
    {"id": "mech_engine_start", "name": "Engine Start", "category": "mechanical", "tags": ["engine", "car", "ignition"]},
    {"id": "mech_engine_idle", "name": "Engine Idle", "category": "mechanical", "tags": ["engine", "car", "hum"]},
    {"id": "mech_robot_beep", "name": "Robot Beep", "category": "mechanical", "tags": ["robot", "beep", "sci-fi"]},
    {"id": "mech_gears", "name": "Gears Turning", "category": "mechanical", "tags": ["gears", "metal", "machine"]},
    {"id": "mech_alarm", "name": "Alarm Siren", "category": "mechanical", "tags": ["alarm", "siren", "warning"]},

    # --- water ---
    {"id": "water_splash", "name": "Water Splash", "category": "water", "tags": ["splash", "water", "pool"]},
    {"id": "water_drip", "name": "Water Drip", "category": "water", "tags": ["drip", "water", "echo"]},
    {"id": "water_stream", "name": "Stream / River", "category": "water", "tags": ["river", "stream", "flow"]},
    {"id": "water_underwater", "name": "Underwater", "category": "water", "tags": ["underwater", "submerged", "muffled"]},

    # --- human ---
    {"id": "human_laugh", "name": "Crowd Laughter", "category": "human", "tags": ["laugh", "crowd", "happy"]},
    {"id": "human_gasp", "name": "Gasp / Surprise", "category": "human", "tags": ["gasp", "surprise", "breath"]},
    {"id": "human_whisper", "name": "Whisper Crowd", "category": "human", "tags": ["whisper", "crowd", "murmur"]},
    {"id": "human_applause", "name": "Applause", "category": "human", "tags": ["clap", "applause", "crowd"]},
    {"id": "human_scream", "name": "Scream", "category": "human", "tags": ["scream", "horror", "fear"]},
    {"id": "human_heartbeat", "name": "Heartbeat", "category": "human", "tags": ["heart", "beat", "tension"]},
]


def get_sfx_dir() -> Path:
    d = config.get_data_dir() / SFX_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_sfx_file_path(sfx_id: str) -> Path | None:
    """Look up a built-in SFX by id and return its expected file path."""
    return get_sfx_dir() / f"{sfx_id}.wav"


def list_sfx(
    category: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    """List built-in SFX, optionally filtered by category or name search."""
    results = BUILTIN_SFX
    if category:
        results = [s for s in results if s["category"] == category]
    if search:
        q = search.lower()
        results = [
            s for s in results
            if q in s["name"].lower() or any(q in t for t in s.get("tags", []))
        ]
    return list(results)


def get_sfx_categories() -> list[str]:
    cats = sorted(set(s["category"] for s in BUILTIN_SFX))
    return cats


def import_sfx_folder(source_dir: str) -> dict[str, Any]:
    """Import audio files from a user-provided folder into the SFX library.

    Supported formats: .wav, .mp3, .ogg, .flac, .aiff
    Returns dict with 'imported' (count) and 'skipped' (count).
    """
    from shutil import copy2

    supported = {".wav", ".mp3", ".ogg", ".flac", ".aiff"}
    src = Path(source_dir)
    if not src.is_dir():
        raise ValueError(f"Not a directory: {source_dir}")

    imported = 0
    skipped = 0
    for file in sorted(src.iterdir()):
        if file.suffix.lower() not in supported or not file.is_file():
            skipped += 1
            continue
        dest = get_sfx_dir() / file.name
        copy2(str(file), str(dest))
        imported += 1

    return {"imported": imported, "skipped": skipped, "dest_dir": str(get_sfx_dir())}


def list_user_sfx() -> list[dict[str, Any]]:
    """List user-imported SFX files."""
    sfx_dir = get_sfx_dir()
    results: list[dict[str, Any]] = []
    for f in sorted(sfx_dir.iterdir()):
        if f.is_file():
            results.append({
                "name": f.stem,
                "file_path": str(f),
                "size_bytes": f.stat().st_size,
                "format": f.suffix.lower().lstrip("."),
            })
    return results
