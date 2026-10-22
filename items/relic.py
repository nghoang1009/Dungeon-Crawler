class Relic:
    """
    Relic Data Architecture:
    Holds relic_id, name, description, rarity, icon_symbol, color, and gameplay effect hooks.

    Passive numbers (dash_*) are plain attributes read by Player, never mutated by hooks, so repeated
    dashes / hits cannot stack an effect up. Owning the same relic twice has no extra effect
    (see Player.unique_relics / Player.add_relic).
    """
    dash_speed_bonus = 0.0         # fraction of base dash speed (Player caps the total at +20%)
    dash_distance_bonus = 0.0      # fraction of base dash distance
    dash_stamina_discount = 0.0    # stamina points removed from the dash cost

    def __init__(self,
                 relic_id: str,
                 name: str,
                 description: str,
                 rarity: str,
                 icon_symbol: str,
                 color: tuple[int, int, int],
                 effect_text: str):
        self.relic_id = relic_id
        self.name = name
        self.description = description
        self.rarity = rarity
        self.icon_symbol = icon_symbol
        self.color = color
        self.effect_text = effect_text

    def on_acquire(self, player):
        """One-time stat changes when the relic is first picked up (a duplicate never re-applies them)."""

    def on_hit_enemy(self, player, enemy, damage: int) -> int:
        return damage

    def on_dash(self, player, game=None):
        """Called once per dash with the Game (for effects that touch enemies)."""


class FlameCore(Relic):
    def __init__(self):
        super().__init__(
            relic_id="flame_core",
            name="Flame Core",
            description="An eternal ember pulsing with elemental fire.",
            rarity="Rare",
            icon_symbol="🔥",
            color=(255, 90, 30),
            effect_text="Attacks deal +8 bonus fire damage."
        )

    def on_hit_enemy(self, player, enemy, damage: int) -> int:
        return damage + 8


class ThunderRing(Relic):
    SHOCK_RADIUS = 64.0
    dash_speed_bonus = 0.18

    def __init__(self):
        super().__init__(
            relic_id="thunder_ring",
            name="Thunder Ring",
            description="Crackles with high-voltage lightning energy.",
            rarity="Epic",
            icon_symbol="⚡",
            color=(80, 220, 255),
            effect_text="+18% dash speed. Dashing emits a shockwave that damages nearby enemies."
        )

    def on_dash(self, player, game=None):
        if game is None:
            return
        import math
        from combat.combat_system import HitParticle
        damage = 6 + int(player.attack_power * 0.5)
        for enemy in game.enemies:
            if not enemy.is_alive:
                continue
            dx, dy = enemy.pos_x - player.pos_x, enemy.pos_y - player.pos_y
            dist = math.hypot(dx, dy)
            if dist <= self.SHOCK_RADIUS:
                away = (dx / dist, dy / dist) if dist > 0 else player.facing_dir
                game.combat_system._apply_damage_to_enemy(player, enemy, damage, False, game.tilemap,
                                                          game.obstacles, knockback_dir=away)
        for k in range(8):
            angle = k * math.pi / 4
            game.combat_system.particles.append(
                HitParticle(player.pos_x + math.cos(angle) * 18, player.pos_y + math.sin(angle) * 18,
                            color=self.color))


class FrostHeart(Relic):
    SLOW_FACTOR = 0.75
    SLOW_SECONDS = 3.0

    def __init__(self):
        super().__init__(
            relic_id="frost_heart",
            name="Frost Heart",
            description="Glacial core freezing nearby air.",
            rarity="Rare",
            icon_symbol="❄️",
            color=(120, 240, 255),
            effect_text="Hits slow enemy movement by 25% for 3 seconds."
        )

    def on_hit_enemy(self, player, enemy, damage: int) -> int:
        if hasattr(enemy, "apply_slow"):
            enemy.apply_slow(self.SLOW_FACTOR, self.SLOW_SECONDS)
        return damage


class BloodCharm(Relic):
    MAX_BONUS = 0.50

    def __init__(self):
        super().__init__(
            relic_id="blood_charm",
            name="Blood Charm",
            description="Ancient amulet drinking user's life essence for power.",
            rarity="Epic",
            icon_symbol="🩸",
            color=(225, 40, 60),
            effect_text="Gain up to +50% bonus damage as Player HP drops."
        )

    def on_hit_enemy(self, player, enemy, damage: int) -> int:
        missing_hp_pct = max(0.0, min(1.0, 1.0 - (player.current_hp / max(1, player.max_hp))))
        return damage + int(damage * self.MAX_BONUS * missing_hp_pct)


class IronShell(Relic):
    def __init__(self):
        super().__init__(
            relic_id="iron_shell",
            name="Iron Shell",
            description="Hardened carapace providing formidable protection.",
            rarity="Uncommon",
            icon_symbol="🛡️",
            color=(170, 170, 190),
            effect_text="+4 Defense, -10 Movement Speed."
        )

    def on_acquire(self, player):
        player.defense += 4
        player.speed = max(90.0, player.speed - 10.0)


class VoidCrystal(Relic):
    dash_distance_bonus = 0.25
    dash_stamina_discount = 5.0

    def __init__(self):
        super().__init__(
            relic_id="void_crystal",
            name="Void Crystal",
            description="Warping shard bending space-time continuum.",
            rarity="Legendary",
            icon_symbol="🔮",
            color=(190, 60, 255),
            effect_text="+25% Dash Distance, Dash costs 5 less Stamina."
        )


AVAILABLE_RELICS = [FlameCore, ThunderRing, FrostHeart, BloodCharm, IronShell, VoidCrystal]
