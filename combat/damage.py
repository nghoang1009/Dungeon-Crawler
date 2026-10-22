import pygame
import random
from settings import (
    COLOR_WHITE
)

class DamageNumber:
    """Floating combat text showing dealt damage or status."""
    def __init__(self, x: float, y: float, text: str, color: tuple[int, int, int] = COLOR_WHITE, is_crit: bool = False):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.is_crit = is_crit
        self.lifetime = 0.8
        self.age = 0.0
        self.vel_y = -45.0  # Float upward
        self.vel_x = random.uniform(-15.0, 15.0)

    def update(self, dt: float):
        self.age += dt
        self.x += self.vel_x * dt
        self.y += self.vel_y * dt
        self.vel_y += 35.0 * dt  # Decelerate upward float

    @property
    def is_alive(self) -> bool:
        return self.age < self.lifetime

    def render(self, surface: pygame.Surface, camera, font: pygame.font.Font):
        screen_x, screen_y = camera.apply_pos(self.x, self.y)
        alpha = int(255 * (1.0 - (self.age / self.lifetime)))

        txt_surf = font.render(self.text, True, self.color)
        if alpha < 255:
            txt_surf.set_alpha(alpha)

        # Draw shadow
        shadow_surf = font.render(self.text, True, (0, 0, 0))
        if alpha < 255:
            shadow_surf.set_alpha(alpha)

        surface.blit(shadow_surf, (screen_x + 1, screen_y + 1))
        surface.blit(txt_surf, (screen_x, screen_y))
