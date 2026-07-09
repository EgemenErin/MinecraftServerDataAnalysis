"""
Editable server lore config — tweak titles and awards without touching core logic.
"""

# Dominant playstyle axis -> title shown on the report card.
# The dominant axis is chosen by how much a player STANDS OUT from the rest of
# the server (population-relative ranking), not by raw totals — so titles are
# spread across the whole roster instead of everyone being a miner.
# Keys must match the axes in report_card.AXES, plus "balanced".
TITLE_CONFIG: dict[str, dict[str, str]] = {
    "combat": {
        "title": "Knight of House Ace",
        "tagline": "Lives for the fight, dies for the drama",
        "icon": "\u2694\ufe0f",
    },
    "mining": {
        "title": "Devout of the Church of Tonton",
        "tagline": "Prays to the deepslate, tithes in cobblestone",
        "icon": "\u26cf\ufe0f",
    },
    "building": {
        "title": "Kluk Artisan",
        "tagline": "Places more than they break — a rare civility",
        "icon": "\U0001f9f1",
    },
    "exploration": {
        "title": "Wandering Politician's Scout",
        "tagline": "Never in the same chunk twice",
        "icon": "\U0001f9ed",
    },
    "crafting": {
        "title": "Apprentice of the Grand Workbench",
        "tagline": "The crafting grid is a second home",
        "icon": "\U0001f6e0\ufe0f",
    },
    "farming": {
        "title": "Keeper of the Sacred Crops",
        "tagline": "The hoe never rests",
        "icon": "\U0001f33e",
    },
    "pvp": {
        "title": "Server Menace",
        "tagline": "A clear and present danger to their fellow player",
        "icon": "\U0001f5e1\ufe0f",
    },
    "boss": {
        "title": "Slayer of the Old Gods",
        "tagline": "Bosses have filed a restraining order",
        "icon": "\U0001f409",
    },
    "daredevil": {
        "title": "The Eternal Respawner",
        "tagline": "Death is merely a minor inconvenience",
        "icon": "\U0001f480",
    },
    "hoarding": {
        "title": "Dragon of the Hoard",
        "tagline": "Picks up everything, parts with nothing",
        "icon": "\U0001f4b0",
    },
    "questing": {
        "title": "Chronicler of the Great Book",
        "tagline": "Lives one checkbox at a time",
        "icon": "\U0001f4d6",
    },
    "homebody": {
        "title": "Hermit of the Hollow",
        "tagline": "Logs the hours without ever leaving the base",
        "icon": "\U0001f3e1",
    },
    "balanced": {
        "title": "Chaotic Neutral Adventurer",
        "tagline": "Master of none, dabbler in everything",
        "icon": "\U0001f3b2",
    },
}

# Superlative awards computed across all players.
# stat: field on each player's internal metrics dict (see analyze_stats.py)
# direction: "max" = highest wins, "min" = lowest wins
AWARDS_CONFIG: list[dict[str, str]] = [
    {
        "id": "most_blocks_placed",
        "label": "Most Blocks Placed",
        "stat": "blocks_placed",
        "direction": "max",
    },
    {
        "id": "most_underground",
        "label": "Most Time Spent Underground",
        "stat": "underground_ratio",
        "direction": "max",
    },
    {
        "id": "least_efficient_hunter",
        "label": "Least Efficient Hunter",
        "stat": "damage_taken_per_kill",
        "direction": "max",
    },
    {
        "id": "biggest_hoarder",
        "label": "Biggest Hoarder",
        "stat": "hoarder_ratio",
        "direction": "max",
    },
    {
        "id": "most_deaths",
        "label": "Most Deaths",
        "stat": "deaths",
        "direction": "max",
    },
    {
        "id": "longest_distance",
        "label": "Longest Distance Traveled",
        "stat": "distance_km_total",
        "direction": "max",
    },
    {
        "id": "most_richest_ores",
        "label": "Most Rich (Ore Hoard)",
        "stat": "ore_wealth",
        "direction": "max",
    },
    {
        "id": "most_emeralds",
        "label": "Emerald Tycoon",
        "stat": "emeralds_picked_up",
        "direction": "max",
    },
    {
        "id": "most_diamonds",
        "label": "Diamond Goblin",
        "stat": "diamonds_picked_up",
        "direction": "max",
    },
    {
        "id": "biggest_looter",
        "label": "Biggest Looter",
        "stat": "chests_looted",
        "direction": "max",
    },
    {
        "id": "most_quests",
        "label": "Quest Completionist",
        "stat": "quest_completion_pct",
        "direction": "max",
    },
    {
        "id": "most_boss_kills",
        "label": "Boss Slayer Supreme",
        "stat": "total_boss_kills",
        "direction": "max",
    },
    {
        "id": "biggest_sleeper",
        "label": "Professional Sleeper",
        "stat": "slept_in_bed",
        "direction": "max",
    },
    {
        "id": "most_villager_chatter",
        "label": "Mayor of Villager Town",
        "stat": "villager_talks",
        "direction": "max",
    },
    {
        "id": "speed_demon",
        "label": "Speed Demon",
        "stat": "sprint_km",
        "direction": "max",
    },
    {
        "id": "most_pvp",
        "label": "Most Wanted (PvP)",
        "stat": "player_kills",
        "direction": "max",
    },
]

# Entity id substrings treated as boss-like kills in stats.
BOSS_ENTITY_HINTS: tuple[str, ...] = (
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
    "alchemist",
    "pumpkini",
    "overgrown",
)

# Death causes considered "embarrassing" for the hall-of-shame list.
EMBARRASSING_CAUSES: set[str] = {
    "fall",
    "lava",
    "drowning",
    "fire",
    "starvation",
    "suffocation",
    "cactus",
    "sweet_berry",
    "other_self_inflicted",
}
