from settings import (
    COLOR_COMMON, COLOR_UNCOMMON, COLOR_RARE, COLOR_EPIC, COLOR_LEGENDARY
)

class WeaponCategory:
    SWORD = "SWORD"
    GREATSWORD = "GREATSWORD"
    AXE = "AXE"
    SPEAR = "SPEAR"
    BOW = "BOW"
    STAFF = "STAFF"
    CROSSBOW = "CROSSBOW"
    GUN = "GUN"


class WeaponRarity:
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"

    COLORS = {
        COMMON: COLOR_COMMON,
        UNCOMMON: COLOR_UNCOMMON,
        RARE: COLOR_RARE,
        EPIC: COLOR_EPIC,
        LEGENDARY: COLOR_LEGENDARY
    }


class Weapon:
    """
    Data-driven Weapon class supporting distinct archetypes:
    - SWORD: 1 tile range (~48px), balanced attack speed, medium cleave arc (110 deg)
    - GREATSWORD: High damage, slower swing, wide cleave arc (160 deg), large range (~68px)
    - AXE: Heavy chop damage, high crit chance, medium arc (90 deg)
    - SPEAR: Long thrust range (~80px, 2.5 tiles), narrow thrust angle (40 deg), rapid thrusts
    - BOW: Long range projectile (arrow), high speed, piercing/critical potential
    - STAFF: Magic bolt with small AoE blast explosion on impact
    """
    def __init__(self,
                 id: str,
                 name: str,
                 damage: int,
                 attack_speed: float = 2.0,
                 range_px: float = 48.0,
                 arc_angle: float = 110.0,
                 crit_chance: float = 0.10,
                 weapon_category: str = WeaponCategory.SWORD,
                 rarity: str = WeaponRarity.COMMON,
                 upgrade_level: int = 0,
                 projectile_type: str = "arrow",
                 area_radius: float = 0.0,
                 special_effect: str | None = None,
                 sprite_name: str | None = None):
        self.id = id
        self.name = name
        self.base_damage = damage
        self.attack_speed = attack_speed
        self.range_px = range_px
        self.arc_angle = arc_angle
        self.crit_chance = crit_chance
        self.weapon_category = weapon_category
        self.rarity = rarity
        self.upgrade_level = upgrade_level
        self.projectile_type = projectile_type
        self.area_radius = area_radius
        self.special_effect = special_effect
        self.sprite_name = sprite_name if sprite_name else name

        self.cooldown = 0.0

    @property
    def is_ranged(self) -> bool:
        return self.weapon_category in (
            WeaponCategory.BOW, WeaponCategory.STAFF,
            WeaponCategory.CROSSBOW, WeaponCategory.GUN
        )

    @property
    def total_damage(self) -> int:
        rarity_mult = {
            WeaponRarity.COMMON: 1.0,
            WeaponRarity.UNCOMMON: 1.25,
            WeaponRarity.RARE: 1.6,
            WeaponRarity.EPIC: 2.0,
            WeaponRarity.LEGENDARY: 2.8
        }.get(self.rarity, 1.0)

        dmg = int(self.base_damage * rarity_mult + (self.upgrade_level * 3))
        return max(1, dmg)

    @property
    def display_name(self) -> str:
        if self.upgrade_level > 0:
            return f"{self.name} +{self.upgrade_level}"
        return self.name

    @property
    def rarity_color(self) -> tuple[int, int, int]:
        return WeaponRarity.COLORS.get(self.rarity, (200, 200, 200))

    def update(self, dt: float):
        if self.cooldown > 0:
            self.cooldown -= dt

    def can_attack(self) -> bool:
        return self.cooldown <= 0

    def trigger_attack(self):
        self.cooldown = 1.0 / max(0.1, self.attack_speed)

    def upgrade(self) -> bool:
        self.upgrade_level += 1
        return True


# Data-Driven Weapon Factory Functions
def create_wooden_sword() -> Weapon:
    return Weapon(
        id="wooden_sword",
        name="Wooden Sword",
        damage=10,
        attack_speed=2.2,
        range_px=48.0,
        arc_angle=110.0,
        crit_chance=0.08,
        weapon_category=WeaponCategory.SWORD,
        rarity=WeaponRarity.COMMON,
        sprite_name="short sword"
    )

def create_iron_sword() -> Weapon:
    return Weapon(
        id="iron_sword",
        name="Iron Sword",
        damage=16,
        attack_speed=2.2,
        range_px=52.0,
        arc_angle=115.0,
        crit_chance=0.12,
        weapon_category=WeaponCategory.SWORD,
        rarity=WeaponRarity.UNCOMMON,
        sprite_name="long sword"
    )

def create_great_sword() -> Weapon:
    return Weapon(
        id="great_sword",
        name="Titan Greatsword",
        damage=34,
        attack_speed=1.2,
        range_px=68.0,
        arc_angle=160.0,
        crit_chance=0.18,
        weapon_category=WeaponCategory.GREATSWORD,
        rarity=WeaponRarity.RARE,
        sprite_name="great sword"
    )

def create_battle_axe() -> Weapon:
    return Weapon(
        id="battle_axe",
        name="Battle Axe",
        damage=28,
        attack_speed=1.5,
        range_px=50.0,
        arc_angle=100.0,
        crit_chance=0.25,
        weapon_category=WeaponCategory.AXE,
        rarity=WeaponRarity.RARE,
        sprite_name="battle axe"
    )

def create_spear() -> Weapon:
    return Weapon(
        id="steel_spear",
        name="Steel Spear",
        damage=20,
        attack_speed=2.4,
        range_px=80.0,
        arc_angle=45.0,
        crit_chance=0.15,
        weapon_category=WeaponCategory.SPEAR,
        rarity=WeaponRarity.UNCOMMON,
        sprite_name="spear"
    )

def create_trident() -> Weapon:
    return Weapon(
        id="trident",
        name="Abyssal Trident",
        damage=28,
        attack_speed=2.5,
        range_px=85.0,
        arc_angle=50.0,
        crit_chance=0.20,
        weapon_category=WeaponCategory.SPEAR,
        rarity=WeaponRarity.EPIC,
        sprite_name="trident"
    )

def create_hunting_bow() -> Weapon:
    return Weapon(
        id="hunting_bow",
        name="Hunting Bow",
        damage=18,
        attack_speed=1.6,
        range_px=360.0,
        crit_chance=0.18,
        weapon_category=WeaponCategory.BOW,
        rarity=WeaponRarity.COMMON,
        projectile_type="arrow",
        sprite_name="short bow"
    )

def create_elven_bow() -> Weapon:
    return Weapon(
        id="elven_bow",
        name="Elven Longbow",
        damage=30,
        attack_speed=1.9,
        range_px=420.0,
        crit_chance=0.28,
        weapon_category=WeaponCategory.BOW,
        rarity=WeaponRarity.RARE,
        projectile_type="arrow",
        sprite_name="long bow"
    )

def create_apprentice_staff() -> Weapon:
    return Weapon(
        id="apprentice_staff",
        name="Apprentice Staff",
        damage=22,
        attack_speed=1.3,
        range_px=320.0,
        crit_chance=0.15,
        weapon_category=WeaponCategory.STAFF,
        rarity=WeaponRarity.COMMON,
        projectile_type="magic_bolt",
        area_radius=20.0,
        sprite_name="crystal staff"
    )

def create_magic_staff() -> Weapon:
    return Weapon(
        id="magic_staff",
        name="Archmage Staff",
        damage=38,
        attack_speed=1.5,
        range_px=380.0,
        crit_chance=0.24,
        weapon_category=WeaponCategory.STAFF,
        rarity=WeaponRarity.EPIC,
        projectile_type="magic_bolt",
        area_radius=28.0,
        sprite_name="blue staff"
    )

def create_legendary_blade() -> Weapon:
    return Weapon(
        id="excalibur",
        name="Excalibur",
        damage=58,
        attack_speed=2.6,
        range_px=72.0,
        arc_angle=130.0,
        crit_chance=0.35,
        weapon_category=WeaponCategory.SWORD,
        rarity=WeaponRarity.LEGENDARY,
        special_effect="burn",
        sprite_name="flame sword"
    )

def create_heavy_crossbow() -> Weapon:
    return Weapon(
        id="heavy_crossbow",
        name="Heavy Crossbow",
        damage=26,
        attack_speed=1.5,
        range_px=400.0,
        crit_chance=0.22,
        weapon_category=WeaponCategory.CROSSBOW,
        rarity=WeaponRarity.UNCOMMON,
        projectile_type="bolt",
        sprite_name="crossbow"
    )

def create_repeater_gun() -> Weapon:
    return Weapon(
        id="repeater_gun",
        name="Arcane Repeater",
        damage=18,
        attack_speed=3.2,
        range_px=360.0,
        crit_chance=0.18,
        weapon_category=WeaponCategory.GUN,
        rarity=WeaponRarity.RARE,
        projectile_type="bullet",
        sprite_name="large crossbow"
    )
