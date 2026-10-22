import pygame
import random
from settings import TILE_SIZE
from core.sprite_loader import SpriteSheetLoader
from items.potion import Potion, PotionType

class ObstacleType:
    BARREL = "barrel"
    PILLAR = "pillar"


class Obstacle:
    """
    Physical world obstacle providing cover and collision.
    Renders direct pixel-art sprites from tiles.png (18.e barrel, 19.a rock/pillar).
    """
    def __init__(self, tx: int, ty: int, obstacle_type: str = ObstacleType.BARREL):
        self.tx = int(tx)
        self.ty = int(ty)
        self.obstacle_type = obstacle_type

        self.x = self.tx * TILE_SIZE
        self.y = self.ty * TILE_SIZE
        self.rect = pygame.Rect(self.x + 2, self.y + 2, TILE_SIZE - 4, TILE_SIZE - 4)

        self.destructible = (obstacle_type == ObstacleType.BARREL)
        self.max_hp = 20 if self.destructible else 99999
        self.current_hp = self.max_hp
        self.is_alive = True

        loader = SpriteSheetLoader()
        loader.initialize()
        if obstacle_type == ObstacleType.BARREL:
            self.surface = loader.get_tile_barrel()
        else:
            self.surface = loader.get_tile_pillar()

    def take_damage(self, amount: int):
        if not self.destructible or not self.is_alive:
            return

        self.current_hp -= amount
        if self.current_hp <= 0:
            self.is_alive = False

    def get_drops(self) -> list:
        if not self.destructible:
            return []

        roll = random.random()
        drops = []

        if roll < 0.25:
            gold_amount = random.randint(1, 3)
            drops.append(("gold", gold_amount))
        elif roll < 0.35:
            p_type = PotionType.HEALTH if random.random() < 0.7 else PotionType.MANA
            drops.append(("potion", Potion(p_type, potency=30)))

        return drops

    def render(self, surface: pygame.Surface, camera):
        if not self.is_alive:
            return

        screen_x, screen_y = camera.apply_pos(self.x, self.y)
        surface.blit(self.surface, (screen_x, screen_y))
