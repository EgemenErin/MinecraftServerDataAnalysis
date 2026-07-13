"""Read a player's worn/best gear from their playerdata .dat NBT file.

Produces a compact, display-friendly gear summary plus a single ``gear_score``
used for the "Strongest Gear" leaderboard. Scoring intentionally leans on
enchantment investment (which we can read reliably even for modded items)
with a smaller material-tier component.
"""

from __future__ import annotations

from pathlib import Path

from nbt_reader import read_nbt_file

# Inventory slot ids for worn armor + offhand (pre-1.20.5 NBT layout).
ARMOR_SLOTS = {103: "helmet", 102: "chestplate", 101: "leggings", 100: "boots"}
OFFHAND_SLOT = -106

# Material tier -> weight. First substring match wins, so order matters.
# Mythic Metals endgame tiers are above netherite; orichalcum is mid-high hallowed.
MATERIAL_WEIGHTS: tuple[tuple[str, int], ...] = (
    ("celestium", 16),
    ("unobtainium", 16),
    ("metallurgium", 15),
    ("star_platinum", 15),
    ("shadowsting", 14),
    ("lichblade", 14),
    ("hearthflame", 14),
    ("hallowed", 12),
    ("adamantite", 10),
    ("mythril", 10),
    ("orichalcum", 10),
    ("palladium", 10),
    ("carmot", 10),
    ("runite", 9),
    ("netherite", 9),
    ("diamond", 7),
    ("turtle", 6),
    ("iron", 4),
    ("chainmail", 4),
    ("bronze", 3),
    ("golden", 3),
    ("gold", 3),
    ("stone", 2),
    ("leather", 2),
    ("wooden", 1),
    ("wood", 1),
)
DEFAULT_MATERIAL_WEIGHT = 6  # unknown modded gear

WEAPON_HINTS = (
    "sword", "axe", "trident", "mace", "bow", "crossbow", "glaive", "spear",
    "halberd", "dagger", "katana", "rapier", "claymore", "scythe", "lance",
    "warhammer", "flail", "pike", "staff", "hammer", "blade", "sting",
)
# Tools and shields are not combat weapons for gear ranking.
NON_WEAPON_HINTS = (
    "shield", "tartsche", "buckler", "targe", "pavise", "kite",
    "pickaxe", "shovel", "hoe", "shears", "fishing_rod", "book",
)

ROLE_ICONS = {
    "helmet": "\u26d1\ufe0f",
    "chestplate": "\U0001f9ba",
    "leggings": "\U0001f456",
    "boots": "\U0001f97e",
    "weapon": "\u2694\ufe0f",
    "offhand": "\U0001f6e1\ufe0f",
}


def _short(item_id: str) -> str:
    return item_id.split(":")[-1]


def pretty_item(item_id: str) -> str:
    return _short(item_id).replace("_", " ").title()


def material_weight(item_id: str) -> int:
    low = item_id.lower()
    for key, weight in MATERIAL_WEIGHTS:
        if key in low:
            return weight
    return DEFAULT_MATERIAL_WEIGHT


def _enchants(item: dict) -> list[dict]:
    tag = item.get("tag") or {}
    raw = tag.get("Enchantments") or tag.get("StoredEnchantments") or []
    out: list[dict] = []
    for entry in raw:
        if isinstance(entry, dict) and entry.get("id"):
            out.append({"name": pretty_item(str(entry["id"])), "lvl": int(entry.get("lvl", 0))})
    # 1.20.5+ component layout, kept for forward compatibility.
    comp = item.get("components") or {}
    ce = comp.get("minecraft:enchantments")
    if isinstance(ce, dict):
        for eid, lvl in (ce.get("levels") or {}).items():
            out.append({"name": pretty_item(str(eid)), "lvl": int(lvl)})
    return out


def _make_piece(role: str, item: dict) -> dict:
    item_id = str(item.get("id"))
    enchants = _enchants(item)
    ench_levels = sum(e["lvl"] for e in enchants)
    return {
        "role": role,
        "icon": ROLE_ICONS.get(role, "\U0001f392"),
        "id": item_id,
        "name": pretty_item(item_id),
        "material_weight": material_weight(item_id),
        "enchant_levels": ench_levels,
        "enchants": enchants,
    }


def _is_weapon(item_id: str) -> bool:
    low = item_id.lower()
    if any(h in low for h in NON_WEAPON_HINTS):
        return False
    return any(h in low for h in WEAPON_HINTS)


def empty_gear() -> dict:
    return {
        "has_data": False,
        "gear_score": 0,
        "armor_pieces": 0,
        "full_set": False,
        "total_enchant_levels": 0,
        "xp_level": 0,
        "pieces": [],
        "best_item": None,
    }


def build_player_gear(uuid: str, playerdata_dir: str | Path) -> dict:
    path = Path(playerdata_dir) / f"{uuid}.dat"
    if not path.exists():
        return empty_gear()

    try:
        root = read_nbt_file(path)
    except Exception:  # noqa: BLE001 - a single corrupt .dat shouldn't break the run
        return empty_gear()

    inventory = root.get("Inventory") or []
    if not isinstance(inventory, list):
        return empty_gear()

    pieces: list[dict] = []
    armor_by_slot: dict[str, dict] = {}
    offhand_piece: dict | None = None
    best_weapon: dict | None = None

    for item in inventory:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        slot = item.get("Slot")
        item_id = str(item.get("id"))

        if slot in ARMOR_SLOTS:
            armor_by_slot[ARMOR_SLOTS[slot]] = _make_piece(ARMOR_SLOTS[slot], item)
        elif slot == OFFHAND_SLOT:
            offhand_piece = _make_piece("offhand", item)

        if _is_weapon(item_id):
            candidate = _make_piece("weapon", item)
            candidate_score = candidate["material_weight"] + candidate["enchant_levels"] * 2
            if best_weapon is None or candidate_score > (
                best_weapon["material_weight"] + best_weapon["enchant_levels"] * 2
            ):
                best_weapon = candidate

    for role in ("helmet", "chestplate", "leggings", "boots"):
        if role in armor_by_slot:
            pieces.append(armor_by_slot[role])
    if best_weapon:
        pieces.append(best_weapon)
    if offhand_piece:
        pieces.append(offhand_piece)

    if not pieces:
        result = empty_gear()
        result["has_data"] = True
        result["xp_level"] = int(root.get("XpLevel", 0) or 0)
        return result

    armor_pieces_list = [armor_by_slot[r] for r in ("helmet", "chestplate", "leggings", "boots") if r in armor_by_slot]
    armor_pieces = len(armor_pieces_list)
    full_set = armor_pieces >= 4
    total_ench = sum(p["enchant_levels"] for p in pieces)

    armor_material = sum(p["material_weight"] for p in armor_pieces_list)
    armor_ench = sum(p["enchant_levels"] for p in armor_pieces_list)
    weapon_material = best_weapon["material_weight"] if best_weapon else 0
    weapon_ench = best_weapon["enchant_levels"] if best_weapon else 0

    # Armor tier matters more than a single god-roll weapon; enchants still count.
    gear_score = (
        armor_material * 3
        + armor_ench * 2
        + weapon_material * 2
        + weapon_ench * 2
        + (15 if full_set else 0)
    )

    best_item = max(pieces, key=lambda p: (p["material_weight"], p["enchant_levels"]))

    return {
        "has_data": True,
        "gear_score": int(gear_score),
        "armor_pieces": armor_pieces,
        "full_set": full_set,
        "total_enchant_levels": int(total_ench),
        "xp_level": int(root.get("XpLevel", 0) or 0),
        "pieces": pieces,
        "best_item": {"name": best_item["name"], "enchant_levels": best_item["enchant_levels"]},
    }
