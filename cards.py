from core import logger


class Card:
    def __init__(
        self,
        name,
        cost=0,
        damage=0,
        block=0,
        dmg_type="neutral",
        description="",
        mouseover="",
        special=None,
        attack_source="hero",
    ):
        self.name = name
        self.cost = cost
        self.damage = damage
        self.block = block
        self.dmg_type = dmg_type
        self.description = description
        self.mouseover = mouseover
        self.special = special
        self.attack_source = attack_source

    def description_lines(self):
        line1 = f"{self.name} ({self.cost})"
        line2 = self.description
        return line1, line2


def card_stab():
    return Card(
        "Stab",
        cost=0,
        damage=4,
        dmg_type="martial",
        description="Deal 4 damage. 1st -> x2 damage.",
        mouseover="First Stab played each turn deals double damage.",
        attack_source="hero",
    )


def card_swipe():
    return Card(
        "Swipe!",
        cost=1,
        damage=8,
        dmg_type="martial",
        description="Kuma deals 8 damage.",
        mouseover="",
        attack_source="kuma",
    )


def card_shoot():
    return Card(
        "Shoot",
        cost=2,
        damage=12,
        dmg_type="martial",
        description="Deal 12 damage, gain Unloaded. If Unloaded, instead clear Unloaded.",
        mouseover="Unloaded is automatically cleared at each reshuffle.",
        attack_source="hero",
    )


def card_defend():
    return Card(
        "Defend",
        cost=1,
        block=6,
        description="Gain 6 Block.",
        mouseover="Block cancels out incoming damage until start of next turn.",
    )


def card_guard():
    def special(user, battle, _target):
        user.guarded_stacks += 1
        logger.log(f"      Guarded gained (x{user.guarded_stacks})")

    return Card(
        "Guard!",
        cost=1,
        description="Attacked -> 0.75x damage and Kuma deals 8 damage.",
        mouseover="Each Guard gives 1 stack of Guarded until start of next turn. When attacked, damage is reduced and Kuma counterattacks.",
        special=special,
    )


def card_macallan_double_cask():
    def special(user, _battle, _target):
        user.energy_current += 1
        user.carry_energy_to_next_turn = True
        logger.log(f"      Macallan Double Cask: +1 energy (now {user.energy_current}); leftover energy will carry over.")

    return Card(
        "Macallan Double Cask",
        cost=0,
        description="Gain 1 Energy. Keep unspent energy for next turn.",
        mouseover="Normally, Energy is reset each turn. After Macallan, unspent energy carries to next turn once.",
        special=special,
    )


def card_good_boy():
    def special(user, _battle, _target):
        user.kuma_double_attack_pending += 1
        logger.log("      Good Boy!: next Kuma attack this turn deals double damage.")

    return Card(
        "Good Boy!",
        cost=1,
        description="1st Kuma attack -> 2x damage.",
        mouseover="The next attack by Kuma before start of next turn deals double damage.",
        special=special,
    )


def make_base_master():
    deck = []
    for _ in range(3):
        deck.append(card_stab())
        deck.append(card_swipe())
        deck.append(card_shoot())
        deck.append(card_defend())
        deck.append(card_guard())
    deck.append(card_macallan_double_cask())
    deck.append(card_good_boy())
    return deck


def make_reward_pool():
    return [card_stab, card_swipe, card_shoot, card_defend, card_guard, card_macallan_double_cask, card_good_boy]
