import pygame
from settings import TILE_SIZE, TILE_CLOSED_GATE, TILE_OPEN_GATE, SCREEN_WIDTH, COLOR_GOLD
from items.loot import BossLootTable
from world.ground_item import GroundItem

class BossRoomState:
    INACTIVE = "INACTIVE"
    ENTERING = "ENTERING"
    BOSS_SPAWNING = "BOSS_SPAWNING"
    ANNOUNCEMENT = "ANNOUNCEMENT"
    LOCKING = "LOCKING"
    FIGHTING = "FIGHTING"
    BOSS_DEFEATED = "BOSS_DEFEATED"
    COMPLETED = "COMPLETED"


class Gate:
    """
    Grid-based portcullis / gate placed at Boss room entrances.
    Locks only during active Boss encounter, and unlocks permanently upon victory.
    """
    def __init__(self, tx: int, ty: int, is_open: bool = True):
        self.tx = int(tx)
        self.ty = int(ty)
        self.is_open = is_open

    def lock(self, tilemap):
        self.is_open = False
        tilemap.set_tile(self.tx, self.ty, TILE_CLOSED_GATE)

    def unlock(self, tilemap):
        self.is_open = True
        tilemap.set_tile(self.tx, self.ty, TILE_OPEN_GATE)

    def render(self, surface: pygame.Surface, camera):
        screen_x, screen_y = camera.apply_pos(self.tx * TILE_SIZE, self.ty * TILE_SIZE)

        if not self.is_open:
            # Closed iron portcullis bars
            pygame.draw.rect(surface, (70, 65, 80), (screen_x + 2, screen_y + 2, TILE_SIZE - 4, TILE_SIZE - 4), border_radius=2)
            for ox in range(6, TILE_SIZE - 4, 6):
                pygame.draw.line(surface, (190, 45, 45), (screen_x + ox, screen_y + 4), (screen_x + ox, screen_y + TILE_SIZE - 4), 2)
            pygame.draw.line(surface, (190, 45, 45), (screen_x + 4, screen_y + TILE_SIZE // 2), (screen_x + TILE_SIZE - 4, screen_y + TILE_SIZE // 2), 2)
        else:
            # Open gate frame with green passage glow
            pygame.draw.rect(surface, (45, 42, 56), (screen_x, screen_y, TILE_SIZE, TILE_SIZE))
            pygame.draw.rect(surface, (60, 180, 80), (screen_x + 3, screen_y + 3, TILE_SIZE - 6, TILE_SIZE - 6), width=2, border_radius=2)


class BossRoomController:
    """
    Manages Boss Room State Machine:
    INACTIVE -> ENTERING -> BOSS_SPAWNING -> ANNOUNCEMENT -> LOCKING -> FIGHTING -> BOSS_DEFEATED -> COMPLETED.
    Guarantees gates only lock after Player is fully inside the room and Boss is announced.
    """
    def __init__(self, boss_room, gates: list[Gate]):
        self.boss_room = boss_room
        self.gates = gates
        self.state = BossRoomState.INACTIVE

        self.timer = 0.0
        self.announcement_text = ""
        self.announcement_sub = ""
        self.announcement_timer = 0.0

    @property
    def gates_locked(self) -> bool:
        return self.state in (BossRoomState.LOCKING, BossRoomState.FIGHTING)

    def is_tile_inside_boss_room(self, tx: int, ty: int) -> bool:
        """Checks if coordinate is inside Boss Room floor boundary (excluding outer walls)."""
        if not self.boss_room:
            return False
        return (self.boss_room.x < tx < self.boss_room.right - 1 and
                self.boss_room.y < ty < self.boss_room.bottom - 1)

    def is_pos_inside_boss_room(self, wx: float, wy: float, margin: float = 16.0) -> bool:
        """Checks if world pixel position is within Boss Room area."""
        if not self.boss_room:
            return False
        min_x = (self.boss_room.x + 1) * TILE_SIZE + margin
        max_x = (self.boss_room.right - 1) * TILE_SIZE - margin
        min_y = (self.boss_room.y + 1) * TILE_SIZE + margin
        max_y = (self.boss_room.bottom - 1) * TILE_SIZE - margin
        return (min_x <= wx <= max_x) and (min_y <= wy <= max_y)

    def clamp_boss_position(self, boss):
        """Strictly clamps Boss position and hitbox inside Boss Room bounds."""
        if not self.boss_room:
            return
        min_x = (self.boss_room.x + 1) * TILE_SIZE + boss.width // 2
        max_x = (self.boss_room.right - 1) * TILE_SIZE - boss.width // 2
        min_y = (self.boss_room.y + 1) * TILE_SIZE + boss.height // 2
        max_y = (self.boss_room.bottom - 1) * TILE_SIZE - boss.height // 2

        boss.pos_x = max(min_x, min(boss.pos_x, max_x))
        boss.pos_y = max(min_y, min(boss.pos_y, max_y))
        boss.sync_rect()

    def update(self, dt: float, player, boss, tilemap, sound_manager=None, camera=None):
        """State machine tick handling transitions."""
        if self.announcement_timer > 0:
            self.announcement_timer -= dt

        px, py = player.grid_x, player.grid_y
        player_inside = self.is_tile_inside_boss_room(px, py)

        if self.state == BossRoomState.INACTIVE:
            # Player enters the room threshold
            if player_inside:
                self.state = BossRoomState.ENTERING
                self.timer = 0.2

        elif self.state == BossRoomState.ENTERING:
            self.timer -= dt
            if self.timer <= 0 and player_inside:
                self.state = BossRoomState.BOSS_SPAWNING
                self.timer = 0.4
                if sound_manager:
                    sound_manager.play("boss_roar")
                if camera:
                    camera.add_shake(duration=0.5, magnitude=8.0)

        elif self.state == BossRoomState.BOSS_SPAWNING:
            self.timer -= dt
            if self.timer <= 0:
                self.state = BossRoomState.ANNOUNCEMENT
                self.announcement_text = boss.name.upper() if boss else "BOSS ENCOUNTER"
                self.announcement_sub = "--- BOSS ENCOUNTER STARTED ---"
                self.announcement_timer = 2.0
                self.timer = 1.2

        elif self.state == BossRoomState.ANNOUNCEMENT:
            self.timer -= dt
            # Lock gates only after announcement and confirming Player is fully inside
            if self.timer <= 0 and player_inside:
                self.state = BossRoomState.LOCKING
                for g in self.gates:
                    g.lock(tilemap)
                if sound_manager:
                    sound_manager.play("hit")
                if camera:
                    camera.add_shake(duration=0.25, magnitude=5.0)
                self.state = BossRoomState.FIGHTING

        elif self.state == BossRoomState.FIGHTING:
            if boss:
                self.clamp_boss_position(boss)

    def on_boss_death(self, boss_pos: tuple[int, int], tilemap, ground_items: list, sound_manager=None, camera=None):
        """Unlocks gates permanently and spawns physical ground loot (including Relic)."""
        self.state = BossRoomState.BOSS_DEFEATED

        for g in self.gates:
            g.unlock(tilemap)

        if sound_manager:
            sound_manager.play("levelup")
        if camera:
            camera.add_shake(duration=0.40, magnitude=7.0)

        self.announcement_text = "BOSS DEFEATED!"
        self.announcement_sub = "Gates are unlocked. Claim your rewards!"
        self.announcement_timer = 2.5

        # Spawn guaranteed loot items on free walkable tiles in Boss Room
        free_tiles = self.get_free_tiles_around(boss_pos, tilemap, count=5)
        loot_items = BossLootTable.generate_boss_loot()

        for idx, item_data in enumerate(loot_items):
            spawn_tile = free_tiles[idx] if idx < len(free_tiles) else boss_pos
            l_type, l_val = item_data
            ground_items.append(GroundItem(spawn_tile[0], spawn_tile[1], l_type, l_val))

        self.state = BossRoomState.COMPLETED

    def get_free_tiles_around(self, center_pos: tuple[int, int], tilemap, count: int = 5) -> list[tuple[int, int]]:
        """Finds valid walkable tiles inside Boss Room boundary."""
        cx, cy = center_pos
        found = []
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                tx, ty = cx + dx, cy + dy
                if (dx != 0 or dy != 0) and self.is_tile_inside_boss_room(tx, ty) and tilemap.is_walkable(tx, ty):
                    found.append((tx, ty))
                    if len(found) >= count:
                        return found
        return found if found else [center_pos]

    def render_announcement(self, surface: pygame.Surface, font_title: pygame.font.Font, font_body: pygame.font.Font):
        """Renders cinematic Boss appearance / defeat banner in top center."""
        if self.announcement_timer <= 0:
            return

        alpha = int(min(255, self.announcement_timer * 220))
        panel_w = 480
        panel_h = 64
        panel_x = (SCREEN_WIDTH - panel_w) // 2
        panel_y = 120

        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((20, 15, 28, min(230, alpha)))
        pygame.draw.rect(panel_surf, (220, 50, 40, alpha), (0, 0, panel_w, panel_h), 2, border_radius=6)

        t1 = font_title.render(self.announcement_text, True, COLOR_GOLD)
        t2 = font_body.render(self.announcement_sub, True, (240, 240, 250))

        if alpha < 255:
            t1.set_alpha(alpha)
            t2.set_alpha(alpha)

        panel_surf.blit(t1, ((panel_w - t1.get_width()) // 2, 8))
        panel_surf.blit(t2, ((panel_w - t2.get_width()) // 2, 36))
        surface.blit(panel_surf, (panel_x, panel_y))
