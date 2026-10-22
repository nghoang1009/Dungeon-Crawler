"""
Entry point for 2D Dungeon Crawler Roguelike.
Run directly with: python main.py
"""
from core.game import Game

def main():
    game = Game()
    game.run()

if __name__ == "__main__":
    main()
