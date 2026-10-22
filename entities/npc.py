import pygame
import random
from core.sprite_loader import SpriteSheetLoader
from items.potion import Potion, PotionType
from items.relic import AVAILABLE_RELICS
from combat.weapon import create_great_sword, create_elven_bow, create_spear

class NPCStyle:
    MERCHANT = "MERCHANT"
    BLACKSMITH = "BLACKSMITH"
    HEALER = "HEALER"
    RELIC_TRADER = "RELIC_TRADER"
    RESCUE = "RESCUE"
    EVENT_SHRINE = "EVENT_SHRINE"


class TradeOption:
    def __init__(self, text: str, cost_gold: int, action_type: str, param=None, stock: int = 1):
        self.text = text
        self.cost_gold = cost_gold
        self.action_type = action_type  # "heal", "upgrade_weapon", "buy_potion", "buy_weapon", "buy_relic", "free_gift"
        self.param = param
        self.stock = stock

    @property
    def is_sold_out(self) -> bool:
        return self.stock <= 0


class NPC:
    """
    Interactive Non-Player Character in Safe NPC Rooms and Rescue Rooms.
    Supports Blacksmith (upgrades), Merchant (gear/potions), Healer (HP recovery),
    Relic Trader (relics), and Trapped Hostages (rescue for rewards).
    Enforces limited inventory stock with SOLD OUT state and strict gold checks.
    """
    def __init__(self, grid_x: int, grid_y: int, npc_type: str = NPCStyle.MERCHANT, is_trapped: bool = False):
        self.grid_x = int(grid_x)
        self.grid_y = int(grid_y)
        self.npc_type = npc_type
        self.is_trapped = is_trapped
        self.is_rescued = not is_trapped
        self.is_alive = True

        self.pos_x = float(grid_x * 32 + 16)
        self.pos_y = float(grid_y * 32 + 16)
        self.rect = pygame.Rect(int(self.pos_x - 16), int(self.pos_y - 16), 32, 32)

        # Configure NPC specific dialog and trades
        self._init_npc_profile()

    def _init_npc_profile(self):
        if self.npc_type == NPCStyle.BLACKSMITH:
            self.name = "Doran the Blacksmith"
            self.dialogue = "I forge iron and steel! Limited materials, choose wisely."
            self.trades = [
                TradeOption("Temper Equipped Weapon (+1 Level)", 80, "upgrade_weapon", stock=2),
                TradeOption("Sharpen Heavy Edge (+2 Attack Base)", 110, "boost_attack", stock=2),
                TradeOption("Reinforce Armor Plates (+2 Defense)", 90, "boost_defense", stock=2)
            ]
            self.color = (180, 110, 50)

        elif self.npc_type == NPCStyle.HEALER:
            self.name = "Sister Althea"
            self.dialogue = "The light still protects us. Let me soothe your wounds."
            self.trades = [
                TradeOption("Minor Healing Blessing (Restore 40 HP)", 30, "heal", 40, stock=3),
                TradeOption("Full Holy Restoration (Restore 100% HP)", 70, "heal", 999, stock=1),
                TradeOption("Blessed Health Potion (50 HP)", 35, "buy_potion", Potion(PotionType.HEALTH, potency=50), stock=2)
            ]
            self.color = (60, 200, 140)

        elif self.npc_type == NPCStyle.RELIC_TRADER:
            self.name = "Xylo the Mystic"
            self.dialogue = "Ancient artifacts whisper to those with deep pockets..."
            relic_obj1 = random.choice(AVAILABLE_RELICS)()
            relic_obj2 = random.choice(AVAILABLE_RELICS)()
            self.trades = [
                TradeOption(f"Ancient Relic: {relic_obj1.name}", 110, "buy_relic", relic_obj1, stock=1),
                TradeOption(f"Mystery Relic: {relic_obj2.name}", 130, "buy_relic", relic_obj2, stock=1),
                TradeOption("Arcane Strength Draught (+10 ATK Buff)", 50, "buy_potion", Potion(PotionType.STRENGTH, potency=10, duration=25.0), stock=2)
            ]
            self.color = (170, 70, 240)

        elif self.npc_type == NPCStyle.EVENT_SHRINE:
            self.name = "Ancient Blood Shrine"
            self.dialogue = "Offer your vitality or gold to invoke primordial blessings..."
            altar_relic = random.choice(AVAILABLE_RELICS)()
            self.trades = [
                TradeOption("Blood Offering (-25 HP for +4 ATK & +150 EXP)", 0, "blood_sacrifice_atk", stock=1),
                TradeOption("Vitality Sacrifice (-25 HP for +15 Max HP)", 0, "blood_sacrifice_hp", stock=1),
                TradeOption(f"Ancient Invocation (75 G for {altar_relic.name})", 75, "buy_relic", altar_relic, stock=1)
            ]
            self.color = (230, 45, 70)

        elif self.npc_type == NPCStyle.RESCUE:
            self.name = "Lost Adventurer"
            self.dialogue = "Thank you for saving my life! Take this token of gratitude."
            reward_potion = Potion(PotionType.HEALTH, potency=75)
            self.trades = [
                TradeOption("Survivor's Gift: Health Elixir (FREE)", 0, "free_gift", reward_potion, stock=1),
                TradeOption("Reinforced Steel Spear", 60, "buy_weapon", create_spear(), stock=1),
                TradeOption("Adventurer's Swift Draught (+30% SPD)", 25, "buy_potion", Potion(PotionType.SPEED, potency=30, duration=20.0), stock=2)
            ]
            self.color = (100, 220, 180)

        else:  # Merchant
            self.name = "Bari the Wanderer"
            self.dialogue = "Fresh supplies! Limited stock for brave dungeoneers."
            self.trades = [
                TradeOption("Health Potion (Heal 40 HP)", 25, "buy_potion", Potion(PotionType.HEALTH, potency=40), stock=2),
                TradeOption("Speed Elixir (+30% SPD 15s)", 35, "buy_potion", Potion(PotionType.SPEED, potency=30, duration=15.0), stock=2),
                TradeOption("Adventurer Greatsword (Rare)", 90, "buy_weapon", create_great_sword(), stock=1),
                TradeOption("Elven Hunting Longbow (Rare)", 100, "buy_weapon", create_elven_bow(), stock=1)
            ]
            self.color = (220, 180, 40)

    def rescue(self) -> str:
        if self.is_trapped:
            self.is_trapped = False
            self.is_rescued = True
            return f"Rescued {self.name}!"
        return ""

    def execute_trade(self, option_idx: int, player) -> tuple[bool, str]:
        """
        Processes transaction safely: verifies item stock, verifies player's gold,
        applies reward, deducts stock, and deducts gold ONLY upon success.
        """
        if not (0 <= option_idx < len(self.trades)):
            return False, "Invalid selection."

        trade = self.trades[option_idx]
        if trade.is_sold_out:
            return False, "This item is SOLD OUT!"

        if player.gold < trade.cost_gold:
            return False, f"Not enough Gold! Need {trade.cost_gold} G."

        # Apply specific trade effect
        if trade.action_type == "heal":
            if player.current_hp >= player.max_hp:
                return False, "Your HP is already full!"
            player.heal(trade.param)

        elif trade.action_type == "upgrade_weapon":
            wp = player.current_weapon
            if not wp:
                return False, "No weapon equipped to upgrade."
            wp.upgrade()

        elif trade.action_type == "boost_attack":
            player.attack_power += 2

        elif trade.action_type == "boost_defense":
            player.defense += 2

        elif trade.action_type == "blood_sacrifice_atk":
            if player.current_hp <= 25:
                return False, "Not enough HP to sacrifice! (Requires > 25 HP)"
            player.current_hp -= 25
            player.attack_power += 4
            from progression.level_system import LevelSystem
            LevelSystem.add_exp(player, 150)

        elif trade.action_type == "blood_sacrifice_hp":
            if player.current_hp <= 25:
                return False, "Not enough HP to sacrifice! (Requires > 25 HP)"
            player.current_hp -= 25
            player.max_hp += 15

        elif trade.action_type in ("buy_potion", "free_gift"):
            player.inventory.add_item(trade.param)

        elif trade.action_type == "buy_weapon":
            player.inventory.add_weapon(trade.param)

        elif trade.action_type == "buy_relic":
            player.add_relic(trade.param)

        # Deduct Gold and decrease stock on successful trade
        player.gold -= trade.cost_gold
        trade.stock -= 1
        return True, "Trade successful!"

    def get_tile_pos(self) -> tuple[int, int]:
        return (self.grid_x, self.grid_y)

    def render(self, surface: pygame.Surface, camera):
        screen_rect = camera.apply(self.rect)
        loader = SpriteSheetLoader()

        sprite_name = "shopkeep"
        if self.npc_type == NPCStyle.BLACKSMITH:
            sprite_name = "blacksmith"
        elif self.npc_type == NPCStyle.HEALER:
            sprite_name = "priest"
        elif self.npc_type == NPCStyle.RELIC_TRADER:
            sprite_name = "desert sage"
        elif self.npc_type == NPCStyle.EVENT_SHRINE:
            sprite_name = "red pendant"
        elif self.npc_type == NPCStyle.RESCUE:
            sprite_name = "dwarf" if not self.is_trapped else "rogue"

        npc_surf = loader.get_sprite(sprite_name, dest_size=32)
        surface.blit(npc_surf, (screen_rect.x, screen_rect.y))

        # Render Trapped cage indicator
        if self.is_trapped:
            cage_surf = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.rect(cage_surf, (180, 50, 50, 160), (2, 2, 28, 28), 2)
            for ox in [8, 16, 24]:
                pygame.draw.line(cage_surf, (200, 100, 100, 180), (ox, 2), (ox, 30), 2)
            surface.blit(cage_surf, (screen_rect.x, screen_rect.y))
