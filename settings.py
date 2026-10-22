"""
Global settings, Tile IDs, EXP curves, Stamina, Relics, and configurations for
2D Real-time Grid-Based Dungeon Crawler / Action Roguelike RPG.
"""

# Screen Settings
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 768
FPS = 60
TITLE = "Dungeon Crawler - 2D Action Roguelike RPG"

# Tile Settings
TILE_SIZE = 32

# Map / Dungeon Generation Settings
MAP_WIDTH = 64      # In tiles (64 * 32 = 2048 px)
MAP_HEIGHT = 50     # In tiles (50 * 32 = 1600 px)

# Room Size Configurations (Favors square tactical rooms)
NORMAL_ROOM_MIN_SIZE = 10
NORMAL_ROOM_MAX_SIZE = 14
BOSS_ROOM_MIN_SIZE = 12
BOSS_ROOM_MAX_SIZE = 18

# Boss arena (min, max) side in tiles, scaled to the boss sprite: 90px bosses (floors 4, 6, 10) get the
# biggest arena, 60px bosses (2, 7, 8, 9) a medium one, the 32-50px early bosses (1, 3, 5) a compact one.
BOSS_ROOM_SIZE_BY_FLOOR = {
    1: (14, 16), 2: (16, 18), 3: (14, 16), 4: (18, 21), 5: (14, 16),
    6: (18, 21), 7: (16, 18), 8: (16, 18), 9: (16, 18), 10: (19, 22),
}
MIN_LEAF_SIZE = 14

# Colors (RGB)
COLOR_BLACK = (15, 15, 20)
COLOR_DARK_GRAY = (35, 35, 45)
COLOR_GRAY = (80, 80, 95)
COLOR_LIGHT_GRAY = (180, 180, 195)
COLOR_WHITE = (245, 245, 250)

COLOR_FLOOR = (45, 42, 55)
COLOR_FLOOR_GRID = (55, 52, 68)
COLOR_WALL = (22, 20, 30)
COLOR_WALL_TOP = (65, 60, 80)
COLOR_DOOR = (140, 90, 45)
COLOR_GATE_CLOSED = (190, 50, 50)
COLOR_GATE_OPEN = (70, 180, 90)
COLOR_EXIT = (50, 200, 150)
COLOR_CHEST = (210, 160, 40)
COLOR_TRAP = (180, 60, 60)

# UI Colors
COLOR_HP_RED = (220, 50, 50)
COLOR_HP_BG = (80, 20, 20)
COLOR_XP_CYAN = (40, 180, 220)
COLOR_XP_BG = (15, 60, 75)
COLOR_STAMINA_GREEN = (50, 200, 80)
COLOR_STAMINA_BG = (15, 65, 25)
COLOR_MANA_BLUE = (70, 130, 250)
COLOR_MANA_BG = (18, 30, 80)
COLOR_GOLD = (255, 215, 0)
COLOR_UI_BG = (20, 20, 28, 220)
COLOR_UI_BORDER = (100, 90, 130)

# Mana System (casting classes, e.g. Mage with Staff weapons)
MANA_STAFF_COST = 6  # MP consumed per Staff/magic-weapon attack

# Rarity Colors
COLOR_COMMON = (200, 200, 200)
COLOR_UNCOMMON = (60, 200, 60)
COLOR_RARE = (60, 140, 240)
COLOR_EPIC = (180, 60, 230)
COLOR_LEGENDARY = (255, 170, 0)

# Grid Tile IDs
TILE_WALL = 0
TILE_FLOOR = 1
TILE_DOOR = 2
TILE_CLOSED_GATE = 3
TILE_OPEN_GATE = 4
TILE_CHEST = 5
TILE_BARREL = 6
TILE_PILLAR = 7
TILE_TRAP = 8
TILE_EXIT = 9
TILE_PLAYER_SPAWN = 10
TILE_ENEMY_SPAWN = 11

WALKABLE_TILES = {TILE_FLOOR, TILE_DOOR, TILE_OPEN_GATE, TILE_TRAP, TILE_EXIT, TILE_PLAYER_SPAWN, TILE_ENEMY_SPAWN}

# Directions
DIR_UP = (0, -1)
DIR_DOWN = (0, 1)
DIR_LEFT = (-1, 0)
DIR_RIGHT = (1, 0)
ALL_DIRECTIONS = [DIR_UP, DIR_DOWN, DIR_LEFT, DIR_RIGHT]

# Action Roguelike Stamina Costs
STAMINA_DASH_COST = 25.0
STAMINA_HEAVY_ATTACK_COST = 30.0
STAMINA_SPECIAL_COST = 35.0
STAMINA_REGEN_RATE = 28.0  # per second

# Difficulties
DIFFICULTY_EASY = "EASY"
DIFFICULTY_NORMAL = "NORMAL"
DIFFICULTY_HARD = "HARD"

DIFFICULTY_MODIFIERS = {
    DIFFICULTY_EASY: {
        "enemy_hp": 0.8,
        "enemy_dmg": 0.8,
        "enemy_count": 0.8,
        "loot_mult": 1.3,
        "boss_hp": 0.8,
        "boss_dmg": 0.8
    },
    DIFFICULTY_NORMAL: {
        "enemy_hp": 1.0,
        "enemy_dmg": 1.0,
        "enemy_count": 1.0,
        "loot_mult": 1.0,
        "boss_hp": 1.0,
        "boss_dmg": 1.0
    },
    DIFFICULTY_HARD: {
        "enemy_hp": 1.3,
        "enemy_dmg": 1.3,
        "enemy_count": 1.3,
        "loot_mult": 0.8,
        "boss_hp": 1.4,
        "boss_dmg": 1.3
    }
}

# Fog of War Settings
FOG_ENABLED = True
FOG_RADIUS = 7.5  # In tiles
FOG_DARKNESS = 230
FOG_EXPLORED_ALPHA = 140

# Experience Table for Enemies
ENEMY_EXP_REWARDS = {
    "goblin": 10,
    "skeleton": 15,
    "archer_enemy": 20,
    "orc": 25,
    "mage_enemy": 30,
    "poison_slime": 22,
    "slime": 22,
    "fire_imp": 28,
    "imp": 28,
    "elite": 65,
    "boss": 200
}

# Pathfinding settings
ASTAR_MAX_ITERATIONS = 400
ENEMY_PATHFIND_COOLDOWN = 0.30  # Recalculate interval for A* in real-time

# Dungeon generation robustness
DUNGEON_MAX_ATTEMPTS = 24  # Bounded regeneration retries per seed before raising an error

# Minimap room-type colors (dungeon-overview style, see demo_dungeon.png reference)
ROOM_MINIMAP_COLORS = {
    "START ROOM": (50, 110, 235),      # Blue - start
    "COMBAT ROOM": (55, 175, 75),      # Green - combat
    "NORMAL ROOM": (55, 175, 75),      # Green - regular combat area
    "ELITE ROOM": (215, 55, 45),       # Red - elite
    "TREASURE ROOM": (235, 180, 40),   # Yellow/gold - treasure
    "SHOP ROOM": (60, 215, 220),       # Cyan - NPC/Shop
    "NPC ROOM": (60, 215, 220),        # Cyan - NPC
    "RESCUE ROOM": (120, 220, 240),    # Light cyan - rescue NPC
    "SURVIVAL ROOM": (240, 145, 40),   # Orange - survival special
    "EVENT ROOM": (200, 90, 230),      # Magenta - event special
    "TRAP ROOM": (150, 45, 55),        # Dark red - trap special
    "BOSS ROOM": (150, 65, 220),       # Purple - boss
}


# Every sprite sheet (heroes, monsters) is drawn facing LEFT, so a sprite is mirrored when it faces right.
SPRITES_FACE_LEFT = True


def flip_for(dx: float, current: bool) -> bool:
    """flip_x for a sprite moving/aiming along `dx`; keeps `current` when there is no horizontal component."""
    if abs(dx) < 0.05:
        return current
    return (dx > 0) if SPRITES_FACE_LEFT else (dx < 0)
