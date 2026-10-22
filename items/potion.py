from items.item import Item, ItemType

class PotionType:
    HEALTH = "HEALTH"
    MANA = "MANA"
    SPEED = "SPEED"
    STRENGTH = "STRENGTH"


class Potion(Item):
    """Consumable potion providing instantaneous recovery or timed stat buffs."""
    def __init__(self, potion_type: str, potency: int = 30, duration: float = 0.0):
        self.potion_type = potion_type
        self.potency = potency
        self.duration = duration

        names = {
            PotionType.HEALTH: "Health Potion",
            PotionType.MANA: "Mana Potion",
            PotionType.SPEED: "Speed Potion",
            PotionType.STRENGTH: "Strength Potion"
        }
        descs = {
            PotionType.HEALTH: f"Restores {potency} HP.",
            PotionType.MANA: f"Restores {potency} Mana.",
            PotionType.SPEED: f"Increases Speed by {potency}% for {int(duration)}s.",
            PotionType.STRENGTH: f"Increases Attack by +{potency} for {int(duration)}s."
        }
        colors = {
            PotionType.HEALTH: (230, 50, 50),
            PotionType.MANA: (50, 120, 240),
            PotionType.SPEED: (50, 220, 180),
            PotionType.STRENGTH: (240, 140, 40)
        }
        sprite_names = {
            PotionType.HEALTH: "red potion",
            PotionType.MANA: "blue potion",
            PotionType.SPEED: "bright green potion",
            PotionType.STRENGTH: "orange potion"
        }

        super().__init__(
            name=names.get(potion_type, "Potion"),
            item_type=ItemType.POTION,
            description=descs.get(potion_type, ""),
            icon_color=colors.get(potion_type, (200, 200, 200))
        )
        self.potion_sprite_name = sprite_names.get(potion_type, "purple potion")

    @property
    def sprite_name(self) -> str:
        return self.potion_sprite_name

    @property
    def rarity(self) -> str:
        return "COMMON"

    @property
    def effect_text(self) -> str:
        if self.potion_type == PotionType.HEALTH:
            return f"Restores {self.potency} HP instantly."
        if self.potion_type == PotionType.MANA:
            return f"Restores {self.potency} MP instantly."
        if self.potion_type in (PotionType.SPEED, PotionType.STRENGTH):
            return f"Lasts {int(self.duration)}s."
        return self.description

    def use(self, player) -> bool:
        """Executes potion effect on player."""
        if self.potion_type == PotionType.HEALTH:
            if player.current_hp >= player.max_hp:
                return False  # Already full HP
            player.heal(self.potency)
            return True

        elif self.potion_type == PotionType.MANA:
            # Only classes that actually use mana can drink a Mana Potion.
            if not getattr(player, "uses_mana", False):
                return False
            if player.mana >= player.max_mana:
                return False  # Already full MP
            player.restore_mana(self.potency)
            return True

        elif self.potion_type == PotionType.SPEED:
            player.apply_buff("speed", boost=self.potency / 100.0, duration=self.duration)
            return True

        elif self.potion_type == PotionType.STRENGTH:
            player.apply_buff("strength", boost=self.potency, duration=self.duration)
            return True

        return False
