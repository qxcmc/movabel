"""
Text analyzer for audiobook segmentation and character extraction.

Provides:
  - Chapter detection (by heading markers, empty lines, word thresholds)
  - Character name extraction (regex + heuristic)
  - Dialogue attribution (linking quoted speech to characters)
"""

from __future__ import annotations

import re

# ── chapter detection patterns ───────────────────────────────────────

CHAPTER_PATTERNS: list[re.Pattern] = [
    # "Chapter 1", "Chapter One", "第1章", "第一章"
    re.compile(r'^(?:Chapter|CHAPTER)\s+(\d+|[IVXLCDM]+)[\s\.:：\-\u2014]*(.+)?$', re.MULTILINE),
    re.compile(r'^第[一二三四五六七八九十百千0-9]+章[\s\.:：\-\u2014]*(.+)?$', re.MULTILINE),
    # "# Chapter Title" (Markdown)
    re.compile(r'^#\s+(.+)$', re.MULTILINE),
    # "1. Title", "Part 1"
    re.compile(r'^(?:Part|PART|Section|SECTION)\s+(\d+)[\s\.:：\-\u2014]*(.+)?$', re.MULTILINE),
    # Numeric chapter: "1." / "1 Title" at line start
    re.compile(r'^(\d{1,3})[\.\s、]\s*([A-Z\u4e00-\u9fff][^\n]{2,})$', re.MULTILINE),
    # "Volume 1" / "Book 1"
    re.compile(r'^(?:Volume|Book|VOLUME|BOOK)\s+(\d+)[\s\.:：\-\u2014]*(.+)?$', re.MULTILINE),
]

# ── character name patterns ──────────────────────────────────────────

# Capitalized names in dialogue attribution: "John said", "said Mary"
SPEAKER_PATTERNS: list[re.Pattern] = [
    # English: "'...' said John" or "John said '...'"
    re.compile(r'["\u201c\u201d\u2018\u2019].*?["\u201c\u201d\u2018\u2019]\s*(?:said|shouted|whispered|asked|replied|murmured|cried|exclaimed)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'),
    re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|shouted|whispered|asked|replied|murmured|cried|exclaimed)\s*[,.:]?\s*["\u201c\u201d\u2018\u2019]'),
    # Chinese: "名字说/道/喊道"
    re.compile(r'([\u4e00-\u9fff]{2,4})(?:说|道|说道|喊道|低语|问道|回答|大叫|轻声道)[:：,，\s]'),
    # Dash dialogue: "— Name," (Russian/European style)
    re.compile(r'[\u2014\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[,:]'),
]


def detect_chapters(text: str) -> list[dict[str, str | int]]:
    """Detect chapters in long text using multiple pattern strategies.

    Returns a list of dicts with 'title', 'start_pos', 'end_pos' keys.
    """
    if not text.strip():
        return []

    # Strategy 1: Try chapter heading patterns
    chapter_spans: list[dict[str, str | int]] = []
    for pattern in CHAPTER_PATTERNS:
        matches = list(pattern.finditer(text))
        if len(matches) >= 2:  # Must find at least 2 to be credible
            for i, m in enumerate(matches):
                start = m.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                title = m.group(0).strip()
                chapter_spans.append({
                    "title": title[:100],
                    "start_pos": start,
                    "end_pos": end,
                })
            if chapter_spans:
                return chapter_spans

    # Strategy 2: Split by consecutive blank lines (paragraph-break heuristic)
    paragraphs = re.split(r'\n{2,}', text)
    if len(paragraphs) >= 3:
        chapter_spans = []
        pos = 0
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                pos += len(para) + 2
                continue
            start = text.index(para, pos)
            end = start + len(para)
            chapter_spans.append({
                "title": para[:100].split("\n")[0].strip() or f"Chapter {i + 1}",
                "start_pos": start,
                "end_pos": end,
            })
            pos = end
        return chapter_spans

    # Strategy 3: Split every 3000 words (fallback)
    words = text.split()
    if len(words) > 3000:
        chapter_spans = []
        chunk_size = 3000
        pos = 0
        chapter_num = 1
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            start = text.index(chunk, pos) if pos < len(text) else pos
            chapter_spans.append({
                "title": f"Part {chapter_num}",
                "start_pos": start,
                "end_pos": start + len(chunk),
            })
            chapter_num += 1
            pos = start + len(chunk)
        return chapter_spans

    # Single chapter
    return [{"title": "Full Text", "start_pos": 0, "end_pos": len(text)}]


def extract_character_names(text: str) -> list[dict[str, str]]:
    """Extract potential character names from dialogue attribution patterns.

    Returns a list of dicts with 'name' and 'occurrences' keys.
    """
    name_counts: dict[str, int] = {}
    for pattern in SPEAKER_PATTERNS:
        for m in pattern.finditer(text):
            name = m.group(1).strip()
            if name not in ("The", "A", "An", "He", "She", "It", "They", "We", "I", "You"):
                name_counts[name] = name_counts.get(name, 0) + 1

    # Heuristic: exclude common nouns that aren't names
    exclude = {"mother", "father", "uncle", "aunt", "grandmother", "grandfather",
               "sir", "madam", "doctor", "professor", "captain", "sergeant"}
    filtered = {
        n: c for n, c in name_counts.items()
        if n.lower() not in exclude and c >= 2
    }

    sorted_names = sorted(filtered.items(), key=lambda x: -x[1])
    return [
        {"name": name, "occurrences": count}
        for name, count in sorted_names
    ]


def link_dialogue_to_characters(
    segments: list[dict],
    characters: list[dict],
) -> list[dict]:
    """For each segment, try to identify which character is speaking.

    Modifies segments in-place by adding 'character_name' if detected.
    Returns the modified list.
    """
    char_names = {c["name"].lower(): c["name"] for c in characters}
    for seg in segments:
        text = seg.get("text", "")
        if not text:
            continue
        # Check direct attribution at the start
        for name_lower, name_display in char_names.items():
            if text.lower().startswith(name_lower + " said") or \
               text.lower().startswith(name_lower + " "):
                seg["character_name"] = name_display
                break
        # Check quoted dialogue attribution
        for pattern in SPEAKER_PATTERNS:
            m = pattern.search(text)
            if m:
                detected = m.group(1).strip()
                if detected.lower() in char_names:
                    seg["character_name"] = char_names[detected.lower()]
                    break
    return segments


def segment_text(
    text: str,
    strategy: str = "paragraph",
    word_limit: int = 500,
) -> list[dict[str, str]]:
    """Segment text into TTS-ready chunks.

    strategy:
      - "chapter": returns one segment (full text)
      - "paragraph": split by double newlines
      - "sentence": split by sentence-ending punctuation
      - "word_count": split into chunks of ~word_limit words
    """
    segments: list[dict[str, str]] = []
    if strategy == "chapter":
        if text.strip():
            segments.append({"text": text.strip(), "type": "chapter"})
    elif strategy == "paragraph":
        parts = re.split(r'\n{2,}', text)
        for part in parts:
            if part.strip():
                segments.append({"text": part.strip(), "type": "paragraph"})
    elif strategy == "sentence":
        # Split on . ! ? followed by space/newline, keeping delimiter
        sentences = re.split(r'(?<=[.!?。！？])\s+', text)
        buf = ""
        for sent in sentences:
            if not sent.strip():
                continue
            if len(buf.split()) + len(sent.split()) > word_limit and buf:
                segments.append({"text": buf.strip(), "type": "sentence"})
                buf = sent
            else:
                buf = (buf + " " + sent).strip()
        if buf:
            segments.append({"text": buf.strip(), "type": "sentence"})
    elif strategy == "word_count":
        words = text.split()
        for i in range(0, len(words), word_limit):
            chunk = " ".join(words[i:i + word_limit]).strip()
            if chunk:
                segments.append({"text": chunk, "type": "word_count"})
    return segments
