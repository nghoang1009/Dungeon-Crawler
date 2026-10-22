import json
import os

from entities.class_data import KNIGHT_CLASS, ARCHER_CLASS, MAGE_CLASS
from entities.player import Player
from items.potion import Potion, PotionType
from combat.weapon import Weapon, WeaponCategory, WeaponRarity
from progression.level_system import LevelSystem

CLASS_BY_NAME = {
    "Knight": KNIGHT_CLASS,
    "Archer": ARCHER_CLASS,
    "Mage": MAGE_CLASS,
}


class SaveManager:
    """
    JSON-based persistent saving and loading for character progression and dungeon state.
    Saves mana, full inventory (stack quantities) and weapons; loading tolerates old
    save files without mana fields by falling back to safe class defaults.
    """
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SAVE_FILE = os.environ.get("DUNGEON_SAVE_FILE") or os.path.join(BASE_DIR, "save_data.json")

    @classmethod
    def save_game(cls, player, dungeon_seed: int, dungeon_floor: int, difficulty: str,
                  dungeon_state: dict | None = None) -> bool:
        try:
            data = {
                "player": {
                    "class_name": player.class_name,
                    "name": getattr(player, "name", "Hero"),
                    "level": player.level,
                    "exp": player.exp,
                    "exp_to_next": LevelSystem.get_required_exp(player.level),
                    "gold": player.gold,
                    "max_hp": player.max_hp,
                    "current_hp": player.current_hp,
                    "uses_mana": player.uses_mana,
                    "max_mana": player.max_mana,
                    "mana": player.mana,
                    "mana_regen": player.mana_regen,
                    "attack_power": player.attack_power,
                    "defense": player.defense,
                    "speed": player.speed,
                    "current_weapon_idx": player.current_weapon_idx,
                    "inventory_items": [
                        {
                            "name": it.name,
                            "type": it.item_type,
                            "qty": it.quantity,
                            "potion_type": getattr(it, "potion_type", None),
                            "potency": getattr(it, "potency", None),
                            "duration": getattr(it, "duration", None)
                        }
                        for it in player.inventory.items
                    ],
                    "weapons": [
                        {
                            "name": wp.name,
                            "id": wp.id,
                            "dmg": wp.base_damage,
                            "rarity": wp.rarity,
                            "upg": wp.upgrade_level,
                            "attack_speed": wp.attack_speed,
                            "range_px": wp.range_px,
                            "arc_angle": wp.arc_angle,
                            "crit_chance": wp.crit_chance,
                            "weapon_category": wp.weapon_category,
                            "projectile_type": wp.projectile_type,
                            "sprite_name": wp.sprite_name
                        }
                        for wp in player.inventory.weapons
                    ]
                },
                "player_pos": [player.grid_x, player.grid_y],
                "dungeon_state": dungeon_state,
                "dungeon_seed": dungeon_seed,
                "dungeon_floor": dungeon_floor,
                "difficulty": difficulty
            }
            with open(cls.SAVE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print("[SaveManager] Game saved successfully.")
            return True
        except Exception as e:
            print(f"[SaveManager] Failed to save: {e}")
            return False

    @classmethod
    def collect_dungeon_state(cls, game) -> dict:
        """
        Snapshots the live dungeon progress so loading resumes the played dungeon
        (explored fog, room states, opened chests, boss defeat) instead of just
        regenerating a fresh map from the seed.
        """
        rooms_data = []
        for r in game.dungeon_gen.rooms:
            rooms_data.append({
                "room_id": r.room_id,
                "type": r.room_type,
                "state": r.state,
                "is_cleared": r.is_cleared,
                "has_visited": r.has_visited,
                "reward_spawned": r.reward_spawned
            })

        explored_rows = [
            "".join("1" if t else "0" for t in row)
            for row in game.tilemap.explored
        ]

        return {
            "rooms": rooms_data,
            "explored_rows": explored_rows,
            "chests_opened": [c.is_opened for c in game.chests],
            "boss_defeated": bool(game.boss_controller and
                                  game.boss_controller.state == "COMPLETED")
        }

    @classmethod
    def load_game(cls) -> dict | None:
        if not os.path.exists(cls.SAVE_FILE):
            return None
        try:
            with open(cls.SAVE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SaveManager] Failed to load: {e}")
            return None

    @classmethod
    def create_player_from_save(cls, data: dict) -> Player | None:
        """
        Rebuilds the Player from save data. Every field is read through .get() with
        safe defaults, so old save files (no mana / no class_name / bare items) load
        without errors.
        """
        if not data or "player" not in data:
            return None
        try:
            p_data = data["player"]

            # Class resolution: explicit name, else infer from legacy mana fields
            class_name = p_data.get("class_name")
            class_data = CLASS_BY_NAME.get(class_name)
            if class_data is None:
                if p_data.get("max_mana", 0) and p_data.get("max_mana", 0) > 0:
                    class_data = MAGE_CLASS
                else:
                    class_data = KNIGHT_CLASS

            grid_x = p_data.get("grid_x", 2)
            grid_y = p_data.get("grid_y", 2)
            player = Player(grid_x, grid_y, class_data)
            player.name = p_data.get("name", "Hero")

            player.level = p_data.get("level", 1)
            player.exp = p_data.get("exp", 0)
            player.gold = p_data.get("gold", 0)
            player.max_hp = p_data.get("max_hp", class_data.max_hp)
            player.current_hp = p_data.get("current_hp", player.max_hp)
            player.attack_power = p_data.get("attack_power", class_data.attack)
            player.defense = p_data.get("defense", class_data.defense)
            player.speed = p_data.get("speed", class_data.speed)

            # Mana: old saves without these fields fall back to the class defaults
            player.uses_mana = p_data.get("uses_mana", class_data.uses_mana)
            player.max_mana = p_data.get("max_mana", class_data.max_mana)
            player.mana = min(float(p_data.get("mana", player.max_mana)), float(player.max_mana))
            player.mana_regen = p_data.get("mana_regen", class_data.mana_regen)

            # Inventory items (potions reconstructed by potion_type; other types by name)
            player.inventory.items = []
            for it in p_data.get("inventory_items", []):
                qty = max(1, int(it.get("qty", 1)))
                if it.get("type") == "POTION" or it.get("potion_type"):
                    pot_type = it.get("potion_type", PotionType.HEALTH)
                    item = Potion(pot_type,
                                  potency=int(it.get("potency", 30)),
                                  duration=float(it.get("duration", 0.0)))
                else:
                    from items.item import Item
                    item = Item(it.get("name", "Unknown"), it.get("type", "ITEM"))
                item.quantity = qty
                player.inventory.items.append(item)

            # Weapons reconstructed from their saved data fields
            player.inventory.weapons = []
            for w in p_data.get("weapons", []):
                weapon = Weapon(
                    id=w.get("id", w.get("name", "weapon").lower().replace(" ", "_")),
                    name=w.get("name", "Weapon"),
                    damage=int(w.get("dmg", 10)),
                    attack_speed=float(w.get("attack_speed", 2.0)),
                    range_px=float(w.get("range_px", 48.0)),
                    arc_angle=float(w.get("arc_angle", 110.0)),
                    crit_chance=float(w.get("crit_chance", 0.10)),
                    weapon_category=w.get("weapon_category", WeaponCategory.SWORD),
                    rarity=w.get("rarity", WeaponRarity.COMMON),
                    upgrade_level=int(w.get("upg", 0)),
                    projectile_type=w.get("projectile_type", "arrow"),
                    sprite_name=w.get("sprite_name")
                )
                player.inventory.weapons.append(weapon)

            if not player.inventory.weapons:
                player.inventory.add_weapon(class_data.create_starter_weapon())
            player.current_weapon_idx = 0
            if 0 <= p_data.get("current_weapon_idx", 0) < len(player.inventory.weapons):
                player.current_weapon_idx = p_data.get("current_weapon_idx", 0)

            return player
        except Exception as e:
            print(f"[SaveManager] Failed to reconstruct player: {e}")
            return None
