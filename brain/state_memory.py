class StateMemory:
    def __init__(self):
        self._history = []

    def add_action(self, action):
        self._history.append(action)

    def history(self):
        return self._history
