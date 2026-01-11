from dataclasses import dataclass


@dataclass
class StockfishVersion:
    text: str
    major_minor: str = ""
    major: int = 0
    minor: int = 0
    patch: str = ""
    sha: str = ""
    is_dev_build: bool = False


@dataclass
class StockfishParameters:
    debug_log_file: str
    threads: int
    hash: int
    ponder: bool
    multipv: int
    skill_level: int
    move_overhead: int
    slow_mover: int
    uci_chess960: bool
    uci_limit_strength: bool
    uci_elo: int
    contempt: int
    min_split_depth: int
    minimum_thinking_time: int
    uci_show_wdl: bool | None = None

    def to_dict(self) -> dict[str, str | int | bool]:
        mappings: dict[str, str | int | bool | None] = {
            "Debug Log File": self.debug_log_file,
            "Threads": self.threads,
            "Hash": self.hash,
            "Ponder": self.ponder,
            "MultiPV": self.multipv,
            "Skill Level": self.skill_level,
            "Move Overhead": self.move_overhead,
            "Slow Mover": self.slow_mover,
            "UCI_Chess960": self.uci_chess960,
            "UCI_LimitStrength": self.uci_limit_strength,
            "UCI_Elo": self.uci_elo,
            "Contempt": self.contempt,
            "Min Split Depth": self.min_split_depth,
            "Minimum Thinking Time": self.minimum_thinking_time,
            "UCI_ShowWDL": self.uci_show_wdl,
        }
        return {k: v for k, v in mappings.items() if v is not None}

    def update(self, params: dict[str, str | int | bool]) -> None:
        mappings: dict[str, str] = {
            "Debug Log File": "debug_log_file",
            "Hash": "hash",
            "MultiPV": "multipv",
            "Skill Level": "skill_level",
            "UCI_LimitStrength": "uci_limit_strength",
            "Threads": "threads",
            "Ponder": "ponder",
            "Move Overhead": "move_overhead",
            "Slow Mover": "slow_mover",
            "UCI_Chess960": "uci_chess960",
            "UCI_Elo": "uci_elo",
            "Contempt": "contempt",
            "Min Split Depth": "min_split_depth",
            "Minimum Thinking Time": "minimum_thinking_time",
            "UCI_ShowWDL": "uci_show_wdl",
        }

        for dict_key, value in params.items():
            field_name = mappings.get(dict_key)
            if field_name is None:
                continue
            if (
                type(getattr(self, field_name)) is not type(value)
                and field_name != "uci_show_wdl"
            ):
                raise ValueError("wrong type")
            setattr(self, field_name, value)


@dataclass
class MoveEvaluation:
    move: str
    centipawn: int | None
    mate: int | None
    time: int | None = None
    nodes: int | None = None
    multipv_number: int | None = None
    nodes_per_second: int | None = None
    selective_depth: int | None = None
    pv_moves: str | None = None
    wdl: str | None = None

    def to_dict(self) -> dict[str, str | int | None]:
        mappings: dict[str, str | int | None] = {
            "Move": self.move,
            "Centipawn": self.centipawn,
            "Mate": self.mate,
            "Time": self.time,
            "Nodes": self.nodes,
            "MultiPVNumber": self.multipv_number,
            "NodesPerSecond": self.nodes_per_second,
            "SelectiveDepth": self.selective_depth,
            "PVMoves": self.pv_moves,
            "WDL": self.wdl,
        }
        return {
            k: v
            for k, v in mappings.items()
            if v is not None or k in ("Centipawn", "Mate")
        }


class StockfishException(Exception):
    pass
