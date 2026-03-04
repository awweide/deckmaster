import math
import random
import tkinter as tk
import uuid
from tkinter import ttk


class DotMap(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key, value):
        self[key] = value


class Logger:
    def __init__(self):
        self.on_update = None

    def log(self, text=""):
        print(text)
        if self.on_update:
            self.on_update(text)


logger = Logger()


class Action:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.parent = None
        self.list_sub_actions = []
        self.resolved = False
        self.typename = type(self).__name__
        self.resolve_string_tail = None

    def resolve(self, engine):
        indent_level = len(engine.index) - 1 if len(engine.index) > 0 else 0
        indent = "  " * indent_level
        if self.resolve_string_tail:
            lines = str(self.resolve_string_tail).splitlines()
            logger.log(f"{indent}{self.typename}: {lines[0]}")
            for ln in lines[1:]:
                logger.log(f"{indent}{ln}")
        else:
            logger.log(f"{indent}{self.typename}")
        self.resolved = True


class Engine:
    def __init__(self):
        self.list_rules = []
        self.state = DotMap()
        self.list_sub_actions = []
        self.num_steps_counter = 0
        self.num_steps_limit = 5000
        self.index = []
        self.active_action = None

    def add_action(self, new_action, parent_action=None):
        if parent_action:
            new_action.parent = parent_action
            parent_action.list_sub_actions.append(new_action)
        else:
            new_action.parent = None
            self.list_sub_actions.append(new_action)

    def broadcast(self, hook_name):
        for rule in list(self.list_rules):
            rule(self, hook_name)

    def get_action_from_index(self, index):
        action = self
        for i in index:
            action = action.list_sub_actions[i]
        return action

    def index_advance(self):
        if not self.index:
            return

        if self.active_action.list_sub_actions:
            self.index.append(0)
            return

        index = list(self.index)
        while index:
            last_index = index.pop()
            action = self.get_action_from_index(index)
            if len(action.list_sub_actions) > last_index + 1:
                index.append(last_index + 1)
                self.index = index
                return

        self.index = []

    def step(self):
        self.num_steps_counter += 1
        if self.index:
            self.active_action = self.get_action_from_index(self.index)
            self.broadcast("pre_resolve")
            self.active_action.resolve(self)
            self.broadcast("post_resolve")
            self.index_advance()
        else:
            self.broadcast("end_of_actions")


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
        logger.log(f"      {self.name} takes {unblocked} {dmg_type} damage (blocked {blocked}), HP now {self.hp_current}/{self.hp_base}")
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
        return Card(card_template.name, card_template.cost, card_template.damage, card_template.block, card_template.dmg_type, card_template.special)

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


class ActionBattleRound(Action):
    def resolve(self, battle):
        battle.state.round += 1
        battle.snapshots.append((battle.state.round, battle.hero.hp_current, battle.enemy.hp_current))
        logger.log(f"\nStart of round {battle.state.round}")
        logger.log(f"  {battle.hero.name}: {battle.hero.hp_current}/{battle.hero.hp_base}")
        logger.log(f"  {battle.enemy.name}: {battle.enemy.hp_current}/{battle.enemy.hp_base}")

        battle.add_action(ActionHeroTurn(), self)
        battle.add_action(ActionEnemyTurn(), self)
        self.resolve_string_tail = f"Round {battle.state.round} sequence queued"
        super().resolve(battle)


class ActionHeroTurn(Action):
    def resolve(self, battle):
        if battle.state.terminated:
            self.resolve_string_tail = "Skipped (battle already terminated)"
            return super().resolve(battle)

        if battle.duck_weave_pending and battle.hero.block > 0:
            battle.state.turn_energy_bonus = 1
            logger.log("      Duck&Weave triggers: +1 energy for starting turn with block")
        else:
            battle.state.turn_energy_bonus = 0
        battle.duck_weave_pending = False

        battle.hero.ebb_consumed_this_turn = False
        battle.hero.energy_current = battle.hero.energy_base + battle.state.turn_energy_bonus
        battle.hero.block = 0

        battle.hero.draw_cards(battle.hero.draw_count)
        while battle.hero.hand and battle.enemy.hp_current > 0:
            card = battle.hero.hand.pop(0)
            battle.hero.play_card_autoplay(card, battle)

        battle.hero.end_turn_cleanup()
        self.resolve_string_tail = f"Hero turn complete (enemy HP {battle.enemy.hp_current})"
        super().resolve(battle)


class ActionEnemyTurn(Action):
    def resolve(self, battle):
        if battle.state.terminated or battle.enemy.hp_current <= 0:
            self.resolve_string_tail = "Skipped (enemy defeated)"
            return super().resolve(battle)
        if isinstance(battle.enemy, Lycanoid):
            battle.enemy.start_round()
        battle.enemy.act(battle)
        self.resolve_string_tail = f"Enemy turn complete (hero HP {battle.hero.hp_current})"
        super().resolve(battle)


class Battle(Engine):
    def __init__(self, hero, enemy):
        super().__init__()
        self.hero = hero
        self.enemy = enemy
        self.snapshots = []
        self.duck_weave_pending = False
        self.list_rules.extend([RuleBattleStateInit(), RuleBattleProgression()])

    def run(self):
        logger.log(f"\n--- Starting battle vs {self.enemy.name} ---")
        self.broadcast("start_of_battle")
        while self.num_steps_counter < self.num_steps_limit and not self.state.terminated:
            self.step()

        self.snapshots.append((self.state.round, self.hero.hp_current, self.enemy.hp_current))
        logger.log("\n--- Battle ended ---")
        self.print_summary()
        return self.state.victory

    def print_summary(self):
        logger.log("\nBattle summary (selected rounds):")
        n = len(self.snapshots)
        indices = range(n) if n <= 6 else sorted(set([0] + [round((n - 1) * i / 5) for i in range(1, 5)] + [n - 1]))
        for i in indices:
            r, h, e = self.snapshots[i]
            logger.log(f"  Round {r}: Hero {h}/{self.hero.hp_base} -- {self.enemy.name} {e}/{self.enemy.hp_base}")
        logger.log(f"Result: {'Victory' if self.state.victory else 'Defeat'}")


class RuleBattleStateInit:
    def __call__(self, battle, hook_name):
        if hook_name != "start_of_battle":
            return
        battle.state.round = 0
        battle.state.max_rounds = 50
        battle.state.victory = False
        battle.state.terminated = False
        battle.state.turn_energy_bonus = 0
        battle.hero.reset_for_battle()
        battle.enemy.reset_for_battle()
        battle.add_action(ActionBattleRound())
        battle.index = [len(battle.list_sub_actions) - 1]


class RuleBattleProgression:
    def __call__(self, battle, hook_name):
        if hook_name != "end_of_actions":
            return

        hero_alive = battle.hero.hp_current > 0
        enemy_alive = battle.enemy.hp_current > 0
        if not hero_alive or not enemy_alive or battle.state.round >= battle.state.max_rounds:
            battle.state.victory = enemy_alive is False and hero_alive
            battle.state.terminated = True
            return

        battle.add_action(ActionBattleRound())
        if not battle.index:
            battle.index = [len(battle.list_sub_actions) - 1]


class ActionCampaignEncounter(Action):
    def resolve(self, campaign):
        campaign.state.battle_number += 1
        idx = campaign.state.battle_number
        enemy = campaign.encounters[idx - 1]

        selected_indices = campaign.select_battle_deck(enemy)
        if selected_indices is None:
            campaign.state.terminated = True
            self.resolve_string_tail = "Deck selection canceled"
            return super().resolve(campaign)

        campaign.hero.deck_battle = [campaign.hero.deck_master[i] for i in selected_indices]
        logger.log("Battle deck confirmed. Starting battle...")
        battle = Battle(campaign.hero, enemy)
        campaign.battles.append(battle)
        won = battle.run()

        if won:
            logger.log(f"\nYou defeated {enemy.name}!")
            heal = math.floor(campaign.hero.hp_base * 0.2)
            campaign.hero.hp_current = min(campaign.hero.hp_current + heal, campaign.hero.hp_base)
            logger.log(f"Hero recovers {heal} HP (now {campaign.hero.hp_current}/{campaign.hero.hp_base}).")
            reward_choice = campaign.select_reward()
            if reward_choice is not None:
                newcard = reward_choice()
                campaign.hero.deck_master.append(newcard)
                logger.log(f"Added {newcard.name} to master deck.")
        else:
            logger.log("\nYou were defeated. Campaign ends.")
            campaign.state.terminated = True

        self.resolve_string_tail = f"Encounter {idx}/{campaign.max_battles} resolved"
        super().resolve(campaign)


class Campaign(Engine):
    def __init__(self, hero=None, app=None, max_battles=3):
        super().__init__()
        self.hero = hero if hero else Hero()
        self.app = app
        self.max_battles = max_battles
        self.enemies = [Zombie, Ooze, Lycanoid]
        self.encounters = []
        self.battles = []
        self.list_rules.extend([RuleCampaignStateInit(), RuleCampaignProgression()])

    def select_battle_deck(self, enemy):
        title = f"Select 12 cards to fight {enemy.name}"
        if self.app:
            return self.app.select_cards(self.hero.deck_master, 12, title, columns=4)
        if len(self.hero.deck_master) < 12:
            return None
        return list(range(12))

    def select_reward(self):
        offered = random.sample(REWARD_POOL, 2)
        if self.app:
            cards = [f() for f in offered]
            selected = self.app.select_cards(cards, 1, "Select 1 reward to add to master deck", columns=2)
            return offered[selected[0]] if selected else None
        return random.choice(offered)

    def run(self):
        logger.log("Start of Campaign")
        self.broadcast("start_of_campaign")
        while self.num_steps_counter < self.num_steps_limit and not self.state.terminated:
            self.step()

        if self.state.completed:
            logger.log("\n*** Campaign complete! You defeated all enemies! ***")
        elif self.state.terminated:
            logger.log("\n*** Campaign ended early. ***")


class RuleCampaignStateInit:
    def __call__(self, campaign, hook_name):
        if hook_name != "start_of_campaign":
            return
        campaign.hero.hp_current = campaign.hero.hp_base
        campaign.state.battle_number = 0
        campaign.state.terminated = False
        campaign.state.completed = False
        campaign.encounters = [cls() for cls in random.sample(campaign.enemies, len(campaign.enemies))][:campaign.max_battles]


class RuleCampaignProgression:
    def __call__(self, campaign, hook_name):
        if hook_name != "end_of_actions":
            return

        if campaign.state.battle_number >= campaign.max_battles:
            campaign.state.completed = True
            campaign.state.terminated = True
            return

        if campaign.state.battle_number >= len(campaign.encounters):
            campaign.state.completed = True
            campaign.state.terminated = True
            return

        campaign.add_action(ActionCampaignEncounter())
        if not campaign.index:
            campaign.index = [len(campaign.list_sub_actions) - 1]


class CardGridSelector(tk.Toplevel):
    def __init__(self, master, cards, required_count, title, columns=4):
        super().__init__(master)
        self.transient(master)
        self.grab_set()
        self.title(title)
        self.cards = cards
        self.required_count = required_count
        self.columns = columns
        self.selected = set()
        self.result = None
        self.card_widgets = []

        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        for idx, card in enumerate(cards):
            r, c = divmod(idx, columns)
            canvas = tk.Canvas(frame, width=220, height=80, bd=1, relief="ridge")
            canvas.grid(row=r, column=c, padx=6, pady=6)
            rect = canvas.create_rectangle(4, 4, 216, 76, fill="white")
            line1, line2 = card.description_lines()
            canvas.create_text(10, 12, anchor="nw", text=line1, font=("TkDefaultFont", 10, "bold"))
            canvas.create_text(10, 34, anchor="nw", text=line2, font=("TkDefaultFont", 9))
            canvas.bind("<Button-1>", lambda _e, i=idx: self.toggle(i))
            self.card_widgets.append((canvas, rect))

        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.sel_label = ttk.Label(bottom, text=f"Selected: 0/{self.required_count}")
        self.sel_label.pack(side=tk.LEFT)
        self.confirm_btn = ttk.Button(bottom, text="Confirm", command=self.confirm, state=tk.DISABLED)
        self.confirm_btn.pack(side=tk.RIGHT)

        self.bind("<Escape>", lambda _e: self.cancel())

    def toggle(self, idx):
        if idx in self.selected:
            self.selected.remove(idx)
            self.card_widgets[idx][0].itemconfig(self.card_widgets[idx][1], fill="white")
        else:
            if len(self.selected) >= self.required_count:
                return
            self.selected.add(idx)
            self.card_widgets[idx][0].itemconfig(self.card_widgets[idx][1], fill="#cfeedd")

        self.sel_label.config(text=f"Selected: {len(self.selected)}/{self.required_count}")
        enabled = tk.NORMAL if len(self.selected) == self.required_count else tk.DISABLED
        self.confirm_btn.config(state=enabled)

    def confirm(self):
        self.result = list(self.selected)
        self.grab_release()
        self.destroy()

    def cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()


class App:
    def __init__(self, root):
        self.root = root
        root.title("Deckmaster")
        root.geometry("1200x800")

        left = ttk.Frame(root)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(left, text="Game Log", font=("Helvetica", 12, "bold")).pack(anchor="nw")
        self.log_text = tk.Text(left, wrap=tk.WORD, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        right = ttk.Frame(root, width=420)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Label(right, text="Controls", font=("Helvetica", 12, "bold")).pack(pady=(6, 4))
        self.info_label = ttk.Label(right, text="Press Start Campaign to begin.", wraplength=380)
        self.info_label.pack(padx=6, pady=6)
        self.start_btn = ttk.Button(right, text="Start Campaign", command=self.start_campaign)
        self.start_btn.pack(pady=4)

        logger.on_update = self._append_log

    def _append_log(self, text):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def select_cards(self, cards, required_count, title, columns=4):
        selector = CardGridSelector(self.root, cards, required_count, title, columns=columns)
        self.root.wait_window(selector)
        return selector.result

    def start_campaign(self):
        self.start_btn.config(state=tk.DISABLED)
        self.info_label.config(text="Campaign running...")
        self.root.after(20, self._run_campaign)

    def _run_campaign(self):
        campaign = Campaign(hero=Hero(), app=self, max_battles=3)
        campaign.run()
        self.start_btn.config(state=tk.NORMAL)
        self.info_label.config(text="Campaign finished. Press Start Campaign to run again.")


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
