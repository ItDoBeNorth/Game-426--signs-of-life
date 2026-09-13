"""A small Days at Three Branches starter built entirely from ``sandbox.village``."""

import math
from collections import deque

from sandbox.observation_types import ThreeBranchesAction, ThreeBranchesObservation
from sandbox.village import action, geometry, layout, me, people, props

# Duration (in ticks) to hold "use" on a prop, by its transition type. Timed props use
# duration/4 so villagers don't stall for the full catalog duration; toggle/occupancy get a
# short fixed hold. "sleep" is reserved for the end-of-day return home, not idle flavor.
_TIMED_USE_TICKS = {"plot": 150, "shrine": 75, "bell": 10, "pump": 3}
_TOGGLE_TYPES = ("lantern", "hearth", "stall")
_OCCUPANCY_TYPES = ("bench", "repair_bench")
_IDLE_EMOTES = tuple(emote for emote in action.EMOTES if emote != "sleep")
_TASK_TYPES = frozenset(
    {"plot", "shrine", "pump", "bell", "stall", "lantern", "hearth", "bench", "repair_bench", "board"}
)
_STUCK_TICKS_LIMIT = 30  # abandon a destination after this many ticks of near-zero movement


def _cell_centre(cell: dict[str, int]) -> dict[str, float]:
    """Return the point at the centre of one village cell."""

    return {"x": cell["x"] + 0.5, "y": cell["y"] + 0.5}


def _prop_use_ticks(prop_type: str) -> int:
    """How many ticks to hold "use" on a prop, based on its catalog transition type."""
    if prop_type in _TIMED_USE_TICKS:
        return _TIMED_USE_TICKS[prop_type]
    if prop_type in _TOGGLE_TYPES:
        return 3
    if prop_type in _OCCUPANCY_TYPES:
        return 4
    return 1  # e.g. "board": no state to hold, just a passing glance


def _nearest_walkable_cell(observation, cell, max_radius=15):
    """Return the closest walkable cell to one that may itself be blocked (e.g. a prop's footprint)."""
    if layout.walkable(observation, cell):
        return cell
    for radius in range(1, max_radius + 1):
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                if max(abs(dx), abs(dy)) != radius:
                    continue
                candidate = {"x": cell["x"] + dx, "y": cell["y"] + dy}
                if layout.walkable(observation, candidate):
                    return candidate
    return cell


def _bfs_path(observation, start_cell, dest_cell):
    """Shortest cardinal-step path of cells from start to dest, or None if unreachable."""
    if start_cell["x"] == dest_cell["x"] and start_cell["y"] == dest_cell["y"]:
        return []
    dest_key = (dest_cell["x"], dest_cell["y"])
    visited = {(start_cell["x"], start_cell["y"])}
    queue = deque([(start_cell, [])])
    while queue:
        current, path = queue.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = {"x": current["x"] + dx, "y": current["y"] + dy}
            key = (neighbor["x"], neighbor["y"])
            if key in visited:
                continue
            if not layout.can_step(observation, current, neighbor):
                continue
            if key == dest_key:
                return path + [neighbor]
            visited.add(key)
            queue.append((neighbor, path + [neighbor]))
    return None


class Agent:
    """Leaves home, tends its plot, wanders the village, and reacts to people it sees."""

    def reset(self, seed: int, observation: ThreeBranchesObservation) -> None:
        """Initialize per-day state: home, plot, personality, and tracking structures."""

        # Home & doorway (static for the day)
        self.home = me.home(observation)
        self.home_doorway = layout.doorway(observation, self.home) if self.home != "none" else None

        # Claim closest plot to home
        here = me.position(observation)
        plots = [prop for prop in props.all(observation) if prop["type"] == "plot"]
        self.claimed_plot = min(
            plots,
            key=lambda p: geometry.distance(here, _cell_centre(p["cell"])),
        ) if plots else None

        # Personality: which destination-picking strategy this villager follows all day
        rng = me.rng(observation, seed)
        self.personality = rng.choice(["wander_random", "visit_building", "seek_tasks"])
        self.rng = rng  # kept for destination picks and random emotes during the day

        # Day-phase tracking
        self.phase = "plot"  # "plot" -> "wander" -> "returning"
        self.used_props = set()  # prop ids already used today, never repeated
        self.greeted = {}  # {player_id: last_greeted_tick}, per-person 10-tick cooldown

        # Destination & task state
        self.current_destination = None  # position dict to walk toward
        self.active_task = None  # {"prop_id": str, "ticks_remaining": int} while mid-use
        self.use_counter = 0

        # Pathfinding cache
        self._path = None  # cached cardinal-step path to current destination
        self._path_destination = None  # (x, y) tuple of cached path's target
        self.stuck_ticks = 0  # consecutive near-zero-movement ticks while walking a destination

    def _walk_toward(self, destination: dict[str, float], observation: ThreeBranchesObservation) -> float:
        """Heading toward destination, following a cached path around obstacles."""
        here = me.position(observation)
        here_cell = layout.cell_at(observation, here)
        dest_cell = layout.cell_at(observation, destination)
        if here_cell is None or dest_cell is None:
            return geometry.heading_to(here, destination)
        dest_cell = _nearest_walkable_cell(observation, dest_cell)

        cache_key = (dest_cell["x"], dest_cell["y"])
        if self._path_destination != cache_key or self._path is None:
            self._path = _bfs_path(observation, here_cell, dest_cell) or []
            self._path_destination = cache_key

        while self._path and self._path[0]["x"] == here_cell["x"] and self._path[0]["y"] == here_cell["y"]:
            self._path.pop(0)

        if not self._path:
            return geometry.heading_to(here, destination)
        return geometry.heading_to(here, _cell_centre(self._path[0]))

    def _pick_destination(self, observation: ThreeBranchesObservation) -> dict[str, float]:
        """Pick the next place to head, per this villager's personality. Always returns an
        actually-walkable point, since a prop or building cell can itself be blocked by
        collision (a raw prop cell led to villagers oscillating against it)."""
        here = me.position(observation)

        if self.personality == "wander_random":
            for _ in range(20):
                angle = math.radians(self.rng.uniform(0.0, 360.0))
                reach = self.rng.uniform(5.0, 30.0)
                point = {"x": here["x"] + reach * math.cos(angle), "y": here["y"] + reach * math.sin(angle)}
                cell = layout.cell_at(observation, point)
                if cell is not None and layout.walkable(observation, cell):
                    return _cell_centre(cell)
            return here

        if self.personality == "visit_building":
            candidates = list(layout.buildings(observation))
            self.rng.shuffle(candidates)
            for building in candidates:
                doorway = layout.doorway(observation, building["id"])
                if doorway is not None:
                    return doorway
            return here

        # "seek_tasks"
        candidates = [
            prop for prop in props.all(observation)
            if prop["type"] in _TASK_TYPES and prop["id"] not in self.used_props
        ]
        if candidates:
            cell = self.rng.choice(candidates)["cell"]
            return _cell_centre(_nearest_walkable_cell(observation, cell))
        return here

    def act(self, observation: ThreeBranchesObservation) -> ThreeBranchesAction:
        """Choose one action from current observation and persistent day state."""

        here = me.position(observation)
        heading = me.heading(observation)

        # Phase: plot (tend home plot for 150 ticks, then switch to wander)
        if self.phase == "plot":
            if self.active_task is None:
                # Initialize plot task
                self.active_task = {"prop_id": self.claimed_plot["id"], "ticks_remaining": 150}
                self.use_counter = 0

            if self.use_counter >= self.active_task["ticks_remaining"]:
                # Done tending plot
                self.used_props.add(self.claimed_plot["id"])
                self.phase = "wander"
                self.active_task = None
                self.use_counter = 0
            else:
                # Walk to plot or use it if close enough
                plot_pos = _cell_centre(self.claimed_plot["cell"])
                dist_to_plot = geometry.distance(here, plot_pos)

                if dist_to_plot < 1.5:  # Close enough to use (prop_reach is 1.5)
                    self.use_counter += 1
                    return action.stand(heading, "use")
                else:
                    return action.walk(self._walk_toward(plot_pos, observation), 1.0, "none")

        # Phase: wander (walk to a personality-driven destination, using anything usable
        # spotted along the way, sweeping at the end of each leg, then picking a new one)
        if self.phase == "wander":
            if self.active_task is None:
                usable = props.usable(observation)
                if usable is not None and usable["id"] not in self.used_props:
                    self.active_task = {"prop_id": usable["id"], "ticks_remaining": _prop_use_ticks(usable["type"])}
                    self.use_counter = 0

            if self.active_task is not None:
                if self.use_counter >= self.active_task["ticks_remaining"]:
                    self.used_props.add(self.active_task["prop_id"])
                    self.active_task = None
                    self.use_counter = 0
                else:
                    self.use_counter += 1
                    return action.stand(heading, "use")

            if self.current_destination is None:
                # Deciding beat: pick where to head next and show it with a random emote
                self.current_destination = self._pick_destination(observation)
                self.stuck_ticks = 0
                self._path = None  # force a fresh path for the new destination
                return action.stand(heading, self.rng.choice(_IDLE_EMOTES))

            if geometry.distance(here, self.current_destination) < 2.0:
                # Arrived: sweep, then pick a fresh destination next tick
                self.current_destination = None
                return action.stand(heading, "sweep")

            # Give up on a destination that isn't actually reachable instead of circling on it
            if me.moved(observation) < 0.05:
                self.stuck_ticks += 1
            else:
                self.stuck_ticks = 0
            if self.stuck_ticks >= _STUCK_TICKS_LIMIT:
                self.current_destination = None
                self.stuck_ticks = 0
                self._path = None
                return action.stand(heading, "shrug")

            return action.walk(self._walk_toward(self.current_destination, observation), 1.0, "none")

        # Placeholder for the returning phase (step 7)
        return action.stand(heading, "none")

    # Optional: messaging. On your turn, chat receives messages addressed to your player since
    # its previous turn. Return messages with a recipient and text, or nothing to stay silent.
    # Use None as the recipient to broadcast. Every message is recorded and shown in replays.
    #
    # def chat(self, inbox: list[dict]) -> list[dict] | None:
    #     ...
