"""
Podcast template presets.

Provides 5 built-in podcast templates: Interview, News, Story, Education, Business.
Each contains archetypes, segment hints, and default settings.
"""

from __future__ import annotations

from ..models.podcast import PodcastTemplate

PRESETS: dict[str, PodcastTemplate] = {}


def _build():
    global PRESETS

    PRESETS["interview"] = PodcastTemplate(
        id="tpl_interview",
        name="Interview",
        description="Classic host-guest interview format with intro, Q&A rounds, and outro.",
        category="interview",
        intro_text="Welcome to the show. Today we have a very special guest with us. "
        "Let's dive right in.",
        intro_duration_sec=15.0,
        outro_text="That's all the time we have for today. Thank you for tuning in, "
        "and we'll see you next time.",
        outro_duration_sec=10.0,
        speaker_archetypes=[
            {"role": "host", "name": "Host"},
            {"role": "guest", "name": "Guest"},
        ],
        segment_hints=[
            {"name": "Guest Introduction", "type": "monologue", "speaker": "host"},
            {"name": "Opening Question", "type": "dialogue", "speaker": "host"},
            {"name": "First Answer", "type": "monologue", "speaker": "guest"},
            {"name": "Follow-up Discussion", "type": "dialogue"},
            {"name": "Closing Remarks", "type": "monologue", "speaker": "host"},
        ],
    )

    PRESETS["news"] = PodcastTemplate(
        id="tpl_news",
        name="News Briefing",
        description="Structured news format with headlines, body, and wrap-up.",
        category="news",
        intro_text="Good morning. Here are today's top stories.",
        intro_duration_sec=8.0,
        outro_text="That's the news for today. Stay informed, and we'll be back tomorrow.",
        outro_duration_sec=8.0,
        speaker_archetypes=[
            {"role": "anchor", "name": "Anchor"},
            {"role": "correspondent", "name": "Correspondent"},
        ],
        segment_hints=[
            {"name": "Headlines", "type": "monologue", "speaker": "anchor"},
            {"name": "Story 1", "type": "monologue", "speaker": "correspondent"},
            {"name": "Story 2", "type": "monologue", "speaker": "anchor"},
            {"name": "Story 3", "type": "monologue", "speaker": "correspondent"},
            {"name": "Wrap-up", "type": "monologue", "speaker": "anchor"},
        ],
    )

    PRESETS["story"] = PodcastTemplate(
        id="tpl_story",
        name="Storytelling",
        description="Narrative storytelling format with atmosphere and pacing cues.",
        category="story",
        intro_text="I want to tell you a story.",
        intro_duration_sec=5.0,
        outro_text="And that's the story. Some are true, some are not — but they all "
        "have something to teach us.",
        outro_duration_sec=12.0,
        speaker_archetypes=[
            {"role": "narrator", "name": "Narrator"},
            {"role": "voice_actor", "name": "Voice Actor"},
        ],
        segment_hints=[
            {"name": "Opening Hook", "type": "monologue", "speaker": "narrator"},
            {"name": "Scene Setting", "type": "monologue", "speaker": "narrator"},
            {"name": "Character Dialogue", "type": "dialogue"},
            {"name": "Climax", "type": "monologue", "speaker": "narrator"},
            {"name": "Resolution", "type": "monologue", "speaker": "narrator"},
        ],
    )

    PRESETS["education"] = PodcastTemplate(
        id="tpl_education",
        name="Educational",
        description="Lesson format with learning objectives, content, and summary.",
        category="education",
        intro_text="Welcome to today's lesson. By the end, you'll understand how this works.",
        intro_duration_sec=10.0,
        outro_text="That covers today's topic. Review the key points and join us next time "
        "for another lesson.",
        outro_duration_sec=10.0,
        speaker_archetypes=[
            {"role": "instructor", "name": "Instructor"},
            {"role": "co_host", "name": "Co-Host"},
        ],
        segment_hints=[
            {"name": "Learning Objectives", "type": "monologue", "speaker": "instructor"},
            {"name": "Core Concept", "type": "monologue", "speaker": "instructor"},
            {"name": "Hands-on Example", "type": "dialogue"},
            {"name": "Common Pitfalls", "type": "monologue", "speaker": "instructor"},
            {"name": "Key Takeaways", "type": "monologue", "speaker": "co_host"},
        ],
    )

    PRESETS["business"] = PodcastTemplate(
        id="tpl_business",
        name="Business/Case Study",
        description="Professional format for business insights and case study analysis.",
        category="business",
        intro_text="Welcome to the show. Today we're breaking down an important business "
        "case study.",
        intro_duration_sec=12.0,
        outro_text="That wraps up today's analysis. Subscribe for more business insights "
        "every week.",
        outro_duration_sec=10.0,
        speaker_archetypes=[
            {"role": "host", "name": "Host"},
            {"role": "analyst", "name": "Analyst"},
        ],
        segment_hints=[
            {"name": "Context & Background", "type": "monologue", "speaker": "host"},
            {"name": "The Problem", "type": "monologue", "speaker": "analyst"},
            {"name": "Solution Discussion", "type": "dialogue"},
            {"name": "Results & Takeaways", "type": "monologue", "speaker": "analyst"},
            {"name": "Closing Insights", "type": "dialogue"},
        ],
    )


_build()


def get_all_templates() -> list[PodcastTemplate]:
    return list(PRESETS.values())


def get_template(template_id: str) -> PodcastTemplate | None:
    return PRESETS.get(template_id)


def get_template_by_name(name: str) -> PodcastTemplate | None:
    name_lower = name.lower()
    for tpl in PRESETS.values():
        if tpl.name.lower() == name_lower:
            return tpl
    return None


def list_template_choices() -> list[dict[str, str]]:
    return [
        {"id": tpl.id, "name": tpl.name, "description": tpl.description}
        for tpl in PRESETS.values()
    ]
