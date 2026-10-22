import pygame
from settings import TILE_SIZE
from core.sprite_loader import SpriteSheetLoader
from items.loot import LootTable
from world.ground_item import GroundItem

class Chest:
    """
    Grid-anchored Treasure chest.
    Opening spawns physical loot items on adjacent floor tiles (Gold, Potions, Weapons, Relics).
    Player must physically step over items to pick them up.
    """
    def __init__(self, tx: int, ty: int, is_treasure_room: bool = False):
        self.tx = int(tx)
        self.ty = int(ty)
        self.is_treasure_room = is_treasure_room
        self.is_opened = False

        self.x = self.tx * TILE_SIZE
        self.y = self.ty * TILE_SIZE
        self.rect = pygame.Rect(self.x + 2, self.y + 2, TILE_SIZE - 4, TILE_SIZE - 4)

        self.loader = SpriteSheetLoader()
        self.loader.initialize()

    def interact(self, player, sound_manager=None, combat_system=None, ground_items=None, tilemap=None) -> list:
        if self.is_opened:
            return []

        self.is_opened = True
        if sound_manager:
            sound_manager.play("chest")

        loot = LootTable.generate_chest_loot(self.is_treasure_room)

        # Physical floor drop around chest
        if ground_items is not None:
            offsets = [(0, 1), (1, 0), (0, -1), (-1, 0), (1, 1), (-1, 1)]
            for idx, (loot_type, val) in enumerate(loot):
                ox, oy = offsets[idx % len(offsets)]
                drop_x, drop_y = self.tx + ox, self.ty + oy
                if tilemap and not tilemap.is_walkable(drop_x, drop_y):
                    drop_x, drop_y = self.tx, self.ty
                ground_items.append(GroundItem(drop_x, drop_y, loot_type, val))

        return loot

    def render(self, surface: pygame.Surface, camera):
        screen_x, screen_y = camera.apply_pos(self.x, self.y)
        chest_surf = self.loader.get_tile_chest(self.is_opened)
        surface.blit(chest_surf, (screen_x, screen_y))
