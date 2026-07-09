#!/usr/bin/env python3
"""
Recompute report cards for the already-generated dashboard data.

The full pipeline (``analyze_stats.py``) needs the live Minecraft server files
to run. When those aren't available, this script rebuilds every player's
``report_card`` in place from the fields already present in
``player_stats.json`` using the shared :mod:`report_card` logic, then rewrites
``player_stats.json``, ``player_stats.js`` and the ``report_title`` column of
``player_stats.csv``.

Run:  python reprocess_report_cards.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import report_card

ROOT = Path(__file__).parent
JSON_PATH = ROOT / "player_stats.json"
JS_PATH = ROOT / "player_stats.js"
CSV_PATH = ROOT / "player_stats.csv"


def metrics_from_player(p: dict) -> dict:
    totals = p.get("totals", {}) or {}
    boss = p.get("boss_stats", {}) or {}
    quest = p.get("quest_progress", {}) or {}
    return {
        "name": p.get("name", ""),
        "playtime_hours": p.get("playtime_hours", 0),
        "deaths": p.get("deaths", 0),
        "player_kills": p.get("player_kills", 0),
        "mob_kills": p.get("mob_kills", 0),
        "damage_dealt": p.get("damage_dealt", 0),
        "damage_taken": p.get("damage_taken", 0),
        "distance_km_total": p.get("distance_km_total", 0),
        "distance_km": p.get("distance_km", {}) or {},
        "blocks_mined": totals.get("blocks_mined", 0),
        "blocks_placed": totals.get("blocks_placed", 0),
        "items_crafted": totals.get("items_crafted", 0),
        "items_picked_up": totals.get("items_picked_up", 0),
        "items_used": totals.get("items_used", 0),
        "farming_score": totals.get("farming_score", 0),
        "total_boss_kills": boss.get("total_boss_kills", 0),
        "quest_completion_pct": quest.get("completion_pct", 0.0),
    }


def main() -> int:
    if not JSON_PATH.is_file():
        print(f"Error: {JSON_PATH} not found")
        return 1

    with JSON_PATH.open(encoding="utf-8") as f:
        payload = json.load(f)

    players = payload.get("players", [])
    if not players:
        print("No players found in payload.")
        return 1

    entries = [metrics_from_player(p) for p in players]
    cards = report_card.build_report_cards(entries)

    for player, card in zip(players, cards):
        player["report_card"] = card

    with JSON_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with JS_PATH.open("w", encoding="utf-8") as f:
        f.write("window.PLAYER_STATS = ")
        json.dump(payload, f, indent=2)
        f.write(";\n")

    # Rebuild the CSV summary (kept consistent with build_summary_csv columns).
    rows = sorted(players, key=lambda p: p.get("playtime_hours", 0), reverse=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "name", "uuid", "playtime_hours", "deaths", "mob_kills",
                "player_kills", "damage_dealt", "damage_taken", "blocks_mined",
                "blocks_placed", "walked_km", "sprinted_km", "flown_km",
                "report_title",
            ]
        )
        for p in rows:
            totals = p.get("totals", {}) or {}
            dist = p.get("distance_km", {}) or {}
            writer.writerow(
                [
                    p.get("name", ""),
                    p.get("uuid", ""),
                    p.get("playtime_hours", 0),
                    p.get("deaths", 0),
                    p.get("mob_kills", 0),
                    p.get("player_kills", 0),
                    p.get("damage_dealt", 0),
                    p.get("damage_taken", 0),
                    totals.get("blocks_mined", 0),
                    totals.get("blocks_placed", 0),
                    dist.get("walked", 0),
                    dist.get("sprinted", 0),
                    dist.get("flown", 0),
                    p["report_card"]["title"],
                ]
            )

    # Report the resulting distribution of titles.
    from collections import Counter

    dist_counter = Counter(p["report_card"]["title"] for p in players)
    print(f"Reprocessed {len(players)} players. Title distribution:")
    for title, count in dist_counter.most_common():
        print(f"  {count:>3}  {title}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
