import uuid
import random
from dotmap import DotMap

# === Actions ===
class Action:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.list_sub_actions = []
        self.resolved = False
        self.typename = type(self).__name__
        self.resolve_string_tail = None

    def resolve(self, battle):
        indent_level = len(battle.index) - 1 if len(battle.index) > 0 else 0
        indent = "  " * indent_level

        if self.resolve_string_tail:
            lines = str(self.resolve_string_tail).splitlines()
            print(f"{indent}{self.typename}: {lines[0]}")
            for ln in lines[1:]:
                print(f"{indent}{ln}")
        else:
            print(f"{indent}{self.typename}")
        self.resolved = True


class ActionRoundStart(Action):
    def resolve(self, battle):
        battle.state.round_number += 1

        units_random_order = list(battle.units); random.shuffle(units_random_order)
        for unit in units_random_order:
            battle.add_action(ActionTurnStart(unit), self)

        status = battle.get_status()
        self.resolve_string_tail = f"Round {battle.state.round_number}\n{status}\nTurn order: {[unit.__str__() for unit in units_random_order]}"

        print('')
        super().resolve(battle)


class ActionTurnStart(Action):
    def __init__(self, unit):
        super().__init__()
        self.unit = unit
        self.skill_chosen = None

    def resolve(self, battle):
        if self.unit.hp > 0:
            self.skill_chosen = self.unit.skill_choose(battle)
            if not self.skill_chosen:
                self.resolve_string_tail = f"{self.unit} has no available skill - passes its turn"
            else:
                self.resolve_string_tail = f"{self.unit} chooses skill {self.skill_chosen.typename}"
                self.skill_chosen.use(battle)
        else:
            self.resolve_string_tail = f"{self.unit} is defeated - passes its turn"
        super().resolve(battle)


class ActionSkillBasicAttack(Action):
    def __init__(self, skill_source):
        super().__init__()
        self.skill_source = skill_source
        self.resolve_string_tail = f"{self.skill_source.unit} whiffs {self.skill_source}"

    def resolve(self, battle):
        list_enemy_not_defeated = [unit for unit in battle.units if unit.team != self.skill_source.unit.team and unit.hp > 0]
        if list_enemy_not_defeated:
            target = list_enemy_not_defeated[0]
            battle.add_action(ActionSkillDamageGive(self.skill_source, target), self)
            self.resolve_string_tail = f"{self.skill_source.unit} uses {self.skill_source} on {target}"
        else:
            self.resolve_string_tail = f"{self.skill_source.unit} whiffs {self.skill_source}"
        super().resolve(battle)
        

class ActionSkillDamageGive(Action):
    def __init__(self, skill_source, target):
        super().__init__()
        self.skill_source = skill_source
        self.target = target
        self.damage_multiplier = 1

    def resolve(self, battle):
        damage = int(self.damage_multiplier * random.randint(1, 6) + self.skill_source.unit.strength)
        self.resolve_string_tail = f"{self.skill_source.unit} directs {damage} damage towards {self.target.__str__()}"
        battle.add_action(ActionSkillDamageTake(self.skill_source, self.target, damage), self)
        super().resolve(battle)


class ActionSkillDamageTake(Action):
    def __init__(self, skill_source, target, damage):
        super().__init__()
        self.skill_source = skill_source
        self.target = target
        self.damage = damage

    def resolve(self, battle):
        hp_before = self.target.hp
        self.target.hp = max(0, self.target.hp - self.damage)
        hp_after = self.target.hp
        self.resolve_string_tail = f"{self.target} HP {hp_before} → {hp_after}"
        super().resolve(battle)
        

# === Units & Skills ===
class Unit:
    def __init__(self, battle, team, hp_max=100, strength=1):
        self.team = team
        self.hp_max = hp_max
        self.hp = hp_max
        self.strength = strength
        self.list_skills = []
        self.typename = type(self).__name__

    def __str__(self):
        return f"{self.team}({id(self) % 1000})"

    def skill_choose(self, battle):
        for skill in self.list_skills:
            if skill.available(battle):
                return skill
        return None

class UnitGuard(Unit):
    def __init__(self, battle, team):
        super().__init__(battle=battle, team=team, hp_max=100, strength=1)
        self.list_skills = [SkillBasicAttack(self)]

class Skill:
    def __init__(self, unit):
        self.unit = unit
        self.typename = type(self).__name__

    def available(self, battle):
        return True

    def use(self, battle):
        raise NotImplementedError
        
    def __str__(self):
        return self.typename


class SkillBasicAttack(Skill):
    def available(self, battle):
        return True

    def use(self, battle):
        battle.add_action(ActionSkillBasicAttack(self), battle.active_action)


# === Battle engine ===
class Battle:
    def __init__(self):
        self.list_rules = []
        self.state = DotMap()
        self.list_sub_actions = []

        self.num_steps_counter = 0
        self.num_steps_limit = 5000

        self.index = []
        self.active_action = None

        self.units = []

    def get_status(self):
        lines = []
        
        teams = sorted({u.team for u in self.units})
        for team in teams:
            members = [u for u in self.units if u.team == team]
            unit_strs = [f"{u} {u.hp}/{u.hp_max}" for u in members]
            lines.append(f"{team}: " + ", ".join(unit_strs))
        return "\n".join(lines)

    def add_action(self, new_action, parent_action=None):
        if parent_action:
            parent_action.list_sub_actions.append(new_action)
        else:
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

    def run(self):
        print("Start of Battle:")
        print("Active rules:")
        for rule in self.list_rules:
            print(f" - {rule.__class__.__name__}")
        print("\n")

        self.broadcast("start_of_battle")

        while self.num_steps_counter < self.num_steps_limit:
            self.step()

        teams = sorted({u.team for u in self.units})
        alive_teams = [t for t in teams if any(u.hp > 0 for u in self.units if u.team == t)]
        if len(alive_teams) == 1:
            result_line = f"BattleEnd: Team {alive_teams[0]} victorious"
            defeated = [t for t in teams if t != alive_teams[0]]
            if defeated:
                result_line += f", team {defeated[0]} defeated"
        elif len(alive_teams) == 0:
            result_line = "BattleEnd: All teams defeated"
        else:
            result_line = "BattleEnd: Timeout reached, no decisive winner"
        print(result_line)
        print(self.get_status())


# === Rules ===
class RuleBattleStateInit:
    def __call__(self, battle, hook_name):
        if hook_name != "start_of_battle": return
        battle.state.round_number = 0
        battle.state.max_rounds = 10
        battle.state.elements = DotMap(steel=0, blood=0, spark=0)
        battle.units = [
            UnitGuard(battle=battle, team="A"),
            UnitGuard(battle=battle, team="B"),
        ]


class RuleStartNextRound:
    def __call__(self, battle, hook_name):
        if hook_name != "end_of_actions": return
        if battle.state.round_number >= battle.state.max_rounds: return
        if len({u.team for u in battle.units if u.hp > 0}) <= 1: return

        battle.add_action(ActionRoundStart())
        if not battle.index: battle.index = [len(battle.list_sub_actions) - 1]
        
if __name__ == "__main__":
    battle = Battle()
    battle.list_rules.extend([RuleBattleStateInit(), RuleStartNextRound()])
    battle.broadcast("start_of_battle")
    battle.run()
