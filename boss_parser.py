"""Boss encounter stats from player stats + advancements."""

from __future__ import annotations

import json
import re
from pathlib import Path

def pretty_id(raw_id: str) -> str:
    name = raw_id.split(":")[-1]
    return name.replace("_", " ").title()


# Fallback if not overridden in config
DEFAULT_BOSS_HINTS = (
    "wither",
    "ender_dragon",
    "elder_guardian",
    "warden",
    "ravager",
    "inquisitor",
    "necromancer",
    "archivist",
    "provoker",
    "basher",
    "captain",
    "cornelia",
    "maw",
    "illusioner",
    "evoker",
    "pillager",
)


def is_boss_entity(entity_id: str, hints: tuple[str, ...]) -> bool:
    lower = entity_id.lower()
    return any(h in lower for h in hints)


def extract_boss_kills(killed: dict | None, hints: tuple[str, ...]) -> list[dict]:
    if not killed:
        return []
    bosses = []
    for entity_id, count in killed.items():
        if is_boss_entity(entity_id, hints):
            bosses.append(
                {
                    "id": entity_id,
                    "name": pretty_id(entity_id),
                    "kills": int(count),
                }
            )
    bosses.sort(key=lambda b: b["kills"], reverse=True)
    return bosses


def load_advancement_bosses(path: Path, namespace: str = "souls_like_bosses") -> list[dict]:
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []

    bosses = []
    prefix = f"{namespace}:"
    for adv_id, entry in data.items():
        if not adv_id.startswith(prefix) or adv_id.endswith(":root"):
            continue
        if entry.get("done"):
            criteria = entry.get("criteria", {})
            completed_at = next(iter(criteria.values()), None) if criteria else None
            bosses.append(
                {
                    "id": adv_id,
                    "name": pretty_id(adv_id.split(":")[-1]),
                    "completed_at": completed_at,
                }
            )
    return bosses


def build_player_boss_stats(
    uuid: str,
    killed: dict | None,
    advancements_path: Path | None,
    hints: tuple[str, ...],
) -> dict:
    boss_kills = extract_boss_kills(killed, hints)
    adv_bosses = load_advancement_bosses(advancements_path) if advancements_path else []
    total_kills = sum(b["kills"] for b in boss_kills)

    return {
        "total_boss_kills": total_kills,
        "boss_kills": boss_kills,
        "advancement_bosses": adv_bosses,
        "souls_like_bosses_mod": {
            "advancements_found": len(adv_bosses),
            "note": "Only advancement milestones found; no dedicated mod save files on disk.",
        },
    }


def build_server_boss_stats(all_boss_stats: list[dict]) -> dict:
    kill_totals: dict[str, dict] = {}
    adv_totals: dict[str, int] = {}

    for player in all_boss_stats:
        for boss in player.get("boss_kills", []):
            bid = boss["id"]
            if bid not in kill_totals:
                kill_totals[bid] = {"id": bid, "name": boss["name"], "total_kills": 0, "players": 0}
            kill_totals[bid]["total_kills"] += boss["kills"]
            kill_totals[bid]["players"] += 1

        for adv in player.get("advancement_bosses", []):
            adv_totals[adv["id"]] = adv_totals.get(adv["id"], 0) + 1

    top_bosses = sorted(kill_totals.values(), key=lambda b: b["total_kills"], reverse=True)
    top_boss_hunters = sorted(all_boss_stats, key=lambda p: p["total_boss_kills"], reverse=True)

    return {
        "top_bosses_by_kills": top_bosses[:15],
        "top_boss_hunters": [
            {
                "name": p["name"],
                "uuid": p["uuid"],
                "total_boss_kills": p["total_boss_kills"],
            }
            for p in top_boss_hunters[:10]
            if p.get("total_boss_kills", 0) > 0
        ],
        "souls_like_advancements": [
            {"id": adv_id, "name": pretty_id(adv_id.split(":")[-1]), "players": count}
            for adv_id, count in sorted(adv_totals.items(), key=lambda x: x[1], reverse=True)
        ],
        "data_sources": [
            "minecraft:killed stats (boss-like entity filter)",
            "world/advancements/<uuid>.json (souls_like_bosses:* milestones)",
        ],
    }
