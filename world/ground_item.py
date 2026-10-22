import pygame
import math
from settings import TILE_SIZE
from core.sprite_loader import SpriteSheetLoader

class GroundItem:
    """
    Physical dropped loot item lying on a walkable grid tile (Gold, Weapons, Potions, Relics).
    Renders actual pixel-art sprites cropped directly from items.png / items.txt.
    """
    def __init__(self, gx: int, gy: int, loot_type: str, data):
        self.gx = int(gx)
        self.gy = int(gy)
        self.loot_type = loot_type  # "gold", "potion", "weapon", "relic"
        self.data = data
        self.is_picked_up = False
        self.hover_time = 0.0

        self.loader = SpriteSheetLoader()
        self.loader.initialize()

        # Cache actual item sprite from items.png
        self.sprite = self._resolve_sprite()

    def _resolve_sprite(self) -> pygame.Surface:
        if self.loot_type == "gold":
            return self.loader.get_sprite("coin", dest_size=TILE_SIZE)

        elif self.loot_type == "potion":
            p_name = getattr(self.data, "name", "Health Potion")
            return self.loader.get_sprite(p_name, dest_size=TILE_SIZE)

        elif self.loot_type == "weapon":
            w_name = getattr(self.data, "name", "Wooden Sword")
            return self.loader.get_sprite(w_name, dest_size=TILE_SIZE)

        elif self.loot_type == "relic":
            r_name = getattr(self.data, "name", "Flame Core")
            return self.loader.get_sprite(r_name, dest_size=TILE_SIZE)

        return self.loader.get_sprite("coin", dest_size=TILE_SIZE)

    def update(self, dt: float):
        self.hover_time += dt

    def render(self, surface: pygame.Surface, camera):
        if self.is_picked_up:
            return

        screen_x, screen_y = camera.apply_pos(self.gx * TILE_SIZE, self.gy * TILE_SIZE)
        bob = int(math.sin(self.hover_time * 4.0) * 2.0)

        # Draw subtle magical aura pedestal
        glow_surf = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(glow_surf, (255, 255, 200, 60), (12, 12), 11)
        surface.blit(glow_surf, (screen_x + 4, screen_y + 4 + bob))

        # Render true item sprite from items.png
        surface.blit(self.sprite, (screen_x, screen_y + bob))
