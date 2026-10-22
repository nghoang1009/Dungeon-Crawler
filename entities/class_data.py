from combat.weapon import create_wooden_sword, create_hunting_bow, create_apprentice_staff, Weapon

class ClassData:
    """
    Hero archetype attributes, base stats, initial weapon, and playstyle description.
    """
    def __init__(self,
                 name: str,
                 max_hp: int,
                 attack: int,
                 defense: int,
                 speed: float,
                 starter_weapon_func,
                 description: str,
                 color: tuple[int, int, int],
                 uses_mana: bool = False,
                 max_mana: int = 0,
                 mana_regen: float = 0.0):
        self.name = name
        self.max_hp = max_hp
        self.attack = attack
        self.defense = defense
        self.speed = speed
        self.starter_weapon_func = starter_weapon_func
        self.description = description
        self.color = color
        self.uses_mana = uses_mana
        self.max_mana = max_mana
        self.mana_regen = mana_regen

    def create_starter_weapon(self) -> Weapon:
        return self.starter_weapon_func()


# 3 Core Hero Classes
KNIGHT_CLASS = ClassData(
    name="Knight",
    max_hp=150,
    attack=12,
    defense=6,
    speed=140.0,
    starter_weapon_func=create_wooden_sword,
    description="Melee Tank. High HP, heavy armor, close-range slash.",
    color=(65, 115, 210)
)

ARCHER_CLASS = ClassData(
    name="Archer",
    max_hp=95,
    attack=18,
    defense=2,
    speed=165.0,
    starter_weapon_func=create_hunting_bow,
    description="Ranged DPS. High speed, deadly arrows, long range.",
    color=(45, 160, 75)
)

MAGE_CLASS = ClassData(
    name="Mage",
    max_hp=80,
    attack=24,
    defense=1,
    speed=145.0,
    starter_weapon_func=create_apprentice_staff,
    description="Magic Ranged. Destructive arcane bolts, high burst damage.",
    color=(135, 60, 200),
    uses_mana=True,
    max_mana=100,
    mana_regen=4.0
)

AVAILABLE_CLASSES = [KNIGHT_CLASS, ARCHER_CLASS, MAGE_CLASS]
