#!/usr/bin/env python3
"""Parse Minecraft server player stats and export JSON/CSV for the dashboard."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import report_card
from boss_parser import build_player_boss_stats, build_server_boss_stats
from config import AWARDS_CONFIG, BOSS_ENTITY_HINTS, EMBARRASSING_CAUSES
from quest_parser import analyze_quests

TICKS_PER_HOUR = 72000
CM_PER_KM = 100_000

LOG_LINE_RE = re.compile(
    r"^\[[\d:]+\]\s+\[[^\]]+/(?:INFO|WARN|ERROR)\]:\s+(?P<msg>.+)$"
)

DEATH_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^(?P<victim>.+?) was slain by (?P<killer>.+?)(?: using \[.+?\])?$"), "pvp_or_mob"),
    (re.compile(r"^(?P<victim>.+?) was shot by (?P<killer>.+?)(?: using \[.+?\])?$"), "pvp_or_mob"),
    (re.compile(r"^(?P<victim>.+?) was killed by (?P<killer>.+)$"), "pvp_or_mob"),
    (re.compile(r"^(?P<victim>.+?) was blown up by (?P<killer>.+)$"), "explosion"),
    (re.compile(r"^(?P<victim>.+?) was pummeled by (?P<killer>.+)$"), "pvp_or_mob"),
    (re.compile(r"^(?P<victim>.+?) was fireballed by (?P<killer>.+)$"), "pvp_or_mob"),
    (re.compile(r"^(?P<victim>.+?) was stung to death$"), "mob"),
    (re.compile(r"^(?P<victim>.+?) was pricked to death$"), "cactus"),
    (re.compile(r"^(?P<victim>.+?) drowned$"), "drowning"),
    (re.compile(r"^(?P<victim>.+?) experienced kinetic energy$"), "fall"),
    (re.compile(r"^(?P<victim>.+?) hit the ground too hard$"), "fall"),
    (re.compile(r"^(?P<victim>.+?) fell from a high place$"), "fall"),
    (re.compile(r"^(?P<victim>.+?) fell off .+$"), "fall"),
    (re.compile(r"^(?P<victim>.+?) fell while .+$"), "fall"),
    (re.compile(r"^(?P<victim>.+?) was squashed by a falling .+$"), "fall"),
    (re.compile(r"^(?P<victim>.+?) went up in flames$"), "fire"),
    (re.compile(r"^(?P<victim>.+?) burned to death$"), "fire"),
    (re.compile(r"^(?P<victim>.+?) tried to swim in lava$"), "lava"),
    (re.compile(r"^(?P<victim>.+?) went off with a bang$"), "explosion"),
    (re.compile(r"^(?P<victim>.+?) blew up$"), "explosion"),
    (re.compile(r"^(?P<victim>.+?) was blown up$"), "explosion"),
    (re.compile(r"^(?P<victim>.+?) starved to death$"), "starvation"),
    (re.compile(r"^(?P<victim>.+?) suffocated in a wall$"), "suffocation"),
    (re.compile(r"^(?P<victim>.+?) was struck by lightning$"), "lightning"),
    (re.compile(r"^(?P<victim>.+?) froze to death$"), "freeze"),
    (re.compile(r"^(?P<victim>.+?) withered away$"), "wither"),
    (re.compile(r"^(?P<victim>.+?) was killed by magic$"), "magic"),
    (re.compile(r"^(?P<victim>.+?) was impaled by .+$"), "fall"),
    (re.compile(r"^(?P<victim>.+?) walked into .+$"), "other_self_inflicted"),
    (re.compile(r"^(?P<victim>.+?) was killed trying to hurt .+$"), "other_self_inflicted"),
]

UNDERGROUND_BLOCK_HINTS = (
    "stone",
    "deepslate",
    "netherrack",
    "andesite",
    "diorite",
    "granite",
    "tuff",
    "basalt",
    "blackstone",
    "calcite",
    "obsidian",
)

FARMING_HINTS = (
    "wheat",
    "carrot",
    "potato",
    "beetroot",
    "melon",
    "pumpkin",
    "sugar_cane",
    "nether_wart",
    "cocoa",
    "sweet_berry",
    "chorus",
    "bamboo",
    "kelp",
    "torchflower",
    "pitcher",
    "cabbage",
    "tomato",
    "lettuce",
    "rice",
    "hops",
    "grape",
    "strawberr",
    "onion",
)

BLOCK_PLACE_HINTS = (
    "_planks",
    "_log",
    "_wood",
    "_stone",
    "_block",
    "_brick",
    "_slab",
    "_stairs",
    "_wall",
    "_fence",
    "_door",
    "_trapdoor",
    "_button",
    "_pressure_plate",
    "_sign",
    "_leaves",
    "_sapling",
    "_terracotta",
    "_concrete",
    "_wool",
    "_carpet",
    "_glass",
    "_sand",
    "_gravel",
    "_dirt",
    "_grass",
    "_mud",
    "_clay",
    "_ore",
    "_cobble",
    "_deepslate",
    "_netherrack",
    "_obsidian",
    "_torch",
    "_lantern",
    "_bed",
    "_chest",
    "_barrel",
    "_table",
    "_furnace",
    "_rail",
    "_piston",
    "_hopper",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze Minecraft player stats from world/stats JSON files."
    )
    parser.add_argument(
        "--stats-dir",
        type=Path,
        required=True,
        help="Path to world/stats folder (contains <uuid>.json files)",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=None,
        help="Path to server logs folder (default: server-root/logs)",
    )
    parser.add_argument(
        "--server-root",
        type=Path,
        default=None,
        help="Server root containing usercache.json (default: stats-dir/../../)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: directory containing this script)",
    )
    parser.add_argument(
        "--quests-config-dir",
        type=Path,
        default=None,
        help="FTB Quests config folder (default: server-root/config/ftbquests/quests)",
    )
    parser.add_argument(
        "--world-quests-dir",
        type=Path,
        default=None,
        help="Per-player FTB Quests progress (default: server-root/world/ftbquests)",
    )
    return parser.parse_args()


def resolve_server_root(stats_dir: Path, server_root: Path | None) -> Path:
    if server_root is not None:
        return server_root.resolve()
    return stats_dir.resolve().parent.parent


def load_name_map(server_root: Path) -> dict[str, str]:
    cache_path = server_root / "usercache.json"
    names: dict[str, str] = {}
    if not cache_path.exists():
        print(f"Warning: usercache.json not found at {cache_path}", file=sys.stderr)
        return names

    with cache_path.open(encoding="utf-8") as f:
        entries = json.load(f)

    for entry in entries:
        uuid = entry.get("uuid", "").lower()
        name = entry.get("name")
        if uuid and name:
            names[uuid] = name
    return names


def reverse_name_map(name_map: dict[str, str]) -> dict[str, str]:
    return {name.lower(): uuid for uuid, name in name_map.items()}


def pretty_id(raw_id: str) -> str:
    name = raw_id.split(":")[-1]
    return name.replace("_", " ").title()


def top_n(d: dict | None, n: int = 10) -> list[dict]:
    if not d:
        return []
    ranked = sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"id": k, "name": pretty_id(k), "count": int(v)} for k, v in ranked]


def get_int(d: dict | None, key: str, default: int = 0) -> int:
    if not d:
        return default
    return int(d.get(key, default))


def sum_dict(d: dict | None) -> int:
    if not d:
        return 0
    return sum(int(v) for v in d.values())


def cm_to_km(cm: int) -> float:
    return round(cm / CM_PER_KM, 2)


def safe_ratio(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator <= 0:
        return default
    return round(numerator / denominator, 4)


def is_farming_item(item_id: str) -> bool:
    lower = item_id.lower()
    return any(h in lower for h in FARMING_HINTS)


def is_block_place_item(item_id: str) -> bool:
    lower = item_id.lower()
    return any(h in lower for h in BLOCK_PLACE_HINTS)


def is_underground_block(block_id: str) -> bool:
    lower = block_id.lower()
    return any(h in lower for h in UNDERGROUND_BLOCK_HINTS)


def estimate_blocks_placed(used: dict | None, mined: dict | None) -> int:
    if not used:
        return 0
    mined_keys = set(mined or {})
    total = 0
    for item_id, count in used.items():
        if item_id in mined_keys or is_block_place_item(item_id):
            total += int(count)
    return total


def farming_score(stats: dict) -> int:
    score = 0
    for namespace in ("minecraft:mined", "minecraft:used", "minecraft:picked_up", "minecraft:crafted"):
        bucket = stats.get(namespace, {})
        for item_id, count in bucket.items():
            if is_farming_item(item_id):
                score += int(count)
    return score


ORE_WEALTH_HINTS = ("_ore", "raw_", "deepslate_", "ancient_debris", "nether_quartz")


def ore_wealth_score(picked_up: dict | None, mined: dict | None) -> int:
    total = 0
    for bucket in (picked_up, mined):
        if not bucket:
            continue
        for item_id, count in bucket.items():
            lower = item_id.lower()
            if any(h in lower for h in ORE_WEALTH_HINTS):
                total += int(count)
    return total


def underground_ratio(mined: dict | None) -> float:
    if not mined:
        return 0.0
    total = sum(int(v) for v in mined.values())
    if total <= 0:
        return 0.0
    underground = sum(int(v) for k, v in mined.items() if is_underground_block(k))
    return round(underground / total, 4)


def iter_log_lines(logs_dir: Path):
    if not logs_dir.is_dir():
        return

    candidates: list[Path] = []
    latest = logs_dir / "latest.log"
    if latest.exists():
        candidates.append(latest)

    for path in sorted(logs_dir.glob("*.log.gz")):
        candidates.append(path)

    for path in sorted(logs_dir.glob("*.log")):
        if path.name == "latest.log":
            continue
        if "kubejs" in path.parts:
            continue
        candidates.append(path)

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            if path.suffix == ".gz":
                with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
                    yield from f
            else:
                with path.open(encoding="utf-8", errors="replace") as f:
                    yield from f
        except OSError as exc:
            print(f"Warning: could not read log {path}: {exc}", file=sys.stderr)


def parse_death_line(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None

    match = LOG_LINE_RE.match(line)
    message = match.group("msg") if match else line

    for pattern, category in DEATH_PATTERNS:
        death_match = pattern.match(message)
        if not death_match:
            continue

        groups = death_match.groupdict()
        victim = groups.get("victim", "").strip()
        killer = groups.get("killer", "").strip() if "killer" in groups else None
        if killer:
            killer = re.sub(r"\s+using\s+\[.+?\]$", "", killer).strip()

        cause = category
        if category == "pvp_or_mob" and killer:
            cause = "pvp" if killer[0].isupper() else "mob"

        return {
            "victim": victim,
            "killer": killer,
            "cause": cause,
            "message": message,
            "embarrassing": cause in EMBARRASSING_CAUSES,
        }
    return None


def parse_logs(logs_dir: Path | None) -> list[dict]:
    deaths: list[dict] = []
    if logs_dir is None:
        return deaths

    for line in iter_log_lines(logs_dir):
        parsed = parse_death_line(line)
        if parsed:
            deaths.append(parsed)
    return deaths


def nemesis_from_stats(killed_by: dict | None) -> dict | None:
    if not killed_by:
        return None
    top_id, count = max(killed_by.items(), key=lambda kv: kv[1])
    return {
        "id": top_id,
        "name": pretty_id(top_id),
        "count": int(count),
    }


def build_death_profiles(
    players: list[dict],
    log_deaths: list[dict],
    name_to_uuid: dict[str, str],
) -> tuple[dict, list[dict]]:
    by_player: dict[str, list[dict]] = defaultdict(list)
    for death in log_deaths:
        uuid = name_to_uuid.get(death["victim"].lower())
        if uuid:
            by_player[uuid].append(death)

    cause_counter: Counter[str] = Counter()
    embarrassing: list[dict] = []

    for player in players:
        uuid = player["uuid"]
        player_logs = by_player.get(uuid, [])

        log_causes: Counter[str] = Counter()
        for entry in player_logs:
            cause_label = entry["killer"] if entry.get("killer") else entry["cause"]
            log_causes[cause_label] += 1
            cause_counter[cause_label] += 1
            if entry["embarrassing"]:
                embarrassing.append(
                    {
                        "player": player["name"],
                        "uuid": uuid,
                        "message": entry["message"],
                        "cause": entry["cause"],
                    }
                )

        stat_nemesis = nemesis_from_stats(player.get("_killed_by"))
        log_nemesis = None
        if log_causes:
            name, count = log_causes.most_common(1)[0]
            log_nemesis = {"name": name, "count": count}

        nemesis = log_nemesis or (
            {"name": stat_nemesis["name"], "count": stat_nemesis["count"]}
            if stat_nemesis
            else None
        )

        recent = player_logs[-1] if player_logs else None
        causes = [
            {"cause": cause, "count": count}
            for cause, count in log_causes.most_common(8)
        ]

        player["death_profile"] = {
            "total_deaths": player["deaths"],
            "log_deaths_parsed": len(player_logs),
            "nemesis": nemesis,
            "most_recent": recent,
            "causes": causes,
        }

    embarrassing.sort(key=lambda x: (x["cause"], x["player"]))
    return cause_counter, embarrassing


def normalize_radar(raw_scores: dict[str, float], server_max: dict[str, float]) -> dict[str, int]:
    result: dict[str, int] = {}
    for axis, value in raw_scores.items():
        ceiling = server_max.get(axis, 0)
        if ceiling <= 0:
            result[axis] = 0
        else:
            result[axis] = min(100, round((value / ceiling) * 100))
    return result


def compute_awards(players: list[dict]) -> list[dict]:
    awards: list[dict] = []
    for spec in AWARDS_CONFIG:
        stat = spec["stat"]
        direction = spec["direction"]

        eligible = [p for p in players if p["_metrics"].get(stat) is not None]
        if not eligible:
            continue

        reverse = direction == "max"
        winner = sorted(
            eligible,
            key=lambda p: p["_metrics"].get(stat, 0),
            reverse=reverse,
        )[0]
        value = winner["_metrics"][stat]

        if stat == "underground_ratio":
            formatted = f"{value * 100:.1f}%"
        elif stat == "quest_completion_pct":
            formatted = f"{value:.1f}%"
        elif isinstance(value, float):
            formatted = f"{value:,.2f}"
        else:
            formatted = f"{int(value):,}"

        awards.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "stat": stat,
                "direction": direction,
                "winner": winner["name"],
                "winner_uuid": winner["uuid"],
                "value": value,
                "formatted_value": formatted,
            }
        )
    return awards


def parse_player_stats(uuid: str, name: str, raw: dict) -> dict:
    stats = raw.get("stats", {})
    custom = stats.get("minecraft:custom", {})
    mined = stats.get("minecraft:mined", {})
    killed = stats.get("minecraft:killed", {})
    crafted = stats.get("minecraft:crafted", {})
    used = stats.get("minecraft:used", {})
    picked_up = stats.get("minecraft:picked_up", {})
    killed_by = stats.get("minecraft:killed_by", {})

    playtime_ticks = get_int(custom, "minecraft:play_time")
    total_mob_kills = get_int(custom, "minecraft:mob_kills")
    if total_mob_kills == 0 and killed:
        total_mob_kills = sum(int(v) for v in killed.values())

    walked_km = cm_to_km(get_int(custom, "minecraft:walk_one_cm"))
    sprinted_km = cm_to_km(get_int(custom, "minecraft:sprint_one_cm"))
    flown_km = cm_to_km(get_int(custom, "minecraft:fly_one_cm"))
    distance_total = round(walked_km + sprinted_km + flown_km, 2)

    blocks_mined = sum(int(v) for v in mined.values()) if mined else 0
    blocks_placed = estimate_blocks_placed(used, mined)
    items_crafted = sum_dict(crafted)
    items_picked_up = sum_dict(picked_up)
    items_used = sum_dict(used)
    deaths = get_int(custom, "minecraft:deaths")
    damage_dealt = get_int(custom, "minecraft:damage_dealt")
    damage_taken = get_int(custom, "minecraft:damage_taken")
    player_kills = get_int(custom, "minecraft:player_kills")
    farm_score = farming_score(stats)
    under_ratio = underground_ratio(mined)
    ore_rich = ore_wealth_score(picked_up, mined)

    metrics = {
        "playtime_hours": round(playtime_ticks / TICKS_PER_HOUR, 2),
        "blocks_mined": blocks_mined,
        "blocks_placed": blocks_placed,
        "items_crafted": items_crafted,
        "items_picked_up": items_picked_up,
        "items_used": items_used,
        "distance_km_total": distance_total,
        "distance_km": {
            "walked": walked_km,
            "sprinted": sprinted_km,
            "flown": flown_km,
        },
        "mob_kills": total_mob_kills,
        "player_kills": player_kills,
        "damage_dealt": damage_dealt,
        "damage_taken": damage_taken,
        "deaths": deaths,
        "farming_score": farm_score,
        "underground_ratio": under_ratio,
        "damage_taken_per_kill": safe_ratio(damage_taken, max(total_mob_kills, 1)),
        "hoarder_ratio": safe_ratio(items_picked_up, max(items_used + items_crafted, 1)),
        "ore_wealth": ore_rich,
        "emeralds_picked_up": get_int(picked_up, "minecraft:emerald"),
        "diamonds_picked_up": get_int(picked_up, "minecraft:diamond"),
        "chests_looted": get_int(custom, "lootr:looted_stat"),
        "slept_in_bed": get_int(custom, "minecraft:sleep_in_bed"),
        "villager_talks": get_int(custom, "minecraft:talked_to_villager"),
        "sprint_km": sprinted_km,
        "quest_completion_pct": 0.0,
        "total_boss_kills": 0,
    }

    player = {
        "uuid": uuid,
        "name": name,
        "playtime_hours": metrics["playtime_hours"],
        "playtime_ticks": playtime_ticks,
        "deaths": deaths,
        "player_kills": player_kills,
        "mob_kills": total_mob_kills,
        "damage_dealt": damage_dealt,
        "damage_taken": damage_taken,
        "distance_km": metrics["distance_km"],
        "distance_km_total": distance_total,
        "totals": {
            "blocks_mined": blocks_mined,
            "blocks_placed": blocks_placed,
            "items_crafted": items_crafted,
            "items_picked_up": items_picked_up,
            "items_used": items_used,
            "farming_score": farm_score,
            "underground_ratio": under_ratio,
        },
        "top_blocks_mined": top_n(mined),
        "top_mobs_killed": top_n(killed),
        "top_items_crafted": top_n(crafted),
        "total_blocks_mined": blocks_mined,
        "_killed_by": killed_by,
        "_killed": killed,
        "_metrics": metrics,
    }
    return player


def finalize_players(players: list[dict]) -> dict[str, int]:
    radar_axes = ("combat", "exploration", "building", "farming", "crafting")
    raw_by_player: dict[str, dict[str, float]] = {}
    server_max: dict[str, float] = {axis: 0.0 for axis in radar_axes}

    for player in players:
        m = player["_metrics"]
        raw = {
            "combat": m["mob_kills"] + m["damage_dealt"] / 1000 + m["player_kills"] * 10,
            "exploration": m["distance_km_total"],
            "building": m["blocks_placed"],
            "farming": m["farming_score"],
            "crafting": m["items_crafted"],
        }
        raw_by_player[player["uuid"]] = raw
        for axis, value in raw.items():
            server_max[axis] = max(server_max[axis], value)

    server_average: dict[str, int] = {}
    for axis in radar_axes:
        values = [raw_by_player[p["uuid"]][axis] for p in players]
        avg = sum(values) / len(values) if values else 0
        ceiling = server_max[axis] or 1
        server_average[axis] = min(100, round((avg / ceiling) * 100))

    report_entries = [{"name": p["name"], **p["_metrics"]} for p in players]
    report_cards = report_card.build_report_cards(report_entries)

    for player, card in zip(players, report_cards):
        player["report_card"] = card
        player["playstyle_radar"] = normalize_radar(
            raw_by_player[player["uuid"]], server_max
        )
        player.pop("_killed_by", None)
        player.pop("_killed", None)
        player.pop("_metrics", None)

    return server_average


def build_summary_csv(players: list[dict]) -> pd.DataFrame:
    rows = []
    for p in players:
        rows.append(
            {
                "name": p["name"],
                "uuid": p["uuid"],
                "playtime_hours": p["playtime_hours"],
                "deaths": p["deaths"],
                "mob_kills": p["mob_kills"],
                "player_kills": p["player_kills"],
                "damage_dealt": p["damage_dealt"],
                "damage_taken": p["damage_taken"],
                "blocks_mined": p["total_blocks_mined"],
                "blocks_placed": p["totals"]["blocks_placed"],
                "walked_km": p["distance_km"]["walked"],
                "sprinted_km": p["distance_km"]["sprinted"],
                "flown_km": p["distance_km"]["flown"],
                "report_title": p["report_card"]["title"],
            }
        )
    return pd.DataFrame(rows).sort_values("playtime_hours", ascending=False)


def main() -> int:
    args = parse_args()
    stats_dir = args.stats_dir.resolve()
    output_dir = (args.output_dir or Path(__file__).parent).resolve()
    server_root = resolve_server_root(stats_dir, args.server_root)
    logs_dir = (args.logs_dir or server_root / "logs").resolve()
    quests_config_dir = (args.quests_config_dir or server_root / "config" / "ftbquests" / "quests").resolve()
    world_quests_dir = (args.world_quests_dir or server_root / "world" / "ftbquests").resolve()
    advancements_dir = server_root / "world" / "advancements"

    if not stats_dir.is_dir():
        print(f"Error: stats directory not found: {stats_dir}", file=sys.stderr)
        return 1

    name_map = load_name_map(server_root)
    name_to_uuid = reverse_name_map(name_map)
    players: list[dict] = []

    stat_files = sorted(stats_dir.glob("*.json"))
    if not stat_files:
        print(f"Warning: no JSON files in {stats_dir}", file=sys.stderr)

    for path in stat_files:
        uuid = path.stem.lower()
        name = name_map.get(uuid, uuid)

        try:
            with path.open(encoding="utf-8") as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"Warning: skipping {path.name}: {exc}", file=sys.stderr)
            continue

        players.append(parse_player_stats(uuid, name, raw))

    players.sort(key=lambda p: p["playtime_hours"], reverse=True)
    player_uuids = [p["uuid"] for p in players]

    quest_by_uuid, server_quest_stats = analyze_quests(
        quests_config_dir, world_quests_dir, player_uuids
    )

    boss_rows: list[dict] = []
    for player in players:
        uuid = player["uuid"]
        if uuid in quest_by_uuid:
            qp = quest_by_uuid[uuid]
            player["quest_progress"] = qp
            player["_metrics"]["quest_completion_pct"] = qp["completion_pct"]

        adv_path = advancements_dir / f"{uuid}.json"
        boss_stats = build_player_boss_stats(
            uuid, player.get("_killed"), adv_path, BOSS_ENTITY_HINTS
        )
        player["boss_stats"] = boss_stats
        player["_metrics"]["total_boss_kills"] = boss_stats["total_boss_kills"]
        boss_rows.append(
            {
                "uuid": uuid,
                "name": player["name"],
                **boss_stats,
            }
        )

    server_boss_stats = build_server_boss_stats(boss_rows)
    for entry in server_quest_stats.get("leaderboard", []):
        entry["name"] = name_map.get(entry["uuid"], entry["uuid"])
    for player in players:
        if "quest_progress" not in player:
            player["quest_progress"] = {
                "completed": 0,
                "started": 0,
                "total_available": server_quest_stats.get("total_quests_available", 0),
                "completion_pct": 0.0,
                "chapters": [],
                "slowest_quests": [],
                "fastest_quests": [],
            }

    log_deaths = parse_logs(logs_dir if logs_dir.is_dir() else None)
    cause_counter, embarrassing = build_death_profiles(players, log_deaths, name_to_uuid)
    awards = compute_awards(players)
    radar_average = finalize_players(players)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats_dir": str(stats_dir),
        "logs_dir": str(logs_dir) if logs_dir.is_dir() else None,
        "quests_config_dir": str(quests_config_dir),
        "world_quests_dir": str(world_quests_dir),
        "player_count": len(players),
        "quest_stats": server_quest_stats,
        "server_wide_boss_stats": server_boss_stats,
        "players": players,
        "death_stats": {
            "log_deaths_parsed": len(log_deaths),
            "cause_leaderboard": [
                {"cause": cause, "count": count}
                for cause, count in cause_counter.most_common(15)
            ],
            "most_deaths": [
                {
                    "name": p["name"],
                    "uuid": p["uuid"],
                    "deaths": p["deaths"],
                }
                for p in sorted(players, key=lambda x: x["deaths"], reverse=True)[:10]
            ],
            "embarrassing_deaths": embarrassing[:20],
        },
        "awards": awards,
        "radar_server_average": radar_average,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "player_stats.json"
    js_path = output_dir / "player_stats.js"
    csv_path = output_dir / "player_stats.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with js_path.open("w", encoding="utf-8") as f:
        f.write("window.PLAYER_STATS = ")
        json.dump(payload, f, indent=2)
        f.write(";\n")

    df = build_summary_csv(players)
    df.to_csv(csv_path, index=False)

    print(f"Processed {len(players)} players")
    print(f"  Quests catalogued: {server_quest_stats.get('total_quests_available', 0)}")
    print(f"  Log deaths parsed: {len(log_deaths)}")
    print(f"  JSON: {json_path}")
    print(f"  JS:   {js_path}")
    print(f"  CSV:  {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
