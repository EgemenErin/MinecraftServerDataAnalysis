"""FTB Quests catalog + per-player progress extraction."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from snbt_utils import load_snbt_map_file, strip_mc_formatting

QUEST_ID_RE = re.compile(r'id:\s*"([0-9A-F]{16})"', re.IGNORECASE)
SUBTITLE_RE = re.compile(r'subtitle:\s*"([^"]+)"')
TASK_TITLE_RE = re.compile(r'title:\s*"([^"]+)"')


def load_chapter_groups(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    groups: dict[str, str] = {}
    for match in re.finditer(r'id:\s*"([0-9A-F]{16})"\s*,\s*title:\s*"([^"]+)"', text, re.I):
        groups[match.group(1).upper()] = strip_mc_formatting(match.group(2))
    return groups


def parse_chapter_file(path: Path, chapter_groups: dict[str, str]) -> dict:
    text = path.read_text(encoding="utf-8")
    quests_idx = text.find("quests:")
    header = text[:quests_idx] if quests_idx >= 0 else text
    quest_section = text[quests_idx:] if quests_idx >= 0 else text

    chapter_id_match = re.search(r'id:\s*"([0-9A-F]{16})"', header, re.I)
    title_match = re.search(r'title:\s*"([^"]+)"', header)
    group_match = re.search(r'group:\s*"([0-9A-F]{16})"', header, re.I)

    chapter_id = chapter_id_match.group(1).upper() if chapter_id_match else path.stem.upper()
    title = strip_mc_formatting(title_match.group(1)) if title_match else path.stem
    group_id = group_match.group(1).upper() if group_match else None
    group_title = chapter_groups.get(group_id, "Other") if group_id else "Other"

    quests: dict[str, dict] = {}

    for quest_match in QUEST_ID_RE.finditer(quest_section):
        quest_id = quest_match.group(1).upper()
        if quest_id == chapter_id:
            continue

        chunk_after = quest_section[quest_match.end() : quest_match.end() + 500]
        chunk_before = quest_section[max(0, quest_match.start() - 80) : quest_match.start()]
        if "tasks:" not in chunk_after and "tasks:" not in chunk_before:
            continue

        start = max(0, quest_match.start() - 200)
        end = min(len(quest_section), quest_match.end() + 400)
        chunk = quest_section[start:end]

        subtitle = SUBTITLE_RE.search(chunk)
        task_title = TASK_TITLE_RE.search(chunk)
        name = strip_mc_formatting(
            subtitle.group(1) if subtitle else (task_title.group(1) if task_title else quest_id)
        )

        quests[quest_id] = {
            "id": quest_id,
            "name": name,
            "chapter_id": chapter_id,
            "chapter_title": title,
            "chapter_group": group_title,
            "filename": path.stem,
        }

    return {
        "chapter_id": chapter_id,
        "title": title,
        "group": group_title,
        "filename": path.stem,
        "quests": quests,
    }


def build_quest_catalog(quests_config_dir: Path) -> dict:
    chapters_dir = quests_config_dir / "chapters"
    groups_path = quests_config_dir / "chapter_groups.snbt"
    chapter_groups = load_chapter_groups(groups_path)

    catalog: dict[str, dict] = {}
    chapters: list[dict] = []

    if not chapters_dir.is_dir():
        return {"quests": catalog, "chapters": chapters, "total_quests": 0}

    for path in sorted(chapters_dir.glob("*.snbt")):
        chapter = parse_chapter_file(path, chapter_groups)
        chapters.append(
            {
                "chapter_id": chapter["chapter_id"],
                "title": chapter["title"],
                "group": chapter["group"],
                "filename": chapter["filename"],
                "quest_count": len(chapter["quests"]),
            }
        )
        catalog.update(chapter["quests"])

    return {
        "quests": catalog,
        "chapters": chapters,
        "total_quests": len(catalog),
    }


def ms_to_iso(ms: int) -> str | None:
    if ms <= 0:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
    except (OSError, OverflowError, ValueError):
        return None


def load_player_progress(path: Path) -> dict:
    started = load_snbt_map_file(path, "started")
    completed = load_snbt_map_file(path, "completed")
    return {"started": started, "completed": completed}


def compute_player_quest_progress(
    uuid: str,
    progress: dict,
    catalog: dict,
) -> dict:
    catalog_quests = catalog["quests"]
    completed_ids = set(progress["completed"].keys())
    started_ids = set(progress["started"].keys())

    valid_completed = [qid for qid in completed_ids if qid in catalog_quests]
    total_available = catalog["total_quests"]
    completed_count = len(valid_completed)
    completion_pct = round((completed_count / total_available) * 100, 1) if total_available else 0.0

    chapter_stats: dict[str, dict] = {}
    for qid in valid_completed:
        quest = catalog_quests[qid]
        cid = quest["chapter_id"]
        if cid not in chapter_stats:
            chapter_stats[cid] = {
                "chapter_id": cid,
                "chapter_title": quest["chapter_title"],
                "chapter_group": quest["chapter_group"],
                "completed": 0,
                "total": 0,
                "completion_pct": 0.0,
            }
        chapter_stats[cid]["completed"] += 1

    for quest in catalog_quests.values():
        cid = quest["chapter_id"]
        if cid not in chapter_stats:
            chapter_stats[cid] = {
                "chapter_id": cid,
                "chapter_title": quest["chapter_title"],
                "chapter_group": quest["chapter_group"],
                "completed": 0,
                "total": 0,
                "completion_pct": 0.0,
            }
        chapter_stats[cid]["total"] += 1

    chapters = []
    for stat in chapter_stats.values():
        stat["completion_pct"] = round((stat["completed"] / stat["total"]) * 100, 1) if stat["total"] else 0.0
        chapters.append(stat)
    chapters.sort(key=lambda c: c["completion_pct"], reverse=True)

    quest_times = []
    for qid in valid_completed:
        started_ms = progress["started"].get(qid)
        completed_ms = progress["completed"].get(qid)
        if started_ms and completed_ms and completed_ms >= started_ms:
            quest_times.append(
                {
                    "quest_id": qid,
                    "name": catalog_quests[qid]["name"],
                    "chapter_title": catalog_quests[qid]["chapter_title"],
                    "duration_minutes": round((completed_ms - started_ms) / 60000, 1),
                    "completed_at": ms_to_iso(completed_ms),
                }
            )
    quest_times.sort(key=lambda q: q["duration_minutes"], reverse=True)

    return {
        "uuid": uuid,
        "completed": completed_count,
        "started": len([q for q in started_ids if q in catalog_quests]),
        "total_available": total_available,
        "completion_pct": completion_pct,
        "chapters": chapters,
        "slowest_quests": quest_times[:5],
        "fastest_quests": sorted(quest_times, key=lambda q: q["duration_minutes"])[:5],
        "completed_ids": valid_completed,
    }


def compute_server_quest_stats(all_progress: list[dict], catalog: dict) -> dict:
    completion_counts: dict[str, int] = {qid: 0 for qid in catalog["quests"]}
    player_count = len(all_progress)

    for prog in all_progress:
        for qid in prog["completed_ids"]:
            completion_counts[qid] = completion_counts.get(qid, 0) + 1

    zero_completion = []
    for qid, count in completion_counts.items():
        if count == 0:
            quest = catalog["quests"][qid]
            zero_completion.append(
                {
                    "quest_id": qid,
                    "name": quest["name"],
                    "chapter_title": quest["chapter_title"],
                    "chapter_group": quest["chapter_group"],
                    "completions": 0,
                }
            )

    zero_completion.sort(key=lambda q: (q["chapter_group"], q["chapter_title"], q["name"]))

    rarest = []
    for qid, count in completion_counts.items():
        if count > 0:
            quest = catalog["quests"][qid]
            rarest.append(
                {
                    "quest_id": qid,
                    "name": quest["name"],
                    "chapter_title": quest["chapter_title"],
                    "completions": count,
                    "completion_rate_pct": round((count / player_count) * 100, 1) if player_count else 0,
                }
            )
    rarest.sort(key=lambda q: q["completions"])

    leaderboard = sorted(all_progress, key=lambda p: p["completion_pct"], reverse=True)
    return {
        "player_count": player_count,
        "total_quests_available": catalog["total_quests"],
        "zero_completion_quests": zero_completion[:25],
        "hardest_quests": zero_completion[:15],
        "rarest_completed": rarest[:15],
        "leaderboard": [
            {
                "uuid": p["uuid"],
                "completion_pct": p["completion_pct"],
                "completed": p["completed"],
                "total_available": p["total_available"],
            }
            for p in leaderboard[:15]
        ],
    }


def analyze_quests(quests_config_dir: Path, world_quests_dir: Path, player_uuids: list[str]) -> tuple[dict, dict]:
    catalog = build_quest_catalog(quests_config_dir)
    all_progress: list[dict] = []
    by_uuid: dict[str, dict] = {}

    if world_quests_dir.is_dir():
        for uuid in player_uuids:
            path = world_quests_dir / f"{uuid}.snbt"
            if not path.exists():
                continue
            raw = load_player_progress(path)
            prog = compute_player_quest_progress(uuid, raw, catalog)
            all_progress.append(prog)
            by_uuid[uuid] = {
                "completed": prog["completed"],
                "started": prog["started"],
                "total_available": prog["total_available"],
                "completion_pct": prog["completion_pct"],
                "chapters": prog["chapters"],
                "slowest_quests": prog["slowest_quests"],
                "fastest_quests": prog["fastest_quests"],
            }

    server_stats = compute_server_quest_stats(all_progress, catalog)
    return by_uuid, server_stats
