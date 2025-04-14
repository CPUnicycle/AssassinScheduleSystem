from dataclasses import dataclass
from collections.abc import Mapping 
from typing import Any

class CaseInsensitiveDict(Mapping):
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
class Statistic:
    tagger: bool = False
    person: str = ''
    verb: str = ''
    point_i: int = 0
    point_f: int = 0
    date: str = ''


@dataclass
class Player:
    name: str
    discID: int
    points: int = 1
    week_points: int = 0
    paused: bool = False
    stat_list: tuple = ()
    # and have a way to track stats
    # Maybe a list with data on every tag that occurs
    #   blueshell means was the blueshell active on the player who was tagged
    # [
    #   [tag/tagged, who, points_exchanged, date/time, verb, blueshell],
    #   [tag/tagged ... ],
    #   []
    # ]
    #   Number Tags/Tagged (and KDR)
    #   Avg pts/tag
    #   Favorite Victim
    #   Most common antagonist
    #   Blue Shells for/against
    # Stats for whole game
    #   Highest value tag
    #   Bloodiest day
    #   Most tags in a day
    #   Blueshelled the most
    #   Used the most blueshells


@dataclass
class AssassinConfig:
    save_path: str
    debug_allow: set[int]
    channel: int
    controlchan: int
    operator: str = ''
    playerrole: int = 0


@dataclass
class GameState:
    players: CaseInsensitiveDict[str, Player]
    assassin_day: int
    wait_clock: int = 0
    game_clock: int = 0
    game_over: bool = False
    score_msg: int = 0
    round_msg: int = 0
    game_waiting: bool = False
    game_active: bool = False
    players_running: tuple = ()
    runner: int = 0
    today_selected: bool = False
    # [8:55, 9:55, 10:55, 11:55, 12:55, 13:55, 14:55, 15:55, 16:55, 17:55]
    time_probabilities: tuple = (0.1, 0.2, 0.3, 0.4, 0.5, 0.5, 0.4, 0.4, 0.3, 0.2)
    times_selected: tuple = ()
    temp_times_selected: tuple = ()


