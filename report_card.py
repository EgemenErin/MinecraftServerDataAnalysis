"""
Population-relative report cards.

The old logic picked a player's title from whichever raw axis score was biggest.
Because ``blocks_mined`` is routinely in the 100k+ range while every other axis
sits in the hundreds, mining won for almost everyone and the whole server ended
up as "Devout of the Church of Tonton".

This module instead ranks every player against the rest of the server on each
axis and assigns the title for the axis where they stand out the most. That
spreads archetypes across the roster and lets us surface genuinely interesting,
comparative stats ("#2 of 31 in PvP", "top 6% for boss kills", etc.).

Stdlib only, so it can be reused both by ``analyze_stats.py`` (live server run)
and by the offline ``reprocess_report_cards.py`` patcher.
"""

from __future__ import annotations

import bisect
import math

import config

# Order matters only for deterministic tie-breaking.
AXES: tuple[str, ...] = (
    "combat",
    "mining",
    "building",
    "exploration",
    "crafting",
    "farming",
    "pvp",
    "boss",
    "daredevil",
    "hoarding",
    "questing",
    "homebody",
)

AXIS_LABEL: dict[str, str] = {
    "combat": "Combat",
    "mining": "Mining",
    "building": "Building",
    "exploration": "Exploration",
    "crafting": "Crafting",
    "farming": "Farming",
    "pvp": "PvP",
    "boss": "Boss Slaying",
    "daredevil": "Recklessness",
    "hoarding": "Hoarding",
    "questing": "Questing",
    "homebody": "Homebody",
}

# A player must clear this percentile on their best axis to earn a themed title;
# otherwise they are a "balanced" Chaotic Neutral Adventurer.
DOMINANCE_THRESHOLD = 55.0
# Axes above this percentile are shown as "what makes you you" standouts.
STANDOUT_THRESHOLD = 60.0


def _g(m: dict, key: str, default: float = 0.0) -> float:
    val = m.get(key, default)
    return val if isinstance(val, (int, float)) else default


def axis_raw_values(m: dict) -> dict[str, float]:
    """Raw, un-normalized score per axis for a single player's metrics."""
    dist = m.get("distance_km") or {}
    flown = dist.get("flown", 0.0) if isinstance(dist, dict) else 0.0
    playtime = max(_g(m, "playtime_hours"), 0.0)
    distance = _g(m, "distance_km_total")
    used_plus_crafted = max(_g(m, "items_used") + _g(m, "items_crafted"), 1.0)

    return {
        "combat": _g(m, "mob_kills") + _g(m, "damage_dealt") / 500.0 + _g(m, "player_kills") * 5.0,
        "mining": _g(m, "blocks_mined"),
        "building": _g(m, "blocks_placed"),
        "exploration": distance + flown * 0.5,
        "crafting": _g(m, "items_crafted"),
        "farming": _g(m, "farming_score"),
        "pvp": _g(m, "player_kills"),
        "boss": _g(m, "total_boss_kills"),
        "daredevil": _g(m, "deaths") / max(playtime, 1.0),
        "hoarding": _g(m, "items_picked_up") / used_plus_crafted,
        # High hours, low travel => classic base-dweller.
        "homebody": playtime / (distance + 1.0),
        "questing": _g(m, "quest_completion_pct"),
    }


def _percentiles(values: list[float]) -> list[float]:
    """Percentile = share of the rest of the server you strictly outscore."""
    n = len(values)
    if n <= 1:
        return [50.0] * n
    ordered = sorted(values)
    out: list[float] = []
    for v in values:
        beaten = bisect.bisect_left(ordered, v)
        out.append(beaten / (n - 1) * 100.0)
    return out


def _ranks(values: list[float]) -> list[int]:
    """Competition ranking, 1 = best (highest value); ties share the top rank."""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i], reverse=True)
    ranks = [0] * n
    prev_val = None
    prev_rank = 0
    for pos, idx in enumerate(order, start=1):
        v = values[idx]
        if prev_val is None or v != prev_val:
            prev_rank = pos
            prev_val = v
        ranks[idx] = prev_rank
    return ranks


def _zscores(values: list[float]) -> list[float]:
    n = len(values)
    if n == 0:
        return []
    mean = sum(values) / n
    var = sum((x - mean) ** 2 for x in values) / n
    std = math.sqrt(var)
    if std <= 0:
        return [0.0] * n
    return [(x - mean) / std for x in values]


def safe_ratio(numerator: float, denominator: float, digits: int = 2) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, digits)


def _fmt_int(v: float) -> str:
    return f"{int(round(v)):,}"


def _title_for(axis: str) -> dict:
    info = config.TITLE_CONFIG.get(axis, config.TITLE_CONFIG["balanced"])
    return {
        "key": axis,
        "title": info["title"],
        "tagline": info["tagline"],
        "icon": info.get("icon", "\U0001f3b2"),
    }


def _summary(entry: dict, dominant: str, standouts: list[dict], ratios: dict) -> str:
    name = entry.get("name", "This player")
    m = entry
    parts: list[str] = []

    openers = {
        "combat": "A career built on violence — {mob_kills:,} mobs cut down and {dmg:,} damage dealt.",
        "mining": "{mined:,} blocks torn from the earth. The bedrock has learned to fear them.",
        "building": "{placed:,} blocks placed — an actual builder among a server of vandals.",
        "exploration": "{dist:.0f} km on the odometer; the map fills in wherever they wander.",
        "crafting": "{crafted:,} items crafted. The workbench files them as a dependent.",
        "farming": "A farming score of {farm:,} — the crops are safe in devoted hands.",
        "pvp": "{pkills:,} player kills. Fellow members log off when they log on.",
        "boss": "{bosses:,} bosses put in the ground. The pantheon is running low.",
        "daredevil": "{deaths:,} deaths and counting — allergic to staying alive, immune to learning.",
        "hoarding": "Hauls in far more than they ever use — a walking, breathing storage unit.",
        "homebody": "{hours:.0f} hours logged, barely {dist:.0f} km traveled. Why leave a good base?",
        "questing": "{quests:.0f}% of the quest book cleared — a checkbox enthusiast of the highest order.",
        "balanced": "No single obsession — {name} dabbles in a bit of everything and masters none.",
    }
    opener = openers.get(dominant, openers["balanced"]).format(
        name=name,
        mob_kills=int(_g(m, "mob_kills")),
        dmg=int(_g(m, "damage_dealt")),
        mined=int(_g(m, "blocks_mined")),
        placed=int(_g(m, "blocks_placed")),
        dist=_g(m, "distance_km_total"),
        crafted=int(_g(m, "items_crafted")),
        farm=int(_g(m, "farming_score")),
        pkills=int(_g(m, "player_kills")),
        bosses=int(_g(m, "total_boss_kills")),
        deaths=int(_g(m, "deaths")),
        hours=_g(m, "playtime_hours"),
        quests=_g(m, "quest_completion_pct"),
    )
    parts.append(opener)

    # A comparative jab using the second-strongest standout.
    secondary = next((s for s in standouts if s["axis"] != dominant), None)
    if secondary:
        parts.append(
            f"Also ranks #{secondary['rank']} of {secondary['of']} in "
            f"{AXIS_LABEL[secondary['axis']]} (top {secondary['top_pct']}%)."
        )

    # A ratio-flavored observation.
    kd = ratios.get("damage_dealt_to_taken", 0)
    build_mine = ratios.get("blocks_placed_to_mined", 0)
    if kd >= 2:
        parts.append("Deals far more than they absorb — respectfully terrifying.")
    elif 0 < kd <= 0.5:
        parts.append("Absorbs damage like a communal punching bag. Bold strategy.")
    elif build_mine >= 1.2:
        parts.append("Puts back more than they dig up. Civilized behaviour, frankly.")
    elif 0 < build_mine < 0.15 and _g(m, "blocks_mined") > 500:
        parts.append("Pure demolition energy — mines everything, replaces nothing.")

    return " ".join(parts[:3])


def build_report_cards(entries: list[dict]) -> list[dict]:
    """
    entries: list of flat metric dicts (each must include a ``name`` key and the
    raw metric fields used by :func:`axis_raw_values`).

    Returns a list of report_card dicts aligned to ``entries`` order.
    """
    n = len(entries)
    if n == 0:
        return []

    raw = [axis_raw_values(e) for e in entries]

    percentile_by_axis: dict[str, list[float]] = {}
    rank_by_axis: dict[str, list[int]] = {}
    z_by_axis: dict[str, list[float]] = {}
    for axis in AXES:
        col = [r[axis] for r in raw]
        # Axes where nobody scored (all zero) carry no signal.
        if max(col) <= 0:
            percentile_by_axis[axis] = [0.0] * n
            z_by_axis[axis] = [0.0] * n
        else:
            percentile_by_axis[axis] = _percentiles(col)
            z_by_axis[axis] = _zscores(col)
        rank_by_axis[axis] = _ranks(col)

    cards: list[dict] = []
    for i, entry in enumerate(entries):
        pcts = {axis: percentile_by_axis[axis][i] for axis in AXES}
        zs = {axis: z_by_axis[axis][i] for axis in AXES}

        # Dominant axis: highest percentile, tie-broken by z-score then axis order.
        best_axis = max(AXES, key=lambda a: (round(pcts[a], 4), round(zs[a], 4), -AXES.index(a)))
        dominant = best_axis if pcts[best_axis] >= DOMINANCE_THRESHOLD else "balanced"

        # Standouts: strongest axes worth bragging about.
        ordered_axes = sorted(AXES, key=lambda a: pcts[a], reverse=True)
        standouts: list[dict] = []
        for axis in ordered_axes:
            if pcts[axis] < STANDOUT_THRESHOLD:
                continue
            rank = rank_by_axis[axis][i]
            standouts.append(
                {
                    "axis": axis,
                    "label": AXIS_LABEL[axis],
                    "rank": rank,
                    "of": n,
                    "percentile": round(pcts[axis]),
                    "top_pct": max(1, round(rank / n * 100)),
                }
            )
            if len(standouts) >= 4:
                break

        walked = max(_g(entry, "distance_km_total"), 0.01)
        ratios = {
            "damage_dealt_to_taken": safe_ratio(_g(entry, "damage_dealt"), max(_g(entry, "damage_taken"), 1)),
            "blocks_placed_to_mined": safe_ratio(_g(entry, "blocks_placed"), max(_g(entry, "blocks_mined"), 1)),
            "blocks_mined_per_km_walked": safe_ratio(_g(entry, "blocks_mined"), walked),
            "kills_per_death": safe_ratio(_g(entry, "mob_kills"), max(_g(entry, "deaths"), 1)),
        }

        title = _title_for(dominant)
        dom_rank = rank_by_axis[dominant][i] if dominant in rank_by_axis else n
        if dominant == "balanced":
            rank_line = f"No dominant axis \u2014 balanced across {n} players"
        else:
            rank_line = (
                f"#{dom_rank} of {n} in {AXIS_LABEL[dominant]} "
                f"\u00b7 top {max(1, round(dom_rank / n * 100))}%"
            )

        summary = _summary(entry, dominant, standouts, ratios)

        cards.append(
            {
                "title": title["title"],
                "title_key": title["key"],
                "tagline": title["tagline"],
                "icon": title["icon"],
                "rank_line": rank_line,
                "summary": summary,
                "standouts": standouts,
                "ratios": ratios,
                "highlights": [
                    {"label": "Playtime", "value": f"{_g(entry, 'playtime_hours'):.1f}h"},
                    {"label": "Mob Kills", "value": _fmt_int(_g(entry, "mob_kills"))},
                    {"label": "Blocks Mined", "value": _fmt_int(_g(entry, "blocks_mined"))},
                    {"label": "Deaths", "value": _fmt_int(_g(entry, "deaths"))},
                    {"label": "Distance", "value": f"{_g(entry, 'distance_km_total'):.0f} km"},
                    {"label": "Bosses", "value": _fmt_int(_g(entry, "total_boss_kills"))},
                ],
            }
        )

    return cards
