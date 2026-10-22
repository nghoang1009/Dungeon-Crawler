"""Background music: right track per game state, ducking, mute toggle (headless dummy audio)."""
import sys, tempfile, os
sys.stdout.reconfigure(encoding="utf-8")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ.setdefault("DUNGEON_SAVE_FILE", os.path.join(tempfile.gettempdir(), "dungeon_test_save.json"))

import pygame

pygame.init()
pygame.display.set_mode((1024, 768))

from core.game import Game
from core.music import BASE_VOLUME, DUCKED_VOLUME
from ui.menu import MenuState
from world.gate import BossRoomState

fails = []
def check(name, cond, extra=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

check("3 file nhạc có sẵn", all(os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                              "assets", "music", f"{n}.wav"))
                                for n in ("menu", "dungeon", "boss")))

game = Game()
check("Mixer khởi tạo", game.music.available)
game.draw()
check("Menu chính phát nhạc menu", game.music.current == "menu" and pygame.mixer.music.get_busy())

game.menu_manager.selected_class_idx = 0
game.start_new_game(555)
game.draw()
check("Vào dungeon -> nhạc dungeon", game.music.current == "dungeon")

game.boss_controller.state = BossRoomState.FIGHTING
game.draw()
check("Đánh boss -> nhạc boss", game.music.current == "boss")
game.boss_controller.state = BossRoomState.BOSS_DEFEATED
game.draw()
check("Hạ boss -> về nhạc dungeon", game.music.current == "dungeon")

game.game_state = MenuState.PAUSED
game.draw()
check("Pause -> nhạc nhỏ lại", abs(pygame.mixer.music.get_volume() - DUCKED_VOLUME) < 0.02)
game.game_state = MenuState.PLAYING
game.draw()
check("Hết pause -> nhạc to lại", abs(pygame.mixer.music.get_volume() - BASE_VOLUME) < 0.02)

# Toggle by key and by the pause-menu button
game.handle_events()
pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_n, mod=0, unicode="n", scancode=0))
game.handle_events()
game.draw()
check("Phím N tắt nhạc", game.music.enabled is False and pygame.mixer.music.get_volume() == 0.0)

game.game_state = MenuState.PAUSED
game.draw()
btn = next(b for b in game.menu_manager.buttons_for(MenuState.PAUSED) if b.action == "music")
check("Nút MUSIC hiện trạng thái OFF", "OFF" in btn.label, btn.label)
pygame.event.clear()
pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=btn.rect.center, button=1))
game.handle_events()
game.draw()
check("Click nút MUSIC bật lại nhạc", game.music.enabled is True)

game.game_state = MenuState.GAME_OVER
game.draw()
check("Game over -> nhạc menu", game.music.current == "menu")

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED")
sys.exit(1 if fails else 0)
