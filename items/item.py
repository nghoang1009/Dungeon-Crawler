
class ItemType:
    POTION = "POTION"
    WEAPON = "WEAPON"
    GOLD = "GOLD"
    KEY = "KEY"

class Item:
    """Base class for all inventory items and world pickups."""
    def __init__(self, name: str, item_type: str, description: str = "", icon_color: tuple[int, int, int] = (200, 200, 200)):
        self.name = name
        self.item_type = item_type
        self.description = description
        self.icon_color = icon_color
        self.stackable = True
        self.quantity = 1

    def use(self, player) -> bool:
        """Override to implement usage effects. Returns True if item consumed."""
        return False

    def __repr__(self) -> str:
        return f"{self.name} x{self.quantity}" if self.quantity > 1 else self.name
