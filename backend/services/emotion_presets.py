"""
Emotion preset library for commercial/ad voice-over.

Each preset maps human-readable emotion names to concrete DSP parameters:
pitch_shift, speed_multiplier, energy, pause_pattern, and optional effects.
"""

from __future__ import annotations

from ..models.commercial import EmotionPreset

PRESETS: dict[str, EmotionPreset] = {}


def _build():
    global PRESETS

    PRESETS["passionate"] = EmotionPreset(
        id="passionate",
        name="激昂",
        description="High energy, fast pace, elevated pitch.",
        category="激昂",
        pitch_shift=2.0,
        speed_multiplier=1.15,
        energy=0.9,
        pause_pattern="short",
        effects=[{"type": "compressor", "threshold_db": -18.0, "ratio": 3.0}],
    )
    PRESETS["heroic"] = EmotionPreset(
        id="heroic",
        name="英雄气概",
        description="Bold and confident with slight reverb.",
        category="激昂",
        pitch_shift=1.0,
        speed_multiplier=1.05,
        energy=0.85,
        pause_pattern="dramatic",
        effects=[{"type": "reverb", "room_size": 0.3, "damping": 0.5, "wet_level": 0.15}],
    )
    PRESETS["warm"] = EmotionPreset(
        id="warm",
        name="温情",
        description="Soft, warm delivery with gentle pace.",
        category="温情",
        pitch_shift=0.0,
        speed_multiplier=0.9,
        energy=0.4,
        pause_pattern="normal",
        effects=[{"type": "lowpass", "cutoff_hz": 8000}],
    )
    PRESETS["gentle"] = EmotionPreset(
        id="gentle",
        name="轻柔",
        description="Whisper-soft, minimal energy.",
        category="温情",
        pitch_shift=-1.0,
        speed_multiplier=0.85,
        energy=0.25,
        pause_pattern="normal",
        effects=[{"type": "lowpass", "cutoff_hz": 6000}, {"type": "gain", "db": -3.0}],
    )
    PRESETS["urgent"] = EmotionPreset(
        id="urgent",
        name="紧迫",
        description="Fast, clipped delivery for urgency.",
        category="紧迫",
        pitch_shift=1.0,
        speed_multiplier=1.3,
        energy=0.95,
        pause_pattern="short",
        effects=[{"type": "compressor", "threshold_db": -14.0, "ratio": 4.0}],
    )
    PRESETS["intense"] = EmotionPreset(
        id="intense",
        name="激烈",
        description="Maximum intensity with high compression.",
        category="紧迫",
        pitch_shift=3.0,
        speed_multiplier=1.4,
        energy=1.0,
        pause_pattern="short",
        effects=[
            {"type": "compressor", "threshold_db": -12.0, "ratio": 5.0},
            {"type": "gain", "db": 2.0},
        ],
    )
    PRESETS["casual"] = EmotionPreset(
        id="casual",
        name="轻松",
        description="Natural, conversational tone.",
        category="轻松",
        pitch_shift=0.0,
        speed_multiplier=1.0,
        energy=0.5,
        pause_pattern="normal",
        effects=[],
    )
    PRESETS["playful"] = EmotionPreset(
        id="playful",
        name="俏皮",
        description="Lively and playful with slight pitch variation.",
        category="轻松",
        pitch_shift=1.5,
        speed_multiplier=1.1,
        energy=0.65,
        pause_pattern="short",
        effects=[],
    )
    PRESETS["grand"] = EmotionPreset(
        id="grand",
        name="大气",
        description="Cinematic, authoritative delivery with deep reverb.",
        category="大气",
        pitch_shift=-0.5,
        speed_multiplier=0.95,
        energy=0.8,
        pause_pattern="dramatic",
        effects=[
            {"type": "reverb", "room_size": 0.5, "damping": 0.4, "wet_level": 0.25},
            {"type": "compressor", "threshold_db": -18.0, "ratio": 2.5},
        ],
    )
    PRESETS["authoritative"] = EmotionPreset(
        id="authoritative",
        name="权威",
        description="Deep, measured voice with authority.",
        category="大气",
        pitch_shift=-1.5,
        speed_multiplier=0.9,
        energy=0.7,
        pause_pattern="dramatic",
        effects=[
            {"type": "gain", "db": 1.0},
            {"type": "compressor", "threshold_db": -16.0, "ratio": 3.0},
        ],
    )


_build()


def get_all_presets() -> list[EmotionPreset]:
    return list(PRESETS.values())


def get_preset(preset_id: str) -> EmotionPreset | None:
    return PRESETS.get(preset_id)


def get_presets_by_category(category: str) -> list[EmotionPreset]:
    return [p for p in PRESETS.values() if p.category == category]


def get_preset_choices() -> list[dict[str, str]]:
    return [
        {
            "id": p.id,
            "name": p.name,
            "category": p.category,
            "description": p.description,
        }
        for p in PRESETS.values()
    ]
