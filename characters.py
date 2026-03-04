import random

from cards import (
    Card,
    card_duck_and_weave,
    card_pray_and_praise,
    card_shoot_and_stab,
    card_singe_and_sear,
    make_base_master,
)
from core import logger


class Character:
    def __init__(self, name, hp_base):
        self.name = name
        self.hp_base = hp_base
        self.hp_current = hp_base
        self.block = 0
        self.strength_base = 0
        self.strength_current = 0
        self.debuffs = {}

    def reset_for_battle(self):
        self.hp_current = min(self.hp_current, self.hp_base)
        self.block = 0
        self.strength_current = self.strength_base
        self.debuffs = {}

    def _take_with_block(self, amount, dmg_type="neutral", source=None):
        if dmg_type == "unblockable":
            unblocked = amount
            blocked = 0
        else:
            blocked = min(self.block, amount)
            unblocked = amount - blocked
            self.block = max(0, self.block - amount)
        self.hp_current = max(0, self.hp_current - unblocked)
        logger.log(
            f"      {self.name} takes {unblocked} {dmg_type} damage (blocked {blocked}), HP now {self.hp_current}/{self.hp_base}"
        )
        return unblocked


class Hero(Character):
    def __init__(self, name="Hero", hp_base=100):
        super().__init__(name, hp_base)
        self.deck_master = make_base_master()
        self.deck_battle = []
        self.deck = []
        self.discard = []
        self.hand = []
        self.limbo = []
        self.draw_count = 3
        self.energy_base = 3
        self.energy_current = 3
        self.ebb_stacks = 0
        self.ebb_consumed_this_turn = False

    def reset_for_battle(self):
        super().reset_for_battle()
        self.deck = [self._clone_card(c) for c in self.deck_battle]
        random.shuffle(self.deck)
        self.discard = []
        self.hand = []
        self.limbo = []
        self.energy_current = self.energy_base
        self.ebb_stacks = 0
        self.ebb_consumed_this_turn = False

    def _clone_card(self, card_template):
        upgrades = {
            "Pray&Praise": card_pray_and_praise,
            "Singe&Sear": card_singe_and_sear,
            "Shoot&Stab": card_shoot_and_stab,
            "Duck&Weave": card_duck_and_weave,
        }
        if card_template.name in upgrades:
            return upgrades[card_template.name]()
        return Card(
            card_template.name,
            card_template.cost,
            card_template.damage,
            card_template.block,
            card_template.dmg_type,
            card_template.special,
        )

    def _deal_direct_damage_to(self, enemy, base_amount, dmg_type):
        total = base_amount + (self.strength_base + self.strength_current)
        return enemy.receive_damage(total, dmg_type, source=self)

    def _gain_block_internal(self, amount, battle):
        bonus = 0
        if self.ebb_stacks > 0 and not self.ebb_consumed_this_turn:
            bonus = 2 * self.ebb_stacks
            self.ebb_consumed_this_turn = True
            logger.log(f"      Ebb&Flow triggers! +{bonus} block.")
        self.block += amount + bonus
        logger.log(f"      {self.name} gains {amount + bonus} block (total {self.block})")

    def draw_cards(self, n):
        for _ in range(n):
            if not self.deck:
                if self.discard:
                    logger.log("    Deck empty — reshuffling discard into deck.")
                    self.deck = self.discard[:]
                    random.shuffle(self.deck)
                    self.discard = []
                else:
                    return
            card = self.deck.pop(0)
            self.hand.append(card)
            logger.log(f"    Drew {card.name}")

    def play_card_autoplay(self, card, battle):
        if card.cost > self.energy_current:
            logger.log(f"    {card.name}: passing (not enough energy)")
            self.limbo.append(card)
            return

        self.energy_current -= card.cost
        logger.log(f"    {card.name}: playing (cost {card.cost}, energy left {self.energy_current})")
        if card.damage:
            self._deal_direct_damage_to(battle.enemy, card.damage, card.dmg_type)
        if card.block:
            self._gain_block_internal(card.block, battle)

        if card.special:
            if card.special == "fire":
                self.strength_current += 1
                logger.log(f"      {self.name} gains 1 strength (this battle) — now {self.strength_current}")
            elif card.special == "ebb":
                self.ebb_stacks += 1
                logger.log(f"      {self.name} gains an Ebb&Flow stack (x{self.ebb_stacks})")
            else:
                card.special(self, battle, battle.enemy)

        if card.name == "Rot":
            logger.log("      Rot dissipates and is removed from deck.")
        else:
            self.limbo.append(card)

    def end_turn_cleanup(self):
        while self.limbo:
            self.discard.append(self.limbo.pop())


class Zombie(Character):
    def __init__(self):
        super().__init__("Zombie", 120)

    def receive_damage(self, amount, dmg_type, source=None):
        if dmg_type == "holy":
            amount = int(amount * 1.25)
        return self._take_with_block(amount, dmg_type, source)

    def act(self, battle):
        mult = 0.75 if self.debuffs.get("weakened", 0) > 0 else 1.0
        if mult < 1.0:
            self.debuffs["weakened"] -= 1
            if self.debuffs["weakened"] <= 0:
                self.debuffs.pop("weakened", None)
        dmg = int(6 * mult)
        logger.log(f"  {self.name} acts and attacks for {dmg} (martial)")
        battle.hero._take_with_block(dmg, "martial", source=self)


class Ooze(Character):
    def __init__(self):
        super().__init__("Ooze", 80)

    def receive_damage(self, amount, dmg_type, source=None):
        if dmg_type == "fire":
            amount = int(amount * 1.25)
        return self._take_with_block(amount, dmg_type, source)

    def act(self, battle):
        mult = 0.75 if self.debuffs.get("weakened", 0) > 0 else 1.0
        if mult < 1.0:
            self.debuffs["weakened"] -= 1
            if self.debuffs["weakened"] <= 0:
                self.debuffs.pop("weakened", None)
        dmg = int(8 * mult)
        logger.log(f"  {self.name} acts and deals {dmg} unblockable damage!")
        battle.hero._take_with_block(dmg, "unblockable", source=self)


class Lycanoid(Character):
    def __init__(self):
        super().__init__("Lycanoid", 110)
        self.evaded_this_round = False

    def start_round(self):
        self.evaded_this_round = False

    def receive_damage(self, amount, dmg_type, source=None):
        if not self.evaded_this_round:
            logger.log(f"      {self.name} evades the first attack this round!")
            self.evaded_this_round = True
            return 0
        if dmg_type == "martial":
            amount = int(amount * 1.25)
        return self._take_with_block(amount, dmg_type, source)

    def act(self, battle):
        mult = 0.75 if self.debuffs.get("weakened", 0) > 0 else 1.0
        if mult < 1.0:
            self.debuffs["weakened"] -= 1
            if self.debuffs["weakened"] <= 0:
                self.debuffs.pop("weakened", None)
        logger.log(f"  {self.name} acts with two quick strikes!")
        for i in range(2):
            dmg = int(5 * mult)
            logger.log(f"    Strike {i + 1} for {dmg}")
            battle.hero._take_with_block(dmg, "martial", source=self)
