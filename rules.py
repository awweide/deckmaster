import random

from actions import ActionBattleLoop, ActionCampaignLoop


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
        battle.add_action(ActionBattleLoop())
        battle.index = [len(battle.list_sub_actions) - 1]


class RuleCampaignStateInit:
    def __call__(self, campaign, hook_name):
        if hook_name != "start_of_campaign":
            return
        campaign.hero.hp_current = campaign.hero.hp_base
        campaign.state.battle_number = 0
        campaign.state.terminated = False
        campaign.state.completed = False
        campaign.encounters = [cls() for cls in random.sample(campaign.enemies, len(campaign.enemies))][: campaign.max_battles]
        campaign.add_action(ActionCampaignLoop())
        campaign.index = [len(campaign.list_sub_actions) - 1]
