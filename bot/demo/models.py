from dataclasses import dataclass, field


@dataclass
class PlayerStats:
    steamid: str
    name: str

    kills: int = 0
    deaths: int = 0
    assists: int = 0
    headshot_kills: int = 0

    knife_deaths: int = 0
    zeus_deaths: int = 0
    world_deaths: int = 0
    suicides: int = 0
    noscoped_deaths: int = 0
    wallbang_deaths: int = 0
    smoke_deaths: int = 0
    first_deaths: int = 0

    teamflash_count: int = 0
    teamflash_seconds: float = 0.0
    team_damage: int = 0
    teamkills: int = 0

    shots_fired: int = 0
    shots_hit: int = 0

    @property
    def kd(self) -> float:
        return self.kills / self.deaths if self.deaths else float(self.kills)

    @property
    def accuracy(self) -> float:
        return self.shots_hit / self.shots_fired if self.shots_fired else 0.0


@dataclass
class MatchStats:
    map_name: str
    rounds: int
    players: dict[str, PlayerStats] = field(default_factory=dict[str, PlayerStats])

    def player(self, steamid: str, name: str) -> PlayerStats:
        if steamid not in self.players:
            self.players[steamid] = PlayerStats(steamid=steamid, name=name)
        return self.players[steamid]
