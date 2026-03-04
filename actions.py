import math

from core import Action, logger
from characters import Lycanoid


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


class ActionBattleLoop(Action):
    def resolve(self, battle):
        if battle.hero.hp_current <= 0 or battle.enemy.hp_current <= 0:
            battle.state.victory = battle.enemy.hp_current <= 0 and battle.hero.hp_current > 0
            battle.state.terminated = True
            self.resolve_string_tail = "Battle loop skipped (already terminal)"
            return super().resolve(battle)

        battle.add_action(ActionBattleRound(), self)
        self.resolve_string_tail = "Battle loop started"
        super().resolve(battle)

    def out_of_children(self, battle):
        if battle.state.terminated:
            return

        hero_alive = battle.hero.hp_current > 0
        enemy_alive = battle.enemy.hp_current > 0
        if not hero_alive or not enemy_alive or battle.state.round >= battle.state.max_rounds:
            battle.state.victory = (not enemy_alive) and hero_alive
            battle.state.terminated = True
            return

        battle.add_action(ActionBattleRound(), self)


class ActionHeroTurn(Action):
    def __init__(self):
        super().__init__()
        self.draws_left = 0
        self.cleaned_up = False

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
        self.draws_left = battle.hero.draw_count
        self.cleaned_up = False

        if self.draws_left > 0 and battle.enemy.hp_current > 0 and battle.hero.hp_current > 0:
            self.draws_left -= 1
            battle.add_action(ActionHeroDrawAndPlay(), self)

        self.resolve_string_tail = f"Hero turn started ({self.draws_left} draws remaining)"
        super().resolve(battle)

    def out_of_children(self, battle):
        if battle.state.terminated:
            return

        if self.draws_left > 0 and battle.enemy.hp_current > 0 and battle.hero.hp_current > 0:
            self.draws_left -= 1
            battle.add_action(ActionHeroDrawAndPlay(), self)
            return

        if not self.cleaned_up:
            battle.hero.end_turn_cleanup()
            self.cleaned_up = True


class ActionHeroDrawAndPlay(Action):
    def resolve(self, battle):
        battle.hero.draw_cards(1)
        if battle.hero.hand and battle.enemy.hp_current > 0 and battle.hero.hp_current > 0:
            card = battle.hero.hand.pop(0)
            battle.hero.play_card_autoplay(card, battle)
            self.resolve_string_tail = f"Resolved card {card.name}"
        else:
            self.resolve_string_tail = "No playable card"
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
        battle = campaign.make_battle(enemy)
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


class ActionCampaignLoop(Action):
    def resolve(self, campaign):
        if campaign.state.terminated:
            self.resolve_string_tail = "Campaign loop skipped (already terminated)"
            return super().resolve(campaign)

        if campaign.state.battle_number < campaign.max_battles and campaign.state.battle_number < len(campaign.encounters):
            campaign.add_action(ActionCampaignEncounter(), self)
        self.resolve_string_tail = "Campaign loop started"
        super().resolve(campaign)

    def out_of_children(self, campaign):
        if campaign.state.terminated:
            return

        if campaign.state.battle_number >= campaign.max_battles or campaign.state.battle_number >= len(campaign.encounters):
            campaign.state.completed = True
            campaign.state.terminated = True
            return

        campaign.add_action(ActionCampaignEncounter(), self)
