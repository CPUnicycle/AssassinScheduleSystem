from dataclasses import dataclass


@dataclass
class Player:
    name: str
    points: int = 1
    paused: bool = False


@dataclass
class GameState:
    players: dict[str, Player]
    assassin_day: int