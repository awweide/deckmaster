from core import logger


class Card:
    def __init__(self, name, cost=0, damage=0, block=0, dmg_type="neutral", special=None):
        self.name = name
        self.cost = cost
        self.damage = damage
        self.block = block
        self.dmg_type = dmg_type
        self.special = special

    def description_lines(self):
        line1 = f"{self.name} ({self.cost})"
        parts = []
        if self.damage:
            parts.append(f"Deal {self.damage} {self.dmg_type}")
        if self.block:
            parts.append(f"Gain {self.block} block")
        if self.special:
            parts.append(self._special_label())
        line2 = "; ".join(parts) if parts else ""
        return line1, line2

    def _special_label(self):
        labels = {
            "Pray&Praise": "Draw 1",
            "Singe&Sear": "Weaken next enemy turn",
            "Shoot&Stab": "2 hits",
            "Duck&Weave": "If start next turn with block, +1 energy",
            "Rot": "Removed on play",
        }
        return labels.get(self.name, "Special")


def make_base_master():
    deck = []
    for _ in range(4):
        deck.append(Card("Prayer", cost=0, damage=3, dmg_type="holy"))
        deck.append(Card("Singe", cost=1, damage=6, dmg_type="alchemical"))
        deck.append(Card("Shoot", cost=2, damage=10, dmg_type="martial"))
        deck.append(Card("Duck", cost=1, block=5))
    for _ in range(2):
        deck.append(Card("Fire&Forget", cost=1, special="fire"))
        deck.append(Card("Ebb&Flow", cost=1, special="ebb"))
    return deck


def card_pray_and_praise():
    def special(user, battle, target):
        user.draw_cards(1)
        logger.log("      Pray&Praise: drew 1 card.")

    return Card("Pray&Praise", cost=0, damage=3, dmg_type="holy", special=special)


def card_singe_and_sear():
    def special(user, battle, target):
        target.debuffs["weakened"] = target.debuffs.get("weakened", 0) + 1
        logger.log(f"      {target.name} is seared: will deal 25% less next turn.")

    return Card("Singe&Sear", cost=1, damage=6, dmg_type="alchemical", special=special)


def card_shoot_and_stab():
    def special(user, battle, target):
        user._deal_direct_damage_to(target, 10, "martial")
        user._deal_direct_damage_to(target, 4, "martial")
        logger.log("      Shoot&Stab: two strikes.")

    return Card("Shoot&Stab", cost=2, damage=10, dmg_type="martial", special=special)


def card_duck_and_weave():
    def special(user, battle, target):
        user._gain_block_internal(7, battle)
        battle.duck_weave_pending = True
        logger.log("      Duck&Weave played: if you start next turn with block, you'll gain +1 energy.")

    return Card("Duck&Weave", cost=1, block=7, special=special)


REWARD_POOL = [card_pray_and_praise, card_singe_and_sear, card_shoot_and_stab, card_duck_and_weave]
