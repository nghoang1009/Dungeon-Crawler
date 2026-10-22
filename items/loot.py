import random
from items.potion import Potion, PotionType
from items.relic import AVAILABLE_RELICS
from combat.weapon import (
    create_iron_sword, create_great_sword,
    create_battle_axe, create_spear, create_trident, create_hunting_bow,
    create_elven_bow, create_apprentice_staff,
    create_magic_staff, create_legendary_blade, create_heavy_crossbow,
    create_repeater_gun
)

class LootTable:
    """
    Data-driven weighted random loot tables for Enemy drops, Normal Chests, and Treasure Chests.
    Drops physical ground items with distinct rarities (Common, Rare, Epic, Legendary).
    """
    @staticmethod
    def generate_enemy_loot(enemy_type: str, rng=None) -> list:
        r = rng if rng else random
        loot = []

        gold_ranges = {
            "goblin": (4, 12),
            "skeleton": (8, 18),
            "orc": (18, 35),
            "archer_enemy": (12, 22),
            "mage_enemy": (15, 28),
            "boss": (80, 150)
        }
        g_min, g_max = gold_ranges.get(enemy_type, (6, 15))
        loot.append(("gold", r.randint(g_min, g_max)))

        drop_chance = 0.35 if enemy_type != "boss" else 1.0
        if r.random() < drop_chance:
            potion_choices = [
                (Potion(PotionType.HEALTH, potency=40), 0.50),
                (Potion(PotionType.MANA, potency=35), 0.25),
                (Potion(PotionType.SPEED, potency=30, duration=12.0), 0.15),
                (Potion(PotionType.STRENGTH, potency=8, duration=12.0), 0.10)
            ]
            total_w = sum(w for _, w in potion_choices)
            val = r.uniform(0, total_w)
            cum = 0.0
            for item, weight in potion_choices:
                cum += weight
                if val <= cum:
                    loot.append(("potion", item))
                    break

        return loot

    @staticmethod
    def generate_chest_loot(is_treasure_room: bool = False, rng=None) -> list:
        r = rng if rng else random
        loot = []

        # 1. Gold
        gold_amt = r.randint(35, 75) if not is_treasure_room else r.randint(90, 180)
        loot.append(("gold", gold_amt))

        # 2. Potions
        pot_potency = 50 if is_treasure_room else 35
        loot.append(("potion", Potion(PotionType.HEALTH, potency=pot_potency)))

        if is_treasure_room or r.random() < 0.45:
            pot_type = r.choice([PotionType.SPEED, PotionType.STRENGTH, PotionType.MANA])
            loot.append(("potion", Potion(pot_type, potency=10, duration=15.0)))

        # 3. Weapons with Rarity Pools
        weapon_roll = r.random()
        if is_treasure_room or weapon_roll < 0.65:
            if is_treasure_room:
                pool = [create_great_sword, create_battle_axe, create_trident, create_elven_bow, create_magic_staff, create_repeater_gun, create_legendary_blade]
            else:
                pool = [create_iron_sword, create_spear, create_hunting_bow, create_heavy_crossbow, create_apprentice_staff, create_battle_axe]
            chosen_wp_func = r.choice(pool)
            loot.append(("weapon", chosen_wp_func()))

        # 4. Relics in Treasure Room
        if is_treasure_room and r.random() < 0.70:
            chosen_relic = r.choice(AVAILABLE_RELICS)()
            loot.append(("relic", chosen_relic))

        return loot


class BossLootTable:
    """
    Guarantees physical multi-item rewards on Boss defeat:
    Gold + High-tier Weapon + Health Potion + Guaranteed Relic Drop.
    """
    @staticmethod
    def generate_boss_loot(floor: int = 1, rng=None) -> list:
        r = rng if rng else random
        loot = []

        # 1. Guaranteed Gold scaled by Floor
        loot.append(("gold", r.randint(70 + floor * 15, 120 + floor * 25)))

        # 2. Guaranteed Weapon (Higher legendary chance on later floors)
        legendary_chance = 0.20 + (floor * 0.08)
        if r.random() < legendary_chance:
            loot.append(("weapon", create_legendary_blade()))
        else:
            pool = [create_great_sword, create_trident, create_battle_axe, create_elven_bow, create_magic_staff, create_repeater_gun, create_heavy_crossbow]
            loot.append(("weapon", r.choice(pool)()))

        # 3. Guaranteed Full Health Potion
        loot.append(("potion", Potion(PotionType.HEALTH, potency=100)))

        # 4. Guaranteed Relic Drop
        chosen_relic = r.choice(AVAILABLE_RELICS)()
        loot.append(("relic", chosen_relic))

        return loot
