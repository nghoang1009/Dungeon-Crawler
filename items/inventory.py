from items.item import Item
from items.potion import Potion
from combat.weapon import Weapon

class Inventory:
    """
    Manages player's held items, consumables, gold, and weapon switching.
    """
    def __init__(self, capacity: int = 25):
        self.capacity = capacity
        self.items: list[Item] = []
        self.weapons: list[Weapon] = []
        self.selected_index = 0

    def add_item(self, item: Item) -> bool:
        """Adds item to inventory, stacking if already present."""
        if item.stackable:
            for existing in self.items:
                if existing.name == item.name and existing.item_type == item.item_type:
                    existing.quantity += item.quantity
                    return True

        if len(self.items) < self.capacity:
            self.items.append(item)
            return True
        return False  # Inventory full

    def remove_item(self, index: int) -> Item | None:
        if 0 <= index < len(self.items):
            item = self.items[index]
            if item.quantity > 1:
                item.quantity -= 1
            else:
                self.items.pop(index)
            return item
        return None

    def remove_quantity(self, index: int, quantity: int) -> int:
        """Removes up to `quantity` units from the stack at index. Returns removed amount."""
        if not (0 <= index < len(self.items)):
            return 0
        item = self.items[index]
        removed = min(max(0, quantity), item.quantity)
        item.quantity -= removed
        if item.quantity <= 0:
            self.items.pop(index)
        return removed

    def use_item_at(self, index: int, player) -> bool:
        if 0 <= index < len(self.items):
            item = self.items[index]
            consumed = item.use(player)
            if consumed:
                if item.quantity > 1:
                    item.quantity -= 1
                else:
                    self.items.pop(index)
                return True
        return False

    def add_weapon(self, weapon: Weapon) -> bool:
        self.weapons.append(weapon)
        return True

    def remove_weapon(self, index: int) -> Weapon | None:
        if 0 <= index < len(self.weapons):
            weapon = self.weapons.pop(index)
            # Keep current_weapon_idx pointing at a valid weapon
            if self.selected_index >= len(self.weapons):
                self.selected_index = max(0, len(self.weapons) - 1)
            return weapon
        return None

    def get_potion_count(self, potion_type: str) -> int:
        total = 0
        for item in self.items:
            if isinstance(item, Potion) and item.potion_type == potion_type:
                total += item.quantity
        return total
