import random
import tkinter as tk
from tkinter import ttk

from cards import REWARD_POOL
from characters import Hero, Lycanoid, Ooze, Zombie
from core import Engine, logger
from rules import (
    RuleBattleStateInit,
    RuleCampaignStateInit,
)


class Battle(Engine):
    def __init__(self, hero, enemy):
        super().__init__()
        self.hero = hero
        self.enemy = enemy
        self.snapshots = []
        self.duck_weave_pending = False
        self.list_rules.extend([RuleBattleStateInit()])

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


class Campaign(Engine):
    def __init__(self, hero=None, app=None, max_battles=3):
        super().__init__()
        self.hero = hero if hero else Hero()
        self.app = app
        self.max_battles = max_battles
        self.enemies = [Zombie, Ooze, Lycanoid]
        self.encounters = []
        self.battles = []
        self.list_rules.extend([RuleCampaignStateInit()])

    def make_battle(self, enemy):
        return Battle(self.hero, enemy)

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
