import uuid


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

    def out_of_children(self, engine):
        return


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
            finished_index = index.pop()
            parent = self.get_action_from_index(index)

            children_before = len(parent.list_sub_actions)
            if isinstance(parent, Action):
                self.active_action = parent
                self.broadcast("pre_out_of_children")
                parent.out_of_children(self)
                self.broadcast("post_out_of_children")
            children_after = len(parent.list_sub_actions)

            if children_after > children_before:
                self.index = index + [children_before]
                return

            if children_after > finished_index + 1:
                self.index = index + [finished_index + 1]
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
