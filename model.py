from dataclasses import dataclass
import collections
from typing import Any


class CaseInsensitiveDict(collections.Mapping):
    def __init__(self, d: dict[str, Any]):
        self._d = {k.lower(): v for k, v in d.items()}

    def __contains__(self, k):
        return k.lower() in self._d

    def __len__(self):
        return len(self._d)

    def __iter__(self):
        return iter(self._d)

    def __getitem__(self, k):
        return self._d[k.lower()]
    
    def __setitem__(self, k, v):
        self._d[k.lower()] = v

    def pop(self, k):
        self._d.pop(k.lower())
    
    def __repr__(self):
        return repr(self._d)
    
    def __str__(self):
        return str(self._d)


@dataclass
class Player:
    name: str
    points: int = 1
    paused: bool = False


@dataclass
class AssassinConfig:
    save_path: str
    debug_allow: set[int]
    channel: int


@dataclass
class GameState:
    players: CaseInsensitiveDict[str, Player]
    assassin_day: int