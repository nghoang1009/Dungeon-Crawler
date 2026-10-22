"""
Builds the game-ready sprites in assets/ from the raw art in spite/.

  python tools/build_assets.py

demo_dungeon.png was upscaled 6x from 17px tiles, so every tile is resampled back to its native
pixel grid first (one sample per 6x6 block) and then scaled to TILE_SIZE with nearest-neighbour.
boss1.png / boss2.png are 3-frame idle sheets (80px / 120px cells) scaled by 0.75 -> 60px / 90px.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from settings import TILE_SIZE  # noqa: E402

SRC = os.path.join(ROOT, "spite")
OUT = os.path.join(ROOT, "assets")

PX = 6                      # upscale factor of demo_dungeon.png
CELL = 102                  # one dungeon tile in demo_dungeon.png (17 native px)
COL0, ROW0 = 86, 283        # grid line origin of cell (0, 0)
BOSS_SCALE = 0.75


def native(src: pygame.Surface, x0: int, y0: int, cols: int, rows: int) -> pygame.Surface:
    """Samples a region of the 6x upscaled demo back down to its native pixel grid."""
    out = pygame.Surface((cols, rows), pygame.SRCALPHA)
    for j in range(rows):
        for i in range(cols):
            out.set_at((i, j), src.get_at((x0 + i * PX + PX // 2, y0 + j * PX + PX // 2)))
    return out


def cell_origin(k: int, j: int) -> tuple[int, int]:
    return COL0 + CELL * k, ROW0 + CELL * j


def tile_from_cell(src, k, j) -> pygame.Surface:
    x0, y0 = cell_origin(k, j)
    return pygame.transform.scale(native(src, x0, y0, 17, 17), (TILE_SIZE, TILE_SIZE))


def keep_aspect(surf: pygame.Surface, height: int) -> pygame.Surface:
    """Scales to `height` keeping aspect and centres it bottom-aligned on a TILE_SIZE square."""
    w = max(1, round(surf.get_width() * height / surf.get_height()))
    scaled = pygame.transform.scale(surf, (w, height))
    out = pygame.Surface((TILE_SIZE, TILE_SIZE), pygame.SRCALPHA)
    out.blit(scaled, ((TILE_SIZE - w) // 2, TILE_SIZE - height))
    return out


def strip_color(surf: pygame.Surface, is_bg) -> pygame.Surface:
    for y in range(surf.get_height()):
        for x in range(surf.get_width()):
            if is_bg(surf.get_at((x, y))):
                surf.set_at((x, y), (0, 0, 0, 0))
    return surf


def build_tiles(demo: pygame.Surface):
    tiles = {
        "floor_0": tile_from_cell(demo, 3, 3),
        "floor_skull": tile_from_cell(demo, 1, 1),
        "floor_crack_1": tile_from_cell(demo, 3, 0),
        "floor_crack_2": tile_from_cell(demo, 12, 0),
        "floor_crack_3": tile_from_cell(demo, 4, 4),
        "trap_up": tile_from_cell(demo, 6, 1),
        "trap_down": tile_from_cell(demo, 5, 1),
        "chest_closed": tile_from_cell(demo, 6, 2),
        # brick face with a lighter cap, taken from the top wall of the demo
        "wall_face": pygame.transform.scale(native(demo, 188, 73, 17, 17), (TILE_SIZE, TILE_SIZE)),
    }

    # Open chest: same chest with the lid replaced by a dark interior and a little gold.
    chest = tiles["chest_closed"].copy()
    inner = pygame.Rect(5, 10, TILE_SIZE - 10, 7)
    pygame.draw.rect(chest, (22, 12, 10), inner)
    for gx, gy in ((10, 14), (14, 13), (18, 14), (22, 13)):
        pygame.draw.rect(chest, (240, 190, 60), (gx, gy, 3, 2))
    tiles["chest_open"] = chest

    tiles["barrel"] = keep_aspect(native(demo, 86, 559, 16, 21), TILE_SIZE)

    pillar = native(demo, 98, 1, 13, 24)
    strip_color(pillar, lambda c: c.r + c.g + c.b < 24)
    tiles["pillar"] = keep_aspect(pillar, TILE_SIZE)
    return tiles


def build_bosses():
    bosses = {}
    for sheet, cell, names in (
        ("boss1.png", 80, ("teal_dragon", "red_dragon", "mech_crab", "void_horror")),
        ("boss2.png", 120, ("green_dragon", "golden_angel", "demon_lord", "abyss_maw")),
    ):
        img = pygame.image.load(os.path.join(SRC, sheet)).convert_alpha()
        size = round(cell * BOSS_SCALE)
        for row, name in enumerate(names):
            frames = []
            for col in range(3):
                frame = img.subsurface((col * cell, row * cell, cell, cell))
                frames.append(pygame.transform.scale(frame, (size, size)))
            bosses[name] = frames
    return bosses


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    os.makedirs(os.path.join(OUT, "tiles"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "bosses"), exist_ok=True)

    demo = pygame.image.load(os.path.join(SRC, "demo_dungeon.png")).convert_alpha()
    for name, surf in build_tiles(demo).items():
        pygame.image.save(surf, os.path.join(OUT, "tiles", f"{name}.png"))

    for name, frames in build_bosses().items():
        for i, frame in enumerate(frames):
            pygame.image.save(frame, os.path.join(OUT, "bosses", f"{name}_{i}.png"))
    print("assets built in", OUT)


if __name__ == "__main__":
    main()
