"""Generate TontoSMP Daily Shop trade table JSON files."""
from __future__ import annotations

import glob
import json
import os
import zipfile

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if not os.path.isdir(os.path.join(BASE, "config", "dailyshop")):
    BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT_DIR = os.path.join(BASE, "config", "dailyshop", "trade_tables")
MODS = os.path.join(BASE, "mods")
COIN = "bcg_smp:joe_coin"

def find_mod_jar(mod_name: str) -> str | None:
    for path in glob.glob(os.path.join(MODS, "*.jar")):
        if mod_name in os.path.basename(path).lower():
            return path
    return None


def read_uniques_tag(mod_name: str) -> list[str]:
    """Load registered unique item IDs from each mod's uniques tag."""
    jar_path = find_mod_jar(mod_name)
    if not jar_path:
        return []

    tag_suffix = "/tags/item/uniques.json" if mod_name == "simplybows" else "/tags/items/uniques.json"
    with zipfile.ZipFile(jar_path) as zf:
        for name in zf.namelist():
            if f"data/{mod_name}" in name and name.endswith(tag_suffix):
                data = json.loads(zf.read(name))
                items: list[str] = []
                for value in data.get("values", []):
                    if isinstance(value, str):
                        items.append(value)
                    elif isinstance(value, dict) and value.get("required", True):
                        item_id = value.get("id")
                        if isinstance(item_id, str):
                            items.append(item_id)
                return sorted(items)
    return []


MYTHIC_DAILY_WEIGHT = 1
MYTHIC_WEAPON_CHANCE = 30
MYTHIC_NONE_CHANCE = 70


def pool_table(roll_count: int, pool: list[dict]) -> dict:
    return {
        "roll": {"type": "constant", "count": roll_count},
        "pool": pool,
    }


def empty_table() -> dict:
    """Trade table that contributes zero offers when selected."""
    return pool_table(0, [{"value": "tontosmp_experience", "weight": 1}])


def output_entry(item: str, count: int = 1) -> dict:
    return {
        "item": item,
        "count": {"type": "constant", "count": count},
        "weight": 1,
    }


def trade_table(price: int, outputs: list, trades: int = -1) -> dict:
    table = {
        "roll": {"type": "constant", "count": 1},
        "input1": {
            "filter": COIN,
            "count": {"type": "constant", "count": price},
        },
        "output": outputs,
    }
    if trades >= 0:
        table["trades"] = {"type": "constant", "count": trades}
    return table


def write_json(name: str, data: dict) -> str:
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    return path


def collect_spawn_eggs() -> list[str]:
    """Use spawn eggs from the pack's original emerald shop tables (already validated)."""
    eggs: set[str] = set()
    for path in glob.glob(os.path.join(OUT_DIR, "*emerald*.json")):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for entry in data.get("output", []):
            item = entry.get("item", "")
            if "spawn_egg" in item:
                eggs.add(item)
    return sorted(eggs)


def enchant_book(enchant_id: str, level: int) -> dict:
    return {
        "item": "minecraft:enchanted_book",
        "nbt": {"StoredEnchantments": [{"id": enchant_id, "lvl": level}]},
        "count": {"type": "constant", "count": 1},
        "weight": 1,
    }


def main() -> None:
    simplyswords = read_uniques_tag("simplyswords")
    simplymore = read_uniques_tag("simplymore")
    simplybows = read_uniques_tag("simplybows")

    artifacts = [
        "artifacts:anglers_hat",
        "artifacts:antidote_vessel",
        "artifacts:aqua_dashers",
        "artifacts:bunny_hoppers",
        "artifacts:charm_of_sinking",
        "artifacts:chorus_totem",
        "artifacts:cloud_in_a_bottle",
        "artifacts:cowboy_hat",
        "artifacts:cross_necklace",
        "artifacts:crystal_heart",
        "artifacts:digging_claws",
        "artifacts:eternal_steak",
        "artifacts:everlasting_beef",
        "artifacts:feral_claws",
        "artifacts:fire_gauntlet",
        "artifacts:flame_pendant",
        "artifacts:flippers",
        "artifacts:golden_hook",
        "artifacts:helium_flamingo",
        "artifacts:kitty_slippers",
        "artifacts:lucky_scarf",
        "artifacts:night_vision_goggles",
        "artifacts:novelty_drinking_hat",
        "artifacts:obsidian_skull",
        "artifacts:onion_ring",
        "artifacts:panic_necklace",
        "artifacts:pickaxe_heater",
        "artifacts:plastic_drinking_hat",
        "artifacts:pocket_piston",
        "artifacts:power_glove",
        "artifacts:rooted_boots",
        "artifacts:running_shoes",
        "artifacts:scarf_of_invisibility",
        "artifacts:shock_pendant",
        "artifacts:snorkel",
        "artifacts:snowshoes",
        "artifacts:steadfast_spikes",
        "artifacts:superstitious_hat",
        "artifacts:thorn_pendant",
        "artifacts:umbrella",
        "artifacts:universal_attractor",
        "artifacts:vampiric_glove",
        "artifacts:villager_hat",
        "artifacts:whoopee_cushion",
    ]

    spawn_eggs = collect_spawn_eggs()

    aircraft = [
        "immersive_aircraft:boiler",
        "immersive_aircraft:bomb_bay",
        "immersive_aircraft:eco_engine",
        "immersive_aircraft:engine",
        "immersive_aircraft:enhanced_propeller",
        "immersive_aircraft:gyroscope",
        "immersive_aircraft:hull",
        "immersive_aircraft:hull_reinforcement",
        "immersive_aircraft:improved_landing_gear",
        "immersive_aircraft:industrial_gears",
        "immersive_aircraft:nether_engine",
        "immersive_aircraft:propeller",
        "immersive_aircraft:sail",
        "immersive_aircraft:steel_boiler",
        "immersive_aircraft:sturdy_pipes",
        "immersive_aircraft:telescope",
    ]

    building_blocks = [
        "minecraft:stone",
        "minecraft:cobblestone",
        "minecraft:stone_bricks",
        "minecraft:mossy_stone_bricks",
        "minecraft:cracked_stone_bricks",
        "minecraft:chiseled_stone_bricks",
        "minecraft:smooth_stone",
        "minecraft:deepslate",
        "minecraft:cobbled_deepslate",
        "minecraft:deepslate_bricks",
        "minecraft:deepslate_tiles",
        "minecraft:polished_deepslate",
        "minecraft:bricks",
        "minecraft:mud_bricks",
        "minecraft:nether_bricks",
        "minecraft:red_nether_bricks",
        "minecraft:polished_blackstone",
        "minecraft:polished_blackstone_bricks",
        "minecraft:blackstone",
        "minecraft:granite",
        "minecraft:polished_granite",
        "minecraft:diorite",
        "minecraft:polished_diorite",
        "minecraft:andesite",
        "minecraft:polished_andesite",
        "minecraft:sandstone",
        "minecraft:smooth_sandstone",
        "minecraft:red_sandstone",
        "minecraft:smooth_red_sandstone",
        "minecraft:prismarine",
        "minecraft:prismarine_bricks",
        "minecraft:dark_prismarine",
        "minecraft:quartz_block",
        "minecraft:smooth_quartz",
        "minecraft:purpur_block",
        "minecraft:end_stone_bricks",
        "create:cut_granite",
        "create:cut_diorite",
        "create:cut_andesite",
        "create:cut_deepslate",
        "create:cut_limestone",
        "create:cut_scorchia",
        "create:cut_scoria",
        "create:cut_tuff",
        "create:cut_granite_bricks",
        "create:cut_diorite_bricks",
        "create:cut_andesite_bricks",
        "create:cut_deepslate_bricks",
        "create:cut_tuff_bricks",
    ]

    enchant_books = [
        enchant_book("minecraft:sharpness", 5),
        enchant_book("minecraft:smite", 5),
        enchant_book("minecraft:bane_of_arthropods", 5),
        enchant_book("minecraft:efficiency", 5),
        enchant_book("minecraft:fortune", 3),
        enchant_book("minecraft:silk_touch", 1),
        enchant_book("minecraft:protection", 4),
        enchant_book("minecraft:blast_protection", 4),
        enchant_book("minecraft:projectile_protection", 4),
        enchant_book("minecraft:fire_protection", 4),
        enchant_book("minecraft:feather_falling", 4),
        enchant_book("minecraft:depth_strider", 3),
        enchant_book("minecraft:respiration", 3),
        enchant_book("minecraft:aqua_affinity", 1),
        enchant_book("minecraft:looting", 3),
        enchant_book("minecraft:sweeping_edge", 3),
        enchant_book("minecraft:power", 5),
        enchant_book("minecraft:punch", 2),
        enchant_book("minecraft:infinity", 1),
        enchant_book("minecraft:mending", 1),
        enchant_book("minecraft:unbreaking", 3),
        enchant_book("minecraft:lure", 3),
        enchant_book("minecraft:luck_of_the_sea", 3),
        enchant_book("minecraft:multishot", 1),
        enchant_book("minecraft:piercing", 4),
        enchant_book("minecraft:quick_charge", 3),
    ]

    tables = {
        "tontosmp_simplyswords": trade_table(128, [output_entry(i) for i in simplyswords], trades=1),
        "tontosmp_simplymore": trade_table(128, [output_entry(i) for i in simplymore], trades=1),
        "tontosmp_simplybows": trade_table(150, [output_entry(i) for i in simplybows], trades=1),
        "tontosmp_spawn_eggs": trade_table(80, [output_entry(i) for i in spawn_eggs]),
        "tontosmp_artifacts": trade_table(50, [output_entry(i) for i in artifacts]),
        "tontosmp_experience": trade_table(10, [output_entry("create:experience_nugget", 64)]),
        "tontosmp_building_blocks": trade_table(
            1, [output_entry(i, 64) for i in building_blocks]
        ),
        "tontosmp_aircraft": trade_table(5, [output_entry(i) for i in aircraft]),
        "tontosmp_enchant_books": trade_table(15, enchant_books),
        "tontosmp_elytra": trade_table(150, [output_entry("minecraft:elytra")], trades=1),
        "tontosmp_netherite": trade_table(35, [output_entry("minecraft:netherite_ingot")]),
        "tontosmp_mythic_none": empty_table(),
        "tontosmp_mythic_weapon": pool_table(
            1,
            [
                {"value": "tontosmp_simplyswords", "weight": len(simplyswords)},
                {"value": "tontosmp_simplymore", "weight": len(simplymore)},
                {"value": "tontosmp_simplybows", "weight": len(simplybows)},
            ],
        ),
        "tontosmp_mythic_daily": pool_table(
            1,
            [
                {"value": "tontosmp_mythic_weapon", "weight": MYTHIC_WEAPON_CHANCE},
                {"value": "tontosmp_mythic_none", "weight": MYTHIC_NONE_CHANCE},
            ],
        ),
    }

    for name, data in tables.items():
        write_json(name, data)

    main = {
        "roll": {"type": "constant", "count": 24},
        "pool": [
            {"value": "tontosmp_mythic_daily", "weight": MYTHIC_DAILY_WEIGHT},
            {"value": "tontosmp_spawn_eggs", "weight": 6},
            {"value": "tontosmp_artifacts", "weight": 5},
            {"value": "tontosmp_experience", "weight": 4},
            {"value": "tontosmp_building_blocks", "weight": 8},
            {"value": "tontosmp_aircraft", "weight": 5},
            {"value": "tontosmp_enchant_books", "weight": 5},
            {"value": "tontosmp_elytra", "weight": 1},
            {"value": "tontosmp_netherite", "weight": 3},
        ],
    }
    write_json("tontosmp_shop", main)

    daily_shop_path = os.path.join(BASE, "config", "dailyshop", "daily_shop.json")
    with open(daily_shop_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "startEpoch": 7200000,
                "refreshDelay": 86400000,
                "trades": "tontosmp_shop",
            },
            f,
            indent=2,
        )
        f.write("\n")

    print(f"simplyswords: {len(simplyswords)}")
    print(f"simplymore: {len(simplymore)}")
    print(f"simplybows: {len(simplybows)}")
    print(f"spawn_eggs: {len(spawn_eggs)}")
    print(f"artifacts: {len(artifacts)}")
    print(f"Updated {daily_shop_path}")


if __name__ == "__main__":
    main()
