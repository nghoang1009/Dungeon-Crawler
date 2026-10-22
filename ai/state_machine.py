class State:
    """
    Abstract base state class for Real-Time Finite State Machine (FSM).
    """
    def __init__(self, name: str):
        self.name = name

    def enter(self, entity):
        pass

    def execute(self, entity, dt: float, game_context):
        """Called every frame in real-time loop."""

    def exit(self, entity):
        pass


class StateMachine:
    """
    Generic Finite State Machine manager for Real-Time action entities.
    """
    def __init__(self, entity):
        self.entity = entity
        self.states: dict[str, State] = {}
        self.current_state: State | None = None
        self.previous_state: State | None = None
        self.time_in_state: float = 0.0

    def add_state(self, state: State):
        self.states[state.name] = state

    def change_state(self, state_name: str):
        if state_name not in self.states:
            raise ValueError(f"State '{state_name}' is not registered in StateMachine.")

        new_state = self.states[state_name]
        if self.current_state:
            self.current_state.exit(self.entity)

        self.previous_state = self.current_state
        self.current_state = new_state
        self.time_in_state = 0.0
        self.current_state.enter(self.entity)

    def update(self, dt: float, game_context):
        if self.current_state:
            self.time_in_state += dt
            self.current_state.execute(self.entity, dt, game_context)

    @property
    def current_state_name(self) -> str:
        return self.current_state.name if self.current_state else "NONE"
