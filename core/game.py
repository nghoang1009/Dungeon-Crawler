import pygame
import random
import math
import sys
import time

from settings import (
    SCREEN_WIDTH, SCREEN_HEIGHT, FPS, TITLE, DIFFICULTY_NORMAL,
    DIFFICULTY_EASY, DIFFICULTY_HARD, DIFFICULTY_MODIFIERS, COLOR_GOLD,
    COLOR_XP_CYAN, TILE_CHEST,
    TILE_TRAP, TILE_EXIT, TILE_FLOOR, TILE_CLOSED_GATE, TILE_OPEN_GATE, MANA_STAFF_COST, flip_for
)
from core.camera import Camera
from core.sound import SoundManager
from core.music import MusicManager
from core.sprite_loader import SpriteSheetLoader
from core.save_manager import SaveManager
from dungeon.dungeon_generator import DungeonGenerator
from dungeon.room import RoomType, RoomState
from world.tilemap import TileMap
from world.chest import Chest
from world.door import Trap
from world.gate import Gate, BossRoomController, BossRoomState
from world.obstacle import Obstacle, ObstacleType
from world.ground_item import GroundItem
from items.relic import AVAILABLE_RELICS
from items.loot import LootTable
from entities.player import Player
from entities.enemy import Goblin, Skeleton, Orc, ArcherEnemy, MageEnemy, PoisonSlime, FireImp
from entities.boss import Boss, create_boss_for_floor
from entities.npc import NPC, NPCStyle
from combat.combat_system import CombatSystem
from combat.damage import DamageNumber
from progression.level_system import LevelSystem, LevelUpModal
from ui.hud import HUD
from ui.boss_bar import BossBar
from ui.inventory_ui import InventoryUI
from ui.npc_modal import NPCModal
from ui.menu import MenuManager, MenuState
from ui.minimap import Minimap

MOUSE_MENU_STATES = (MenuState.MAIN_MENU, MenuState.CLASS_SELECT, MenuState.RUN_CONFIG,
                     MenuState.PAUSED, MenuState.GAME_OVER, MenuState.VICTORY)


class Game:
    """
    Main Game Controller for 2D Real-Time Grid-Based Action Roguelike RPG.
    Supports 10 Floors Progression, 10 Unique Bosses (Type A & Type B), 3-Phase Final Boss on Floor 10,
    Telegraph Warning Zones, Dodge i-frames, Room Clear Locking & Unlocking,
    Special Rooms (Treasure, Shop, Rescue, Survival, Event, Trap), Data-Driven Weapons,
    Status Effects (Slow, Poison, Burn, Hazard Areas), Score System, Physical Loot Drops,
    and Run Complete Victory Screen.
    """
    def __init__(self):
        pygame.init()
        pygame.font.init()
        pygame.display.set_caption(TITLE)

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.is_running = True
        self._last_class_click = 0.0

        # Initialize Sprite Sheet Assets
        self.sprite_loader = SpriteSheetLoader()
        self.sprite_loader.initialize()

        # Fonts
        self.font_small = pygame.font.SysFont("consolas", 14)
        self.font_medium = pygame.font.SysFont("consolas", 18, bold=True)
        self.font_title = pygame.font.SysFont("consolas", 24, bold=True)
        self.font_huge = pygame.font.SysFont("consolas", 48, bold=True)

        # Core Subsystems
        self.sound_manager = SoundManager()
        self.sound_manager.initialize()
        self.music = MusicManager(self.sound_manager)
        self.camera = Camera(SCREEN_WIDTH, SCREEN_HEIGHT)
        self.combat_system = CombatSystem(self.sound_manager, self.camera)

        # UI Subsystems
        self.hud = HUD(self.font_small, self.font_medium)
        self.boss_bar = BossBar(self.font_medium, self.font_small)
        self.inventory_ui = InventoryUI(self.font_title, self.font_medium)
        self.npc_modal = NPCModal(self.font_huge, self.font_title, self.font_medium)
        self.menu_manager = MenuManager(self.font_huge, self.font_title, self.font_medium)
        self.level_up_modal = LevelUpModal(self.font_huge, self.font_title, self.font_medium)
        self.minimap = Minimap()

        # Game State
        self.game_state = MenuState.MAIN_MENU
        self.current_floor = 1
        self.seed = random.randint(100000, 999999)
        self.debug_mode = False
        self.sprite_debug_mode = False

        # World State
        self.tilemap: TileMap | None = None
        self.dungeon_gen: DungeonGenerator | None = None
        self.boss_controller: BossRoomController | None = None
        self.player: Player | None = None
        self.enemies: list = []
        self.boss: Boss | None = None
        self.chests: list[Chest] = []
        self.traps: list[Trap] = []
        self.npcs: list[NPC] = []
        self.obstacles: list[Obstacle] = []
        self.ground_items: list[GroundItem] = []
        self.boss_gates: list[Gate] = []

    def start_new_game(self, new_seed: int | None = None):
        """Builds fresh procedural floor with 8-12 diverse rooms, NPCs, and relics."""
        if new_seed is not None:
            self.seed = new_seed

        diff = self.menu_manager.selected_difficulty
        base_mod = DIFFICULTY_MODIFIERS.get(diff, DIFFICULTY_MODIFIERS[DIFFICULTY_NORMAL]).copy()
        floor_scale = 1.0 + (self.current_floor - 1) * 0.18
        diff_mod = {
            "enemy_hp": base_mod.get("enemy_hp", 1.0) * floor_scale,
            "enemy_dmg": base_mod.get("enemy_dmg", 1.0) * floor_scale,
            "boss_hp": base_mod.get("boss_hp", 1.0) * (1.0 + (self.current_floor - 1) * 0.22),
            "boss_dmg": base_mod.get("boss_dmg", 1.0) * (1.0 + (self.current_floor - 1) * 0.20),
        }
        chosen_class = self.menu_manager.current_class

        # 1. Procedural Dungeon Generation (BSP, Topologies, Room Shapes)
        # Spawn placement uses its own seeded rng (never the global random state),
        # so the same seed always reproduces the same layout + entity placement.
        # Global random stays reserved for gameplay-time rolls (loot, crits).
        spawn_rng = random.Random(f"{self.seed}:spawn:{self.current_floor}")
        self.dungeon_gen = DungeonGenerator(seed=self.seed, floor=self.current_floor)
        grid = self.dungeon_gen.generate()
        self.tilemap = TileMap(grid)
        self.camera.set_map_size(self.tilemap.width, self.tilemap.height)
        self.boss_gates = list(self.dungeon_gen.boss_gates)
        self.boss_controller = self.dungeon_gen.boss_controller

        # 2. Spawn Player (Retains progression across floors & when loading a save)
        spawn_tx, spawn_ty = self.dungeon_gen.get_player_spawn_pos()
        if self.player is None:
            self.player = Player(spawn_tx, spawn_ty, chosen_class)
        else:
            self.player.set_grid_pos(spawn_tx, spawn_ty)
            self.player.current_hp = self.player.max_hp

        # 3. Populate Entities, Objects, Chests, Obstacles
        self.enemies.clear()
        self.chests.clear()
        self.traps.clear()
        self.npcs.clear()
        self.obstacles.clear()
        self.ground_items.clear()
        self.combat_system.projectiles.clear()
        self.combat_system.slash_effects.clear()
        self.combat_system.telegraph_zones.clear()
        self.combat_system.hazard_areas.clear()
        self.boss = None

        # Chests & Traps from Tilemap
        for ty in range(self.tilemap.height):
            for tx in range(self.tilemap.width):
                tid = self.tilemap.grid[ty][tx]
                if tid == TILE_CHEST:
                    is_tr = any(r.room_type == RoomType.TREASURE and r.x <= tx < r.right and r.y <= ty < r.bottom for r in self.dungeon_gen.rooms)
                    self.chests.append(Chest(tx, ty, is_treasure_room=is_tr))
                elif tid == TILE_TRAP:
                    self.traps.append(Trap(tx, ty))

        # Populate Rooms with Boss, NPCs, Obstacles, and Relics
        for room in self.dungeon_gen.rooms:
            room.enemies = []
            room.state = RoomState.UNVISITED

            if room.room_type == RoomType.BOSS:
                bx, by = room.center_x, room.center_y
                self.boss = create_boss_for_floor(self.current_floor, diff_mod, bx, by)
                self.enemies.append(self.boss)
                room.enemies.append(self.boss)

                for offset in [(-4, -4), (4, -4), (-4, 4), (4, 4)]:
                    ptx = room.center_x + offset[0]
                    pty = room.center_y + offset[1]
                    if self.tilemap.is_walkable(ptx, pty, self.obstacles, self.boss_gates):
                        self.obstacles.append(Obstacle(ptx, pty, ObstacleType.PILLAR))

            elif room.room_type == RoomType.SHOP:
                npc_types = [NPCStyle.BLACKSMITH, NPCStyle.MERCHANT, NPCStyle.HEALER, NPCStyle.RELIC_TRADER]
                chosen_npc_type = self.dungeon_gen.rng.choice(npc_types)
                self.npcs.append(NPC(room.center_x, room.center_y, npc_type=chosen_npc_type))

            elif room.room_type == RoomType.RESCUE:
                # Trapped NPC in cage + 2 enemy guards
                trapped_npc = NPC(room.center_x, room.center_y, npc_type=NPCStyle.RESCUE, is_trapped=True)
                self.npcs.append(trapped_npc)
                for ox in [-2, 2]:
                    gx, gy = room.center_x + ox, room.center_y
                    if self.tilemap.is_walkable(gx, gy, self.obstacles, self.boss_gates):
                        guard = Orc(gx, gy, diff_mod) if ox < 0 else ArcherEnemy(gx, gy, diff_mod)
                        self.enemies.append(guard)
                        room.enemies.append(guard)

            elif room.room_type == RoomType.SURVIVAL:
                # Survival room with timed waves
                room.survival_timer = 20.0
                room.wave_timer = 3.0
                e1 = Goblin(room.center_x - 2, room.center_y, diff_mod)
                e2 = PoisonSlime(room.center_x + 2, room.center_y, diff_mod)
                self.enemies.extend([e1, e2])
                room.enemies.extend([e1, e2])

            elif room.room_type == RoomType.EVENT:
                # Mystery Altar / Blood Shrine
                shrine = NPC(room.center_x, room.center_y, npc_type=NPCStyle.EVENT_SHRINE)
                self.npcs.append(shrine)

            elif room.room_type == RoomType.TRAP:
                # Floor hazard patches
                self.combat_system.spawn_hazard_area(room.center_x, room.center_y, "poison", duration=9999.0)
                self.combat_system.spawn_hazard_area(room.center_x + 1, room.center_y + 1, "burn", duration=9999.0)

            elif room.room_type == RoomType.ELITE:
                ex, ey = room.center_x, room.center_y
                elite_orc = Orc(ex, ey, diff_mod)
                elite_orc.max_hp = int(elite_orc.max_hp * 1.6)
                elite_orc.current_hp = elite_orc.max_hp
                elite_orc.attack_power += 6
                elite_orc.exp_reward = 70
                self.enemies.append(elite_orc)
                room.enemies.append(elite_orc)

                chosen_relic = spawn_rng.choice(AVAILABLE_RELICS)()
                self.ground_items.append(GroundItem(room.center_x, room.center_y + 1, "relic", chosen_relic))

            elif room.room_type in (RoomType.COMBAT, RoomType.NORMAL):
                num_barrels = spawn_rng.randint(1, 3)
                for _ in range(num_barrels):
                    btx, bty = room.get_random_floor_tile(self.dungeon_gen.rng)
                    if self.tilemap.is_walkable(btx, bty, self.obstacles, self.boss_gates) and (btx, bty) != room.center:
                        self.obstacles.append(Obstacle(btx, bty, ObstacleType.BARREL))

                num_enemies = spawn_rng.randint(2, 4)
                for _ in range(num_enemies):
                    etx, ety = room.get_random_floor_tile(self.dungeon_gen.rng)
                    if not self.tilemap.is_walkable(etx, ety, self.obstacles, self.boss_gates):
                        continue

                    roll = spawn_rng.random()
                    if roll < 0.25:
                        enemy = Goblin(etx, ety, diff_mod)
                    elif roll < 0.45:
                        enemy = Skeleton(etx, ety, diff_mod)
                    elif roll < 0.60:
                        enemy = PoisonSlime(etx, ety, diff_mod)
                    elif roll < 0.75:
                        enemy = ArcherEnemy(etx, ety, diff_mod)
                    elif roll < 0.88:
                        enemy = FireImp(etx, ety, diff_mod)
                    elif roll < 0.95:
                        enemy = MageEnemy(etx, ety, diff_mod)
                    else:
                        enemy = Orc(etx, ety, diff_mod)

                    self.enemies.append(enemy)
                    room.enemies.append(enemy)

        for room in self.dungeon_gen.rooms:
            for e in room.enemies:
                e.home_room = room

        self.tilemap.update_fog_of_war(spawn_tx, spawn_ty)
        self.game_state = MenuState.PLAYING

    def next_floor(self):
        self.current_floor += 1
        if self.current_floor > 10:
            self.game_state = MenuState.VICTORY
            return
        self.seed = random.randint(100000, 999999)
        self.start_new_game(self.seed)

    def load_saved_game(self):
        """Loads a save file (if any) and rebuilds the dungeon + player from it."""
        data = SaveManager.load_game()
        if not data:
            return
        player = SaveManager.create_player_from_save(data)
        if player is None:
            return

        self.player = player
        self.current_floor = max(1, int(data.get("dungeon_floor", 1)))
        self.seed = int(data.get("dungeon_seed", random.randint(100000, 999999)))
        diff = data.get("difficulty")
        if diff in (DIFFICULTY_EASY, DIFFICULTY_NORMAL, DIFFICULTY_HARD):
            self.menu_manager.selected_difficulty = diff

        # start_new_game refills HP when repositioning the player; restore the
        # exact saved HP/mana afterwards so the run resumes as it was saved.
        saved_hp = player.current_hp
        saved_mana = player.mana
        self.start_new_game(self.seed)
        self.player.current_hp = max(1, min(saved_hp, self.player.max_hp))
        self.player.mana = max(0.0, min(saved_mana, float(self.player.max_mana)))

        # Restore the played dungeon progress (fog, room states, chests, boss)
        self._restore_dungeon_state(data.get("dungeon_state"),
                                    player_pos=data.get("player_pos"))

    def _restore_dungeon_state(self, dungeon_state: dict | None, player_pos=None):
        """
        Applies saved dungeon progress onto the freshly regenerated (deterministic,
        same-seed) floor. Old save files without dungeon_state keep the fresh map.
        """
        if not dungeon_state or not self.dungeon_gen or not self.tilemap:
            return

        # 1. Room states by room_id (deterministic generation guarantees the ids)
        saved_rooms = {rd.get("room_id"): rd for rd in dungeon_state.get("rooms", [])}
        for room in self.dungeon_gen.rooms:
            rd = saved_rooms.get(room.room_id)
            if not rd:
                continue
            room.state = rd.get("state", RoomState.UNVISITED)
            room.is_cleared = rd.get("is_cleared", False)
            room.has_visited = rd.get("has_visited", False)
            room.reward_spawned = rd.get("reward_spawned", False)

            if room.state == RoomState.ACTIVE:
                # Combat was mid-encounter: re-lock the entrance gates
                for dx, dy in room.door_tiles:
                    self.tilemap.set_tile(dx, dy, TILE_CLOSED_GATE)
            elif room.is_cleared:
                for dx, dy in room.door_tiles:
                    self.tilemap.set_tile(dx, dy, TILE_FLOOR)

        # 2. Explored fog
        explored_rows = dungeon_state.get("explored_rows", [])
        for ty, row in enumerate(explored_rows):
            if ty >= self.tilemap.height:
                break
            for tx, ch in enumerate(row[:self.tilemap.width]):
                self.tilemap.explored[ty][tx] = (ch == "1")

        # 3. Opened chests (deterministic spawn order from the generator)
        chest_flags = dungeon_state.get("chests_opened", [])
        for chest, opened in zip(self.chests, chest_flags):
            if opened:
                chest.is_opened = True

        # 4. Boss already defeated: no respawn, gates open, room cleared
        if dungeon_state.get("boss_defeated") and self.boss:
            if self.boss in self.enemies:
                self.enemies.remove(self.boss)
            if self.dungeon_gen.boss_room:
                self.dungeon_gen.boss_room.state = RoomState.CLEARED
                self.dungeon_gen.boss_room.is_cleared = True
            for gate in self.boss_gates:
                gate.is_open = True
                self.tilemap.set_tile(gate.tx, gate.ty, TILE_OPEN_GATE)
            if self.boss_controller:
                self.boss_controller.state = "COMPLETED"
            self.boss = None

        # 5. Player position
        if player_pos and len(player_pos) == 2:
            px, py = int(player_pos[0]), int(player_pos[1])
            if self.tilemap.is_walkable(px, py):
                self.player.set_grid_pos(px, py)
                self.tilemap.update_fog_of_war(px, py)

    def start_attack(self, direction: tuple[float, float] | None = None) -> bool:
        if not self.player or not self.player.can_attack():
            return False
        if direction is not None:
            self.player.facing_dir = direction
            self.player.flip_x = flip_for(direction[0], self.player.flip_x)

        # Magic weapons (Staff) consume the caster's mana per cast
        wp = self.player.current_weapon
        mana_cost = MANA_STAFF_COST if (self.player.uses_mana and wp and wp.weapon_category == "STAFF") else 0.0
        if mana_cost > 0 and not self.player.use_mana(mana_cost):
            if wp:
                wp.cooldown = max(0.35, 1.0 / max(0.1, wp.attack_speed))
            self.combat_system.damage_numbers.append(
                DamageNumber(self.player.pos_x, self.player.pos_y - 14, "Not enough mana!", (120, 170, 255))
            )
            return False

        return self.combat_system.player_attack(self.player, self.enemies, self.obstacles, self.tilemap, direction=direction)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
                return

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F3:
                    self.debug_mode = not self.debug_mode
                elif event.key == pygame.K_F4:
                    self.sprite_debug_mode = not self.sprite_debug_mode

            # Mouse: click buttons / cards / fields of the menu screens
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.game_state in MOUSE_MENU_STATES:
                action = self.menu_manager.click(self.game_state, event.pos, self.current_floor)
                if action:
                    self._menu_action(action)
                continue

            if self.game_state == MenuState.MAIN_MENU:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._open_class_select()
                    elif event.key == pygame.K_l:
                        self.load_saved_game()
                    elif event.key == pygame.K_t:
                        self.menu_manager.cycle_difficulty()

            elif self.game_state == MenuState.CLASS_SELECT:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_a, pygame.K_LEFT):
                        self.menu_manager.cycle_class(-1)
                    elif event.key in (pygame.K_d, pygame.K_RIGHT):
                        self.menu_manager.cycle_class(1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._confirm_class()
                    elif event.key == pygame.K_ESCAPE:
                        self.game_state = MenuState.MAIN_MENU

            elif self.game_state == MenuState.RUN_CONFIG:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.game_state = MenuState.CLASS_SELECT
                    elif event.key in (pygame.K_TAB, pygame.K_UP, pygame.K_DOWN):
                        self.menu_manager.active_field = \
                            "seed" if self.menu_manager.active_field == "name" else "name"
                    elif event.key == pygame.K_r:
                        self.menu_manager.randomize_seed()
                    elif event.key == pygame.K_BACKSPACE:
                        self.menu_manager.backspace()
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self._start_run()
                    else:
                        if event.unicode:
                            self.menu_manager.append_char(event.unicode)

            elif self.game_state == MenuState.PLAYING:
                if self.level_up_modal.is_active:
                    if self.level_up_modal.handle_input(event, self.player):
                        continue

                if self.npc_modal.is_active:
                    if self.npc_modal.handle_input(event, self.player, self.sound_manager):
                        continue

                if self.inventory_ui.is_open:
                    if self.inventory_ui.handle_input(event, self.player):
                        continue
                    # Unconsumed I / ESC closes the inventory instead of pausing
                    if event.type == pygame.KEYDOWN and event.key in (pygame.K_i, pygame.K_ESCAPE):
                        self.inventory_ui.close()
                        continue

                # Real-Time Action Input Events
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_p, pygame.K_ESCAPE):
                        self.game_state = MenuState.PAUSED
                    elif event.key == pygame.K_i:
                        self.inventory_ui.toggle()
                    elif event.key == pygame.K_m:
                        self.minimap.toggle()
                    elif event.key == pygame.K_n:
                        self.music.toggle()
                    elif event.key == pygame.K_TAB:
                        self.player.next_weapon()
                    elif event.key == pygame.K_SPACE:
                        # Space Dash Dodge (with i-frames along moving/facing dir)
                        keys = pygame.key.get_pressed()
                        mx, my = 0.0, 0.0
                        if keys[pygame.K_w] or keys[pygame.K_UP]: my -= 1.0
                        if keys[pygame.K_s] or keys[pygame.K_DOWN]: my += 1.0
                        if keys[pygame.K_a] or keys[pygame.K_LEFT]: mx -= 1.0
                        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: mx += 1.0
                        mag = math.hypot(mx, my)
                        move_dir = (mx / mag, my / mag) if mag > 0 else self.player.facing_dir
                        self.player.trigger_dash(move_dir=move_dir, sound_manager=self.sound_manager, game=self)
                    elif event.key in (pygame.K_q, pygame.K_1):
                        self.player.use_health_potion(self.sound_manager, self.combat_system)
                    elif event.key == pygame.K_2:
                        self.player.use_mana_potion(self.sound_manager, self.combat_system)
                    elif event.key in (pygame.K_k, pygame.K_j):
                        # B. ATTACK THEO HƯỚNG PLAYER ĐANG NHÌN (K Key)
                        self.start_attack(direction=self.player.facing_dir)
                    elif event.key == pygame.K_f:
                        if not self._interact_world():
                            self.player.trigger_special_skill(self)
                    elif event.key == pygame.K_e:
                        self._interact_world()

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # A. ATTACK THEO CON TRỎ CHUỘT (Left Mouse Button)
                    toolbar = self.hud.toolbar_action(event.pos)
                    if toolbar:
                        if toolbar == "inventory":
                            self.inventory_ui.toggle()
                        elif toolbar == "map":
                            self.minimap.toggle()
                        elif toolbar == "pause":
                            self.game_state = MenuState.PAUSED
                    elif not self.inventory_ui.is_open and not self.level_up_modal.is_active and not self.npc_modal.is_active:
                        mx, my = event.pos
                        player_screen_rect = self.camera.apply(self.player.rect)
                        dx = float(mx - player_screen_rect.centerx)
                        dy = float(my - player_screen_rect.centery)
                        mag = math.hypot(dx, dy)
                        mouse_dir = (dx / mag, dy / mag) if mag > 0 else self.player.facing_dir
                        self.start_attack(direction=mouse_dir)

            elif self.game_state == MenuState.PAUSED:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_p, pygame.K_ESCAPE):
                        self.game_state = MenuState.PLAYING
                    elif event.key == pygame.K_s:
                        self._save_game()
                    elif event.key == pygame.K_n:
                        self.music.toggle()
                    elif event.key == pygame.K_m:
                        self.game_state = MenuState.MAIN_MENU

            elif self.game_state == MenuState.GAME_OVER:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:
                        self._restart_dungeon()
                    elif event.key == pygame.K_m:
                        self.game_state = MenuState.MAIN_MENU

            elif self.game_state == MenuState.VICTORY:
                if event.type == pygame.KEYDOWN:
                    if self.current_floor >= 10:
                        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_m):
                            self.game_state = MenuState.MAIN_MENU
                    else:
                        if event.key in (pygame.K_RETURN, pygame.K_n, pygame.K_SPACE):
                            self.next_floor()
                        elif event.key == pygame.K_m:
                            self.game_state = MenuState.MAIN_MENU

    # ------------------------------------------------------------------ menu actions (keys + mouse)
    def _open_class_select(self):
        self.game_state = MenuState.CLASS_SELECT

    def _confirm_class(self):
        self.menu_manager.reset_run_config()
        self.game_state = MenuState.RUN_CONFIG

    def _start_run(self):
        configured = self.menu_manager.get_configured_seed()
        self.seed = configured if configured is not None else random.randint(100000, 999999)
        self.current_floor = 1
        self.player = None
        self.start_new_game()
        self.player.name = self.menu_manager.player_name.strip() or "Hero"

    def _save_game(self):
        dungeon_state = SaveManager.collect_dungeon_state(self)
        ok = SaveManager.save_game(self.player, self.seed, self.current_floor,
                                   self.menu_manager.selected_difficulty,
                                   dungeon_state=dungeon_state)
        self.menu_manager.show_notice("Game saved" if ok else "Could not save the game")

    def _restart_dungeon(self):
        self.player = None
        self.current_floor = 1
        self.start_new_game()

    def _menu_action(self, action: str) -> None:
        """Runs a clickable menu action (see MenuManager.buttons_for / hotspots_for)."""
        mm = self.menu_manager
        if action == "play":
            self._open_class_select()
        elif action == "load":
            self.load_saved_game()
        elif action == "difficulty":
            mm.cycle_difficulty()
        elif action == "quit":
            self.is_running = False
        elif action == "back":
            self.game_state = MenuState.MAIN_MENU if self.game_state == MenuState.CLASS_SELECT else MenuState.CLASS_SELECT
        elif action == "confirm_class":
            self._confirm_class()
        elif action == "start_run":
            self._start_run()
        elif action == "random":
            mm.randomize_seed()
        elif action.startswith("field:"):
            mm.active_field = action.split(":", 1)[1]
        elif action.startswith("class:"):
            idx = int(action.split(":", 1)[1])
            now = time.perf_counter()
            if idx == mm.selected_class_idx and now - self._last_class_click < 0.4:
                self._confirm_class()   # double-click starts with that hero
            mm.selected_class_idx = idx
            self._last_class_click = now
        elif action == "music":
            self.music.toggle()
        elif action == "resume":
            self.game_state = MenuState.PLAYING
        elif action == "save":
            self._save_game()
        elif action == "main_menu":
            self.game_state = MenuState.MAIN_MENU
        elif action == "restart":
            self._restart_dungeon()
        elif action == "next_floor":
            self.next_floor()

    def _interact_world(self) -> bool:
        px, py = self.player.grid_x, self.player.grid_y

        for chest in self.chests:
            if not chest.is_opened and (abs(chest.tx - px) + abs(chest.ty - py) <= 1):
                chest.interact(self.player, self.sound_manager, self.combat_system, self.ground_items, self.tilemap)
                return True

        for npc in self.npcs:
            ntx, nty = npc.get_tile_pos()
            if abs(ntx - px) + abs(nty - py) <= 1:
                if npc.is_trapped:
                    msg = npc.rescue()
                    self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 20, msg, (100, 255, 180)))
                    self.sound_manager.play("levelup")
                self.npc_modal.open_npc(npc)
                return True

        if self.tilemap.get_tile(px, py) == TILE_EXIT:
            if self.boss and not self.boss.is_alive:
                self.game_state = MenuState.VICTORY
                return True

        return False

    def update(self, dt: float):
        # Inventory modal freezes ALL gameplay simulation (player, enemies, boss AI,
        # projectiles, telegraph countdown, status ticks, traps, cooldowns, room/survival/
        # spawn timers) while UI keeps receiving events in handle_events() and rendering.
        if self.game_state != MenuState.PLAYING or self.level_up_modal.is_active \
                or self.npc_modal.is_active or self.inventory_ui.is_open:
            return

        # 1. Real-Time Player Continuous Input Handling (WASD) & Update
        keys = pygame.key.get_pressed()
        self.player.handle_continuous_input(keys, dt, self.tilemap, self.obstacles, self.boss_gates)
        self.player.update(dt, self.combat_system)

        # 1b. Hold Left Mouse Button Auto-Hit (attacks at weapon's attack speed)
        mouse_pressed = pygame.mouse.get_pressed()
        if mouse_pressed[0] and self.player.is_alive and not self.hud.is_over_ui(pygame.mouse.get_pos()):
            mx, my = pygame.mouse.get_pos()
            player_screen_rect = self.camera.apply(self.player.rect)
            dx = float(mx - player_screen_rect.centerx)
            dy = float(my - player_screen_rect.centery)
            mag = math.hypot(dx, dy)
            if mag > 0:
                mouse_dir = (dx / mag, dy / mag)
                self.player.facing_dir = mouse_dir
                self.player.flip_x = flip_for(mouse_dir[0], self.player.flip_x)
            else:
                mouse_dir = self.player.facing_dir
            self.start_attack(direction=mouse_dir)

        if not self.player.is_alive:
            self.game_state = MenuState.GAME_OVER
            return

        px, py = self.player.grid_x, self.player.grid_y

        # 2. Room State & Combat Locking System
        if self.dungeon_gen:
            for room in self.dungeon_gen.rooms:
                if room.room_type in (RoomType.COMBAT, RoomType.ELITE, RoomType.SURVIVAL, RoomType.RESCUE):
                    # Enter unvisited room -> Lock room doors
                    if room.state == RoomState.UNVISITED and room.is_pos_inside_inner(px, py):
                        room.state = RoomState.ACTIVE
                        for dx, dy in room.door_tiles:
                            self.tilemap.set_tile(dx, dy, TILE_CLOSED_GATE)

                    # Update Active Room
                    if room.state == RoomState.ACTIVE:
                        if room.room_type == RoomType.SURVIVAL:
                            room.survival_timer -= dt
                            room.wave_timer -= dt
                            if room.wave_timer <= 0 and room.survival_timer > 3.0:
                                room.wave_timer = 4.5
                                sx, sy = room.get_random_floor_tile()
                                if self.tilemap.is_walkable(sx, sy, self.obstacles, self.boss_gates):
                                    m_pool = [Goblin, PoisonSlime, Skeleton, FireImp]
                                    chosen_m_cls = random.choice(m_pool)
                                    new_m = chosen_m_cls(sx, sy)
                                    new_m.home_room = room
                                    self.enemies.append(new_m)
                                    room.enemies.append(new_m)

                            if room.survival_timer <= 0:
                                for e in room.enemies:
                                    e.take_damage(9999)
                                room.is_cleared = True

                        # Check if all enemies in this room are dead
                        living_enemies = [e for e in room.enemies if e.is_alive]
                        if not living_enemies:
                            room.state = RoomState.CLEARED
                            room.is_cleared = True
                            # Unlock door tiles
                            for dx, dy in room.door_tiles:
                                self.tilemap.set_tile(dx, dy, TILE_FLOOR)

                            # Spawn room clear reward & award score
                            if not room.reward_spawned:
                                room.reward_spawned = True
                                self.player.add_score(150)
                                c_loot = LootTable.generate_chest_loot(is_treasure_room=(room.room_type == RoomType.ELITE))
                                for l_type, l_val in c_loot:
                                    self.ground_items.append(GroundItem(room.center_x, room.center_y, l_type, l_val))
                                self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 25, "ROOM CLEARED!", (100, 255, 140)))
                                self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 42, "+150 SCORE", COLOR_GOLD))
                                self.sound_manager.play("levelup")

        # 3. Check Ground Item Pickups (Gold, Potions, Weapons, Relics)
        for item in self.ground_items:
            if not item.is_picked_up and (item.gx, item.gy) == (px, py):
                item.is_picked_up = True
                if item.loot_type == "gold":
                    self.player.add_gold(item.data)
                    self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 12, f"+{item.data} Gold", COLOR_GOLD))
                elif item.loot_type == "potion":
                    self.player.inventory.add_item(item.data)
                    self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 12, f"+{item.data.name}", item.data.icon_color))
                elif item.loot_type == "weapon":
                    self.player.inventory.add_weapon(item.data)
                    self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 12, f"Found {item.data.display_name}!", item.data.rarity_color))
                elif item.loot_type == "relic":
                    self.player.add_relic(item.data)
                    self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 16, f"Obtained: {item.data.name}!", item.data.color, is_crit=True))
                self.sound_manager.play("chest")

        self.ground_items = [it for it in self.ground_items if not it.is_picked_up]

        # 4. Update Boss Room Controller State Machine
        if self.boss_controller:
            self.boss_controller.update(dt, self.player, self.boss, self.tilemap, self.sound_manager, self.camera)

        # 5. Traps
        for trap in self.traps:
            trap.update(dt, self.player, self.combat_system)

        # 6. Enemies Real-Time Update
        earned_exp = 0
        for enemy in self.enemies:
            if enemy.is_alive:
                enemy.update(dt, self)
            elif not enemy.is_removed and enemy.state_machine.current_state_name == "DEAD":
                earned_exp += enemy.exp_reward
                enemy.is_removed = True
                self.sound_manager.play("death")

                if enemy == self.boss and self.boss_controller:
                    self.boss_controller.on_boss_death((self.boss.grid_x, self.boss.grid_y), self.tilemap, self.ground_items, self.sound_manager, self.camera)
                else:
                    e_loot = LootTable.generate_enemy_loot(enemy.enemy_type)
                    for l_type, l_val in e_loot:
                        self.ground_items.append(GroundItem(enemy.grid_x, enemy.grid_y, l_type, l_val))

        self.enemies = [e for e in self.enemies if not e.is_removed]

        # 7. Obstacles destruction & loot drop
        for obs in self.obstacles:
            if not obs.is_alive and hasattr(obs, "get_drops"):
                drops = obs.get_drops()
                for dtype, dval in drops:
                    self.ground_items.append(GroundItem(obs.tx, obs.ty, dtype, dval))
        self.obstacles = [o for o in self.obstacles if o.is_alive]

        # 8. Check EXP & Level Up Choice Modal
        if earned_exp > 0:
            level_ups = LevelSystem.add_exp(self.player, earned_exp)
            self.combat_system.damage_numbers.append(DamageNumber(self.player.pos_x, self.player.pos_y - 20, f"+{earned_exp} EXP", COLOR_XP_CYAN))

            if level_ups > 0:
                self.sound_manager.play("levelup")
                self.level_up_modal.trigger_level_up(level_ups)

        # 9. Update Combat Subsystems (Slashes, Projectiles, Telegraph zones, Hazard areas, Particles)
        self.combat_system.update(dt, self.tilemap, self.enemies, self.player, self.obstacles)

        # 10. Camera Lerp & Fog of War
        self.camera.update(self.player, dt)
        self.tilemap.update_fog_of_war(self.player.grid_x, self.player.grid_y)

    def draw(self):
        self._sync_music()
        self.screen.fill((15, 12, 22))

        if self.game_state in (MenuState.PLAYING, MenuState.PAUSED, MenuState.GAME_OVER, MenuState.VICTORY):
            # 1. Tilemap Frustum Culling & Fog of War
            self.tilemap.render(self.screen, self.camera)

            # 2. Gates
            for gate in self.boss_gates:
                if self.tilemap.explored[gate.ty][gate.tx]:
                    gate.render(self.screen, self.camera)

            # 3. Obstacles (Barrels, Pillars)
            for obs in self.obstacles:
                if self.tilemap.explored[obs.ty][obs.tx]:
                    obs.render(self.screen, self.camera)

            # 4. Chests & NPCs
            for chest in self.chests:
                if self.tilemap.explored[chest.ty][chest.tx]:
                    chest.render(self.screen, self.camera)

            for npc in self.npcs:
                ntx, nty = npc.get_tile_pos()
                if self.tilemap.explored[nty][ntx]:
                    npc.render(self.screen, self.camera)

            # 5. Ground Items
            for item in self.ground_items:
                if self.tilemap.explored[item.gy][item.gx]:
                    item.render(self.screen, self.camera)

            # 6. Enemies
            for enemy in self.enemies:
                if self.tilemap.visible[enemy.grid_y][enemy.grid_x] or self.debug_mode or self.sprite_debug_mode:
                    enemy.render(self.screen, self.camera)

            # 7. Player
            self.player.render(self.screen, self.camera)

            # 8. Combat Visuals (Telegraph Warning Zones, Slash Arcs, Projectiles, Particles, Damage Numbers)
            self.combat_system.render_visuals(self.screen, self.camera, self.font_small, self.tilemap)

            # 9. HUD & Radar Minimap with special room icons
            self.hud.render(self.screen, self.player, self.current_floor)
            rooms = self.dungeon_gen.rooms if self.dungeon_gen else None
            self.minimap.render(self.screen, self.tilemap, self.player, self.enemies, self.boss, rooms=rooms,
                                camera=self.camera, floor=self.current_floor)

            # 10. Boss HP Bar (only while the encounter is on, never when just walking past)
            engaged = bool(self.boss_controller and self.boss_controller.state in (
                BossRoomState.ANNOUNCEMENT, BossRoomState.LOCKING, BossRoomState.FIGHTING))
            self.boss_bar.render(self.screen, self.boss, engaged=engaged)

            # 11. Boss Announcement Banner
            if self.boss_controller:
                self.boss_controller.render_announcement(self.screen, self.font_title, self.font_medium)

            # 12. Relic Hover Tooltips
            mouse_pos = pygame.mouse.get_pos()
            self.hud.render_relic_tooltips(self.screen, mouse_pos)

            # 13. Debug Overlays (F3 = General, F4 = Sprite Sheet Diagnostics)
            if self.debug_mode:
                self._draw_debug_overlay()
            if self.sprite_debug_mode:
                self._draw_sprite_debug_overlay()

            # 14. Modals & Overlays
            if self.npc_modal.is_active:
                self.npc_modal.render(self.screen, self.player)
            elif self.level_up_modal.is_active:
                self.level_up_modal.render(self.screen, self.player)
            elif self.inventory_ui.is_open:
                self.inventory_ui.render(self.screen, self.player)
            elif self.game_state == MenuState.PAUSED:
                self.menu_manager.render_pause_menu(self.screen)
            elif self.game_state == MenuState.GAME_OVER:
                self.menu_manager.render_game_over(self.screen, self.player, self.current_floor)
            elif self.game_state == MenuState.VICTORY:
                self.menu_manager.render_victory(self.screen, self.current_floor, self.player)

        elif self.game_state == MenuState.MAIN_MENU:
            self.menu_manager.render_main_menu(self.screen, self.seed)

        elif self.game_state == MenuState.CLASS_SELECT:
            self.menu_manager.render_class_select(self.screen)

        elif self.game_state == MenuState.RUN_CONFIG:
            self.menu_manager.render_run_config(self.screen)

        pygame.display.flip()

    def _draw_debug_overlay(self):
        fps = int(self.clock.get_fps())
        req_exp = LevelSystem.get_required_exp(self.player.level)
        wp = self.player.current_weapon
        wp_cd = f"{wp.cooldown:.2f}s" if wp else "0.00s"

        lines = [
            "ACTION ROGUELIKE DEBUG (F3)",
            f"FPS: {fps} | Floor: {self.current_floor}/10 | Score: {self.player.score}",
            f"Hero: {self.player.class_name} | Lv.{self.player.level} (EXP: {self.player.exp}/{req_exp})",
            f"Position: ({int(self.player.pos_x)}, {int(self.player.pos_y)}) [Grid: {self.player.grid_x}, {self.player.grid_y}]",
            f"Attack Cooldown: {wp_cd} | Can Attack: {self.player.can_attack()}",
            f"Stamina: {int(self.player.stamina)}/{int(self.player.max_stamina)} | Dashing: {self.player.is_dashing}",
            f"Boss State: {self.boss_controller.state if self.boss_controller else 'None'} | Gates: {self.boss_controller.gates_locked if self.boss_controller else False}",
            f"Relics ({len(self.player.relics)}): {[r.name for r in self.player.relics]}",
            f"Rooms Total: {len(self.dungeon_gen.rooms) if self.dungeon_gen else 0}"
        ]

        if self.boss and self.boss.is_alive:
            lines.append(f"Boss: {self.boss.name} | HP: {self.boss.current_hp}/{self.boss.max_hp} | Phase: {self.boss.phase}")

        box_h = len(lines) * 18 + 12
        overlay = pygame.Surface((440, box_h), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 220))
        pygame.draw.rect(overlay, (80, 160, 240), (0, 0, 440, box_h), 1)

        for idx, line in enumerate(lines):
            col = (255, 220, 80) if idx == 0 else (220, 220, 240)
            txt = self.font_small.render(line, True, col)
            overlay.blit(txt, (10, 6 + idx * 18))

        self.screen.blit(overlay, (12, SCREEN_HEIGHT - box_h - 12))

    def _draw_sprite_debug_overlay(self):
        panel = pygame.Surface((520, 360), pygame.SRCALPHA)
        panel.fill((15, 12, 25, 235))
        pygame.draw.rect(panel, (180, 100, 240), (0, 0, 520, 360), 2)

        t_title = self.font_title.render("SPRITE DIAGNOSTICS (F4)", True, (240, 200, 80))
        panel.blit(t_title, (16, 12))

        # Preview Tiles, Monsters, Items
        y_off = 50
        categories = [
            ("Classes", ["knight", "archer", "mage"]),
            ("Enemies", ["goblin", "skeleton", "orc", "archer_enemy", "mage_enemy"]),
            ("Weapons", ["short sword", "great sword", "spear", "short bow", "crystal staff", "flame sword"]),
            ("Potions", ["red potion", "blue potion", "bright green potion", "orange potion"])
        ]

        for cat_name, item_names in categories:
            lbl = self.font_small.render(cat_name + ":", True, (180, 180, 210))
            panel.blit(lbl, (16, y_off + 8))

            x_off = 110
            for iname in item_names:
                surf = self.sprite_loader.get_sprite(iname, dest_size=32)
                panel.blit(surf, (x_off, y_off))
                x_off += 38
            y_off += 44

        self.screen.blit(panel, (SCREEN_WIDTH // 2 - 260, SCREEN_HEIGHT // 2 - 180))

    def _sync_music(self):
        """Picks the background track from the game state; ducks it while a menu or modal is open."""
        state = self.game_state
        if state == MenuState.PLAYING or state == MenuState.PAUSED:
            boss_fight = bool(self.boss and self.boss.is_alive and self.boss_controller and
                              self.boss_controller.state in (BossRoomState.LOCKING, BossRoomState.FIGHTING))
            track = "boss" if boss_fight else "dungeon"
            ducked = (state == MenuState.PAUSED or self.inventory_ui.is_open
                      or self.level_up_modal.is_active or self.npc_modal.is_active)
        else:
            track, ducked = "menu", False
        self.music.update(track, ducked)
        self.menu_manager.music_on = self.music.enabled

    def run(self):
        while self.is_running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)  # Cap large delta spikes
            self.handle_events()
            self.update(dt)
            self.draw()

        pygame.quit()
        sys.exit()
