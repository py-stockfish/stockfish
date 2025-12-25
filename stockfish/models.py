"""
This module implements the Stockfish class.

Copyright (c) 2016-2025 by Ilya Zhelyabuzhsky and contributors.
Contributors: https://github.com/py-stockfish/stockfish/graphs/contributors
License: MIT. See LICENSE for more details.
"""
from __future__ import annotations
import subprocess
from typing import Any
import copy
import os
from dataclasses import dataclass
from enum import Enum
import re
import datetime
import warnings


class Stockfish:
    """Integrates the [Stockfish chess engine](https://stockfishchess.org/) with Python."""

    _del_counter = 0
    # Used in test_models: will count how many times the del function is called.

    _RELEASES = {
        "16.0": "2023-06-30",
        "15.1": "2022-12-04",
        "15.0": "2022-04-18",
        "14.1": "2021-10-28",
        "14.0": "2021-07-02",
        "13.0": "2021-02-19",
        "12.0": "2020-09-02",
        "11.0": "2020-01-18",
        "10.0": "2018-11-29",
    }

    _PIECE_CHARS = ("P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k")

    # _PARAM_RESTRICTIONS stores the types of each of the params, and any applicable min and max values, based
    # off the Stockfish source code: https://github.com/official-stockfish/Stockfish/blob/65ece7d985291cc787d6c804a33f1dd82b75736d/src/ucioption.cpp#L58-L82
    _PARAM_RESTRICTIONS: dict[str, tuple[type, int | None, int | None]] = {
        "Debug Log File": (str, None, None),
        "Threads": (int, 1, 1024),
        "Hash": (int, 1, 2048),
        "Ponder": (bool, None, None),
        "MultiPV": (int, 1, 500),
        "Skill Level": (int, 0, 20),
        "Move Overhead": (int, 0, 5000),
        "Slow Mover": (int, 10, 1000),
        "UCI_Chess960": (bool, None, None),
        "UCI_LimitStrength": (bool, None, None),
        "UCI_Elo": (int, 1320, 3190),
        "Contempt": (int, -100, 100),
        "Min Split Depth": (int, 0, 12),
        "Minimum Thinking Time": (int, 0, 5000),
        "UCI_ShowWDL": (bool, None, None),
    }
    """
        _PARAM_RESTRICTIONS stores the types of each of the params, and any applicable min and max values, based off the Stockfish
        source code: https://github.com/official-stockfish/Stockfish/blob/65ece7d985291cc787d6c804a33f1dd82b75736d/src/ucioption.cpp#L58-L82
    """

    def __init__(
        self,
        path: str = "stockfish",
        depth: int = 15,
        parameters: dict | None = None,
        num_nodes: int = 1000000,
        turn_perspective: bool = True,
        debug_view: bool = False,
    ) -> None:
        """Initializes the Stockfish engine.

        Example:
        >>> from stockfish import Stockfish
        >>> stockfish = Stockfish()
        """
        self._DEFAULT_STOCKFISH_PARAMS = {
            "Debug Log File": "",
            "Contempt": 0,
            "Min Split Depth": 0,
            "Threads": 1,
            "Ponder": False,
            "Hash": 16,
            "MultiPV": 1,
            "Skill Level": 20,
            "Move Overhead": 10,
            "Minimum Thinking Time": 20,
            "Slow Mover": 100,
            "UCI_Chess960": False,
            "UCI_LimitStrength": False,
            "UCI_Elo": 1350,
        }
        self._debug_view: bool = debug_view

        self._path: str = path
        self._stockfish = subprocess.Popen(
            self._path,
            universal_newlines=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self._has_quit_command_been_sent: bool = False

        self._set_stockfish_version()

        self._put("uci")

        self.set_depth(depth)
        self.set_num_nodes(num_nodes)
        self.set_turn_perspective(turn_perspective)

        self.info: str = ""

        self._parameters: dict = {}
        self.update_engine_parameters(self._DEFAULT_STOCKFISH_PARAMS)
        self.update_engine_parameters(parameters)

        if self.does_current_engine_version_have_wdl_option():
            self._set_option("UCI_ShowWDL", True, False)

        self._prepare_for_new_position(True)

    def set_debug_view(self, activate: bool) -> None:
        self._debug_view = activate

    def get_engine_parameters(self) -> dict:
        """Returns the current engine parameters being used.

        Returns:
            A deep copy of the dictionary storing the current engine parameters.
        """
        return copy.deepcopy(self._parameters)

    def get_parameters(self) -> dict:
        """Returns the current engine parameters being used. *Deprecated, see `get_engine_parameters()` instead*."""

        raise ValueError(
            """The values for 'Ponder', 'UCI_Chess960', and 'UCI_LimitStrength' have been updated from
               strings to bools in a new release of the python stockfish package. As a result, this
               'get_parameters()' function has been deprecated, in an effort to avoid existing users
               unknowingly getting bugs. It has been replaced with 'get_engine_parameters()'."""
        )

    def update_engine_parameters(self, parameters: dict | None) -> None:
        """Updates the Stockfish engine parameters.

        Args:
            parameters:
                Contains (key, value) pairs which will be used to update
                the Stockfish engine's current parameters.

        Example:
            >>> stockfish.update_engine_parameters({'Threads': 2})
        """
        if not parameters:
            return

        new_param_values = copy.deepcopy(parameters)

        for key in new_param_values:
            if len(self._parameters) > 0 and key not in self._parameters:
                raise ValueError(f"'{key}' is not a key that exists.")
            if key in (
                "Ponder",
                "UCI_Chess960",
                "UCI_LimitStrength",
            ) and not isinstance(new_param_values[key], bool):
                raise ValueError(
                    f"The value for the '{key}' key has been updated from a string to a bool in a new release of the python stockfish package."
                )
            self._validate_param_val(key, new_param_values[key])

        if ("Skill Level" in new_param_values) != (
            "UCI_Elo" in new_param_values
        ) and "UCI_LimitStrength" not in new_param_values:
            # This means the user wants to update the Skill Level or UCI_Elo (only one,
            # not both), and that they didn't specify a new value for UCI_LimitStrength.
            # So, update UCI_LimitStrength, in case it's not the right value currently.
            if "Skill Level" in new_param_values:
                new_param_values.update({"UCI_LimitStrength": False})
            elif "UCI_Elo" in new_param_values:
                new_param_values.update({"UCI_LimitStrength": True})

        if "Threads" in new_param_values:
            # Recommended to set the hash param after threads.
            threads_value = new_param_values["Threads"]
            del new_param_values["Threads"]
            hash_value = None
            if "Hash" in new_param_values:
                hash_value = new_param_values["Hash"]
                del new_param_values["Hash"]
            else:
                hash_value = self._parameters["Hash"]
            new_param_values["Threads"] = threads_value
            new_param_values["Hash"] = hash_value

        for name, value in new_param_values.items():
            self._set_option(name, value)
        self.set_fen_position(self.get_fen_position(), False)
        # Getting SF to set the position again, since UCI option(s) have been updated.

    def reset_engine_parameters(self) -> None:
        """Resets the Stockfish engine parameters."""
        self.update_engine_parameters(self._DEFAULT_STOCKFISH_PARAMS)

    def _prepare_for_new_position(self, send_ucinewgame_token: bool = True) -> None:
        if send_ucinewgame_token:
            self._put("ucinewgame")
        self._is_ready()
        self.info = ""

    def _put(self, command: str) -> None:
        if not self._stockfish.stdin:
            raise BrokenPipeError()
        if self._stockfish.poll() is None and not self._has_quit_command_been_sent:
            if self._debug_view:
                print(f">>> {command}\n")
            self._stockfish.stdin.write(f"{command}\n")
            self._stockfish.stdin.flush()
            if command == "quit":
                self._has_quit_command_been_sent = True

    def _read_line(self) -> str:
        if not self._stockfish.stdout:
            raise BrokenPipeError()
        if self._stockfish.poll() is not None:
            raise StockfishException("The Stockfish process has crashed")
        line = self._stockfish.stdout.readline().strip()
        if self._debug_view:
            print(line)
        return line

    def _discard_remaining_stdout_lines(self, substr_in_last_line: str) -> None:
        """Calls _read_line() until encountering `substr_in_last_line` in the line."""
        while substr_in_last_line not in self._read_line():
            pass

    def _set_option(
        self, name: str, value: Any, update_parameters_attribute: bool = True
    ) -> None:
        self._validate_param_val(name, value)
        str_rep_value = str(value)
        if isinstance(value, bool):
            str_rep_value = str_rep_value.lower()
        self._put(f"setoption name {name} value {str_rep_value}")
        if update_parameters_attribute:
            self._parameters.update({name: value})
        self._is_ready()

    def _validate_param_val(self, name: str, value: Any) -> None:
        if name not in Stockfish._PARAM_RESTRICTIONS:
            raise ValueError(f"{name} is not a supported engine parameter")
        required_type, minimum, maximum = Stockfish._PARAM_RESTRICTIONS[name]
        if type(value) is not required_type:
            raise ValueError(f"{value} is not of type {required_type}")
        if minimum is not None and type(value) is int and value < minimum:
            raise ValueError(f"{value} is below {name}'s minimum value of {minimum}")
        if maximum is not None and type(value) is int and value > maximum:
            raise ValueError(f"{value} is over {name}'s maximum value of {maximum}")

    def _is_ready(self) -> None:
        self._put("isready")
        while self._read_line() != "readyok":
            pass

    def _go(self) -> None:
        self._put(f"go depth {self._depth}")

    def _go_nodes(self) -> None:
        self._put(f"go nodes {self._num_nodes}")

    def _go_time(self, time: int) -> None:
        self._put(f"go movetime {time}")

    def _go_remaining_time(self, wtime: int | None, btime: int | None) -> None:
        cmd = "go"
        if wtime is not None:
            cmd += f" wtime {wtime}"
        if btime is not None:
            cmd += f" btime {btime}"
        self._put(cmd)

    def _go_perft(self, depth: int) -> None:
        self._put(f"go perft {depth}")

    def _on_weaker_setting(self) -> bool:
        return (
            self._parameters["UCI_LimitStrength"]
            or self._parameters["Skill Level"] < 20
        )

    def _weaker_setting_warning(self, message: str) -> None:
        """Will issue a warning, referring to the function that calls this one."""
        warnings.warn(message, stacklevel=3)

    def set_fen_position(
        self, fen_position: str, send_ucinewgame_token: bool = True
    ) -> None:
        """Sets current board position in Forsyth-Edwards notation (FEN).

        Args:
            fen_position:
                FEN string of board position.

            send_ucinewgame_token:
                Whether to send the `ucinewgame` token to the Stockfish engine.
                The most prominent effect this will have is clearing Stockfish's transposition table,
                which should be done if the new position is unrelated to the current position.

        Example:
            >>> stockfish.set_fen_position("1nb1k1n1/pppppppp/8/6r1/5bqK/6r1/8/8 w - - 2 2")
        """
        self._prepare_for_new_position(send_ucinewgame_token)
        self._put(f"position fen {fen_position}")

    def set_position(self, moves: list[str] | None = None) -> None:
        """Sets current board position.

        Args:
            moves:
                A list of moves to set this position on the board. Must be in pure algebraic coordinate notation.

        Example:
            >>> stockfish.set_position(['e2e4', 'e7e5'])
        """
        self.set_fen_position(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1", True
        )
        self.make_moves_from_current_position(moves)

    def make_moves_from_current_position(self, moves: list[str] | None) -> None:
        """Sets a new position by playing the moves from the current position.

        Args:
            moves:
              A list of moves to play in the current position, in order to reach a new position.
              Must be in pure algebraic coordinate notation.

        Example:
            >>> stockfish.make_moves_from_current_position(["g4d7", "a8b8", "f1d1"])
        """
        if not moves:
            return
        self._prepare_for_new_position(False)
        for move in moves:
            if not self.is_move_correct(move):
                raise ValueError(f"Cannot make move: {move}")
            self._put(f"position fen {self.get_fen_position()} moves {move}")

    def get_board_visual(self, perspective_white: bool = True) -> str:
        """Returns a visual representation of the current board position.

        Args:
            perspective_white:
                A boolean that indicates whether the board should be displayed from the
                perspective of white. `True` indicates White's perspective.

        Returns:
            A visual representation of the chessboard in the current position.

            For example:
            ```
            +---+---+---+---+---+---+---+---+
            | r | n | b | q | k | b | n | r | 8
            +---+---+---+---+---+---+---+---+
            | p | p | p | p | p | p | p | p | 7
            +---+---+---+---+---+---+---+---+
            |   |   |   |   |   |   |   |   | 6
            +---+---+---+---+---+---+---+---+
            |   |   |   |   |   |   |   |   | 5
            +---+---+---+---+---+---+---+---+
            |   |   |   |   |   |   |   |   | 4
            +---+---+---+---+---+---+---+---+
            |   |   |   |   |   |   |   |   | 3
            +---+---+---+---+---+---+---+---+
            | P | P | P | P | P | P | P | P | 2
            +---+---+---+---+---+---+---+---+
            | R | N | B | Q | K | B | N | R | 1
            +---+---+---+---+---+---+---+---+
              a   b   c   d   e   f   g   h
            ```
        """
        self._put("d")
        board_rep_lines: list[str] = []
        count_lines: int = 0
        while count_lines < 17:
            board_str: str = self._read_line()
            if "+" in board_str or "|" in board_str:
                count_lines += 1
                if perspective_white:
                    board_rep_lines.append(f"{board_str}")
                else:
                    # If the board is to be shown from black's point of view, all lines are
                    # inverted horizontally and at the end the order of the lines is reversed.
                    board_part = board_str[:33]
                    # To keep the displayed numbers on the right side,
                    # only the string representing the board is flipped.
                    number_part = board_str[33:] if len(board_str) > 33 else ""
                    board_rep_lines.append(f"{board_part[::-1]}{number_part}")
        if not perspective_white:
            board_rep_lines = board_rep_lines[::-1]
        board_str = self._read_line()
        if "a   b   c" in board_str:
            # Engine being used is recent enough to have coordinates, so add them:
            if perspective_white:
                board_rep_lines.append(f"  {board_str}")
            else:
                board_rep_lines.append(f"  {board_str[::-1]}")
        self._discard_remaining_stdout_lines("Checkers")
        # "Checkers" is in the last line outputted by Stockfish for the "d" command.
        board_rep = "\n".join(board_rep_lines) + "\n"
        return board_rep

    def get_fen_position(self) -> str:
        """Returns the current board position in Forsyth-Edwards notation (FEN).

        Returns:
            A string of the current board position in Forsyth-Edwards notation (FEN).
            For example: `rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1`
        """
        self._put("d")
        while True:
            text = self._read_line()
            splitted_text = text.split(" ")
            if splitted_text[0] == "Fen:":
                self._discard_remaining_stdout_lines("Checkers")
                return " ".join(splitted_text[1:])

    def set_skill_level(self, skill_level: int = 20) -> None:
        """Sets the skill level of the stockfish engine.

        Args:
            skill_level:
              Skill Level option between 0 (weakest level) and 20 (full strength).

        Example:
            >>> stockfish.set_skill_level(10)
        """
        self.update_engine_parameters(
            {"UCI_LimitStrength": False, "Skill Level": skill_level}
        )

    def set_elo_rating(self, elo_rating: int = 1350) -> None:
        """Sets the elo rating of the Stockfish engine, ignoring skill level.

        Args:
            elo_rating:
                Gets Stockfish to approximate the strength of the given elo.

        Example:
            >>> stockfish.set_elo_rating(2500)
        """
        self.update_engine_parameters(
            {"UCI_LimitStrength": True, "UCI_Elo": elo_rating}
        )

    def resume_full_strength(self) -> None:
        """Puts Stockfish back to full strength, if you've previously lowered the elo or skill level.

        Example:
            >>> stockfish.resume_full_strength()
        """
        self.update_engine_parameters({"UCI_LimitStrength": False, "Skill Level": 20})

    def set_depth(self, depth: int = 15) -> None:
        """Sets the search depth of the Stockfish engine.

        Args:
            depth: The depth should be a positive integer.

        Example:
            >>> stockfish.set_depth(16)
        """
        if not isinstance(depth, int) or depth < 1 or isinstance(depth, bool):
            raise TypeError("depth must be an integer higher than 0")
        self._depth = depth

    def get_depth(self) -> int:
        """Returns an int conveying the configured search depth."""
        return self._depth

    def set_num_nodes(self, num_nodes: int = 1000000) -> None:
        """Sets the number of nodes for Stockfish to explore during its search.

        Args:
            num_nodes: Number of nodes for Stockfish to search.

        Example:
            >>> stockfish.set_num_nodes(1000000)
        """
        if (
            not isinstance(num_nodes, int)
            or isinstance(num_nodes, bool)
            or num_nodes < 1
        ):
            raise TypeError("num_nodes must be an integer higher than 0")
        self._num_nodes: int = num_nodes

    def get_num_nodes(self) -> int:
        """Returns the configured number of nodes for Stockfish to search."""
        return self._num_nodes

    def set_turn_perspective(self, turn_perspective: bool = True) -> None:
        """Sets the turn perspective of centipawn and WDL evaluations.

        Args:
            turn_perspective:
              Represents whether the perspective of evaluation should be turn-based
              (i.e., positive if it favours whose turn it is, which is what Stockfish does by default).
              This function's default value for the `turn_perspective` parameter is `True`;
              if `False`, subsequent evaluations will be from White's perspective.

        Example:
            >>> stockfish.set_turn_perspective(False)
        """
        if not isinstance(turn_perspective, bool):
            raise TypeError("`turn_perspective` must be a bool")
        self._turn_perspective = turn_perspective

    def get_turn_perspective(self) -> bool:
        """Returns whether centipawn and WDL values are set from turn perspective."""
        return self._turn_perspective

    def get_best_move(
        self, wtime: int | None = None, btime: int | None = None
    ) -> str | None:
        """Returns the best move in the current position on the board.
        `wtime` and `btime` arguments influence the search only if provided.

        Args:
            wtime:
                Time for white player in milliseconds.
            btime:
                Time for black player in milliseconds.

        Returns:
            A string of the best move in pure algebraic coordinate notation, or `None` if it's a mate now.

        Example:
            >>> move = stockfish.get_best_move(wtime=1000, btime=1000)
        """
        if wtime is not None or btime is not None:
            self._go_remaining_time(wtime, btime)
        else:
            self._go()
        return self._get_best_move_from_sf_popen_process()

    def get_best_move_time(self, time: int = 1000) -> str | None:
        """Returns the best move in the current position after a determined time.

        Args:
            time:
                Time for Stockfish to determine the best move (milliseconds).

        Returns:
            A string of a move in pure algebraic coordinate notation, or `None` if it's a mate now.

        Example:
            >>> move = stockfish.get_best_move_time(1000)
        """
        self._go_time(time)
        return self._get_best_move_from_sf_popen_process()

    def _get_best_move_from_sf_popen_process(self) -> str | None:
        """Precondition - a "go" command must have been sent to SF before calling this function.
        This function needs existing output to read from the SF popen process."""

        lines: list[str] = self._get_sf_go_command_output()
        self.info = lines[-2]
        last_line_split = lines[-1].split(" ")
        return None if last_line_split[1] == "(none)" else last_line_split[1]

    def _get_sf_go_command_output(self) -> list[str]:
        """Precondition - a "go" command must have been sent to SF before calling this function.
        This function needs existing output to read from the SF popen process.

        A list of strings is returned, where each string represents a line of output."""

        lines: list[str] = []
        while True:
            lines.append(self._read_line())
            if lines[-1].startswith("bestmove"):
                # The "bestmove" line is the last line of the output.
                return lines

    @staticmethod
    def _is_fen_syntax_valid(fen: str) -> bool:
        # Code for this function taken from: https://gist.github.com/Dani4kor/e1e8b439115878f8c6dcf127a4ed5d3e
        # Some small changes have been made to the code.
        if not re.match(
            r"\s*^(((?:[rnbqkpRNBQKP1-8]+\/){7})[rnbqkpRNBQKP1-8]+)\s([b|w])\s(-|[K|Q|k|q]{1,4})\s(-|[a-h][1-8])\s(\d+\s\d+)$",
            fen,
        ):
            return False

        fen_fields = fen.split()

        if any(
            (
                len(fen_fields) != 6,
                len(fen_fields[0].split("/")) != 8,
                any(x not in fen_fields[0] for x in "Kk"),
                any(not fen_fields[x].isdigit() for x in (4, 5)),
                int(fen_fields[4]) >= int(fen_fields[5]) * 2,
            )
        ):
            return False

        for fenPart in fen_fields[0].split("/"):
            field_sum: int = 0
            previous_was_digit: bool = False
            for c in fenPart:
                if "1" <= c <= "8":
                    if previous_was_digit:
                        return False  # Two digits next to each other.
                    field_sum += int(c)
                    previous_was_digit = True
                elif c in Stockfish._PIECE_CHARS:
                    field_sum += 1
                    previous_was_digit = False
                else:
                    return False  # Invalid character.
            if field_sum != 8:
                return False  # One of the rows doesn't have 8 columns.
        return True

    def is_fen_valid(self, fen: str) -> bool:
        """Checks if the FEN string is valid.

        Returns:
            `True` if valid, `False` otherwise.

        Example:
            >>> is_valid = stockfish.is_fen_valid("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
        """
        if not Stockfish._is_fen_syntax_valid(fen):
            return False
        temp_sf: Stockfish = Stockfish(path=self._path, parameters={"Hash": 1})
        # Using a new temporary SF instance, in case the fen is an illegal position that causes
        # the SF process to crash.
        best_move: str | None = None
        temp_sf.set_fen_position(fen, False)
        try:
            temp_sf._put("go depth 10")
            best_move = temp_sf._get_best_move_from_sf_popen_process()
        except StockfishException:
            # If a StockfishException is thrown, then it happened in read_line() since the SF process crashed.
            # This is likely due to the position being illegal, so set the var to false:
            return False
        else:
            return best_move is not None
        finally:
            temp_sf.__del__()
            # Calling this function before returning from either the except or else block above.
            # The __del__ function should generally be called implicitly by python when this
            # temp_sf object goes out of scope, but calling it explicitly guarantees this will happen.

    def is_move_correct(self, move_value: str) -> bool:
        """Checks if the passed in move is legal.

        Args:
            move_value:
              New move value in pure algebraic coordinate notation.

        Returns:
            `True` if the new move is legal, otherwise `False`.

        Example:
            >>> is_correct = stockfish.is_move_correct("f4f5")
        """
        old_self_info = self.info
        self._put(f"go depth 1 searchmoves {move_value}")
        is_move_correct = self._get_best_move_from_sf_popen_process() is not None
        self.info = old_self_info
        return is_move_correct

    def get_wdl_stats(
        self, get_as_tuple: bool = False
    ) -> list[int] | tuple[int, int, int] | None:
        """Returns Stockfish's win/draw/loss stats for the side to move.

        Args:
            get_as_tuple:
                Option to return the wdl stats as a tuple instead of a list. Default is `False`.

        Returns:
            A list or tuple of three integers, unless the game is over (in which case
            `None` is returned).
        """

        if not self.does_current_engine_version_have_wdl_option():
            raise RuntimeError(
                "Your version of Stockfish isn't recent enough to have the UCI_ShowWDL option."
            )
        if self._on_weaker_setting():
            self._weaker_setting_warning(
                """Note that even though you've set Stockfish to play on a weaker elo or skill level,"""
                + """ get_wdl_stats will still return full strength Stockfish's wdl stats of the position."""
            )

        self._go()
        lines = self._get_sf_go_command_output()
        if lines[-1].startswith("bestmove (none)"):
            return None
        split_line = [line.split(" ") for line in lines if " multipv 1 " in line][-1]
        wdl_index = split_line.index("wdl")

        wdl_stats = [int(split_line[i]) for i in range(wdl_index + 1, wdl_index + 4)]

        if get_as_tuple:
            return (wdl_stats[0], wdl_stats[1], wdl_stats[2])
        return wdl_stats

    def does_current_engine_version_have_wdl_option(self) -> bool:
        """Returns whether the user's version of Stockfish has the option to display WDL stats."""
        self._put("uci")
        while True:
            splitted_text = self._read_line().split(" ")
            if splitted_text[0] == "uciok":
                return False
            elif "UCI_ShowWDL" in splitted_text:
                self._discard_remaining_stdout_lines("uciok")
                return True

    def get_evaluation(self, searchtime: int | None = None) -> dict[str, str | int]:
        """Performs a search to evaluate the current position.

        Args:
            searchtime:
              Time for Stockfish to evaluate (milliseconds). If left as `None`, the currently configured
              search depth will be used (call `get_depth()` to see it).

        Returns:
            A dictionary of two key-value pairs: {str: str, str: int}
            - The first key is "type", and its value will be either "cp" or "mate".
              This describes the type of evaluation (centipawns or mate in x).
            - The second key is "value", and its value will be some int (representing either
              centipawns or mate in x, depending on the aforementioned "type").
        """

        if self._on_weaker_setting():
            self._weaker_setting_warning(
                """Note that even though you've set Stockfish to play on a weaker elo or skill level,"""
                + """ get_evaluation will still return full strength Stockfish's evaluation of the position."""
            )
        compare: int = (
            1 if self.get_turn_perspective() or ("w" in self.get_fen_position()) else -1
        )
        # If the user wants the evaluation specified relative to who is to move, this will be done.
        # Otherwise, the evaluation will be in terms of white's side (positive meaning advantage white,
        # negative meaning advantage black).
        if searchtime is None:
            self._go()
        else:
            self._go_time(searchtime)
        lines = self._get_sf_go_command_output()
        split_line = [line.split(" ") for line in lines if line.startswith("info")][-1]
        score_index = split_line.index("score")
        eval_type, val = split_line[score_index + 1], split_line[score_index + 2]
        return {"type": eval_type, "value": int(val) * compare}

    def get_static_eval(self) -> float | None:
        """Sends the 'eval' command to stockfish to get the static evaluation. The current position is
           'directly' evaluated -- i.e., no search is involved.

        Returns:
            A float representing the static eval, unless one side is in check or
            checkmated, in which case None is returned.
        """

        # Stockfish gives the static eval from white's perspective:
        compare: int = (
            1
            if not self.get_turn_perspective() or ("w" in self.get_fen_position())
            else -1
        )
        self._put("eval")
        while True:
            text = self._read_line()
            if any(
                text.startswith(x) for x in ("Final evaluation", "Total Evaluation")
            ):
                static_eval = text.split()[2]
                if " none " not in text:
                    self._read_line()
                    # Consume the remaining line (for some reason `eval` outputs an extra newline)
                if static_eval == "none":
                    assert "(in check)" in text
                    return None
                else:
                    return float(static_eval) * compare

    def get_top_moves(
        self,
        num_top_moves: int = 5,
        verbose: bool = False,
        num_nodes: int = 0,
    ) -> list[dict]:
        """Returns info on the top moves in the position.

        Args:
            num_top_moves:
              The number of moves for which to return information, assuming there
              are at least that many legal moves.
              Default is 5.

            verbose:
              Option to include the full info from the engine in the returned dictionary,
              including seldepth, multipv, time, nodes, nps, and wdl if available.
              Default is `False`.

            num_nodes:
              Option to search until a certain number of nodes have been searched, instead of depth.
              Default is 0.

        Returns:
            A list of dictionaries, where each dictionary contains keys for `Move`, `Centipawn`, and `Mate`.
            The corresponding value for either the `Centipawn` or `Mate` key will be `None`.
            If there are no moves in the position, an empty list is returned.

            If `verbose` is `True`, the dictionary will also include the following keys: `SelectiveDepth`, `Time`,
            `Nodes`, `NodesPerSecond`, `MultiPVLine`, and `WDL` (if available).

        Example:
            >>> moves = stockfish.get_top_moves(2, num_nodes=1000000, verbose=True)
        """
        if num_top_moves <= 0:
            raise ValueError("num_top_moves is not a positive number.")
        if self._on_weaker_setting():
            self._weaker_setting_warning(
                """Note that even though you've set Stockfish to play on a weaker elo or skill level,"""
                + """ get_top_moves will still return the top moves of full strength Stockfish."""
            )

        # remember global values
        old_multipv: int = self._parameters["MultiPV"]
        old_num_nodes: int = self._num_nodes

        # to get number of top moves, we use Stockfish's MultiPV option (i.e., multiple principal variations).
        # set MultiPV to num_top_moves requested
        if num_top_moves != self._parameters["MultiPV"]:
            self._set_option("MultiPV", num_top_moves)

        # start engine. will go until reaches self._depth or self._num_nodes
        if num_nodes == 0:
            self._go()
        else:
            self._num_nodes = num_nodes
            self._go_nodes()

        lines: list[list[str]] = [
            line.split(" ") for line in self._get_sf_go_command_output()
        ]

        # Stockfish is now done evaluating the position,
        # and the output is stored in the list 'lines'
        top_moves: list[dict] = []

        # Set perspective of evaluations. If get_turn_perspective() is True, or white to move,
        # use Stockfish's values -- otherwise, invert values.
        perspective: int = (
            1 if self.get_turn_perspective() or ("w" in self.get_fen_position()) else -1
        )

        # loop through Stockfish output lines in reverse order
        for line in reversed(lines):
            # If the line is a "bestmove" line, and the best move is "(none)", then
            # there are no top moves, and we're done. Otherwise, continue with the next line.
            if line[0] == "bestmove":
                if line[1] == "(none)":
                    top_moves = []
                    break
                continue

            # if the line has no relevant info, we're done
            if ("multipv" not in line) or ("depth" not in line):
                break

            # if we're searching depth and the line is not our desired depth, we're done
            if (num_nodes == 0) and (int(self._pick(line, "depth")) != self._depth):
                break

            # if we're searching nodes and the line has less than desired number of nodes, we're done
            if (num_nodes > 0) and (int(self._pick(line, "nodes")) < self._num_nodes):
                break

            move_evaluation: dict[str, str | int | None] = {
                # get move
                "Move": self._pick(line, "pv"),
                # get cp if available
                "Centipawn": (
                    int(self._pick(line, "cp")) * perspective if "cp" in line else None
                ),
                # get mate if available
                "Mate": (
                    int(self._pick(line, "mate")) * perspective
                    if "mate" in line
                    else None
                ),
            }

            # add more info if verbose
            if verbose:
                move_evaluation["Time"] = self._pick(line, "time")
                move_evaluation["Nodes"] = self._pick(line, "nodes")
                move_evaluation["MultiPVLine"] = self._pick(line, "multipv")
                move_evaluation["NodesPerSecond"] = self._pick(line, "nps")
                move_evaluation["SelectiveDepth"] = self._pick(line, "seldepth")

                # add wdl if available
                if self.does_current_engine_version_have_wdl_option():
                    move_evaluation["WDL"] = " ".join(
                        [
                            self._pick(line, "wdl", 1),
                            self._pick(line, "wdl", 2),
                            self._pick(line, "wdl", 3),
                        ][::perspective]
                    )

            # add move to list of top moves
            top_moves.insert(0, move_evaluation)

        # reset MultiPV to global value
        if old_multipv != self._parameters["MultiPV"]:
            self._set_option("MultiPV", old_multipv)

        # reset self._num_nodes to global value
        if old_num_nodes != self._num_nodes:
            self._num_nodes = old_num_nodes

        return top_moves

    def get_perft(self, depth: int) -> tuple[int, dict[str, int]]:
        """Returns perft information of the current position for a given depth.

        Args:
            depth: The search depth given as an integer (1 or higher).

        Returns:
            - The first element of the tuple is the total number of leaf nodes at the specified depth.
            - The second element is a dictionary. Each legal move in the current position are keys,
              and their associated values are the number of leaf nodes (at the specified depth) for that move.

        Example:
            >>> num_nodes, move_possibilities = stockfish.get_perft(3)
        """
        if not isinstance(depth, int) or depth < 1 or isinstance(depth, bool):
            raise TypeError("depth must be an integer higher than 0")

        self._go_perft(depth)

        move_possibilities: dict[str, int] = {}
        num_nodes = 0

        while True:
            line = self._read_line()
            if line == "":
                continue
            if "searched" in line:
                num_nodes = int(line.split(":")[1])
                break
            move, num = line.split(":")
            assert move not in move_possibilities
            move_possibilities[move] = int(num)
        self._read_line()  # Consumes the remaining newline stockfish outputs.

        return num_nodes, move_possibilities

    def flip(self) -> None:
        """Flip the side to move"""
        self._put("flip")

    def _pick(self, line: list[str], value: str = "", index: int = 1) -> str:
        return line[line.index(value) + index]

    def get_what_is_on_square(self, square: str) -> Piece | None:
        """Returns what is on the specified square.

        Args:
            square:
                The coordinate of the square in question (e.g., "e4").

        Returns:
            One of the 12 members of the `Piece` enum, or `None` if the square is empty.

        Example:
            >>> piece = stockfish.get_what_is_on_square("e2")
        """

        file_letter: str = square[0].lower()
        rank_num: int = int(square[1])
        if (
            len(square) != 2
            or file_letter < "a"
            or file_letter > "h"
            or square[1] < "1"
            or square[1] > "8"
        ):
            raise ValueError(
                "square argument to the get_what_is_on_square function isn't valid."
            )
        rank_visual: str = self.get_board_visual().splitlines()[17 - 2 * rank_num]
        piece_as_char: str = rank_visual[2 + (ord(file_letter) - ord("a")) * 4]
        return None if piece_as_char == " " else Stockfish.Piece(piece_as_char)

    def will_move_be_a_capture(self, move_value: str) -> Capture:
        """Returns whether the proposed move will be a direct capture,
        en passant, or not a capture at all.

        Args:
            move_value:
                The proposed move, in the notation that Stockfish uses.
                E.g., "e2e4", "g1f3", etc.

        Returns:
            One of the members of the `Stockfish.Capture` enum.
            - `Stockfish.Capture.DIRECT_CAPTURE` if the move will be a direct capture.
            - `Stockfish.Capture.EN_PASSANT` if the move is a capture done with en passant.
            - `Stockfish.Capture.NO_CAPTURE` if the move does not capture anything.

        Example:
            >>> capture = stockfish.will_move_be_a_capture("e2e4")
        """
        if not self.is_move_correct(move_value):
            raise ValueError("The proposed move is not valid in the current position.")
        starting_square_piece: Stockfish.Piece | None = self.get_what_is_on_square(
            move_value[:2]
        )
        ending_square_piece: Stockfish.Piece | None = self.get_what_is_on_square(
            move_value[2:4]
        )
        if ending_square_piece is not None:
            if not self._parameters["UCI_Chess960"]:
                return Stockfish.Capture.DIRECT_CAPTURE
            else:
                # Check for Chess960 castling:
                castling_pieces = [
                    [Stockfish.Piece.WHITE_KING, Stockfish.Piece.WHITE_ROOK],
                    [Stockfish.Piece.BLACK_KING, Stockfish.Piece.BLACK_ROOK],
                ]
                if [starting_square_piece, ending_square_piece] in castling_pieces:
                    return Stockfish.Capture.NO_CAPTURE
                else:
                    return Stockfish.Capture.DIRECT_CAPTURE
        elif move_value[2:4] == self.get_fen_position().split()[
            3
        ] and starting_square_piece in [
            Stockfish.Piece.WHITE_PAWN,
            Stockfish.Piece.BLACK_PAWN,
        ]:
            return Stockfish.Capture.EN_PASSANT
        else:
            return Stockfish.Capture.NO_CAPTURE

    def get_stockfish_full_version(self) -> float:
        """Returns the full version of the Stockfish engine being used."""
        return self._version["full"]

    def get_stockfish_major_version(self) -> int:
        """Returns the major version of the Stockfish engine being used."""
        return self._version["major"]

    def get_stockfish_minor_version(self) -> int:
        """Returns the minor version of the Stockfish engine being used."""
        return self._version["minor"]

    def get_stockfish_patch_version(self) -> str:
        """Returns the patch version of the Stockfish engine being used."""
        return self._version["patch"]

    def get_stockfish_sha_version(self) -> str:
        """Returns the build version of the Stockfish engine being used."""
        return self._version["sha"]

    def is_development_build_of_engine(self) -> bool:
        """Returns whether the version of Stockfish being used is a development build."""
        return self._version["is_dev_build"]

    def _set_stockfish_version(self) -> None:
        self._put("uci")
        # read version text:
        while True:
            line = self._read_line()
            if line.startswith("id name"):
                self._discard_remaining_stdout_lines("uciok")
                self._parse_stockfish_version(line.split(" ")[3])
                return

    def _parse_stockfish_version(self, version_text: str = "") -> None:
        try:
            self._version: dict["str", Any] = {
                "full": 0,
                "major": 0,
                "minor": 0,
                "patch": "",
                "sha": "",
                "is_dev_build": False,
                "text": version_text,
            }

            # check if version is a development build, eg. dev-20221219-61ea1534
            if self._version["text"].startswith("dev-"):
                self._version["is_dev_build"] = True

                # parse patch and sha from dev version text
                self._version["patch"] = self._version["text"].split("-")[1]
                self._version["sha"] = self._version["text"].split("-")[2]

                # get major.minor version as text from build date
                build_date = self._version["text"].split("-")[1]
                date_string = f"{int(build_date[:4])}-{int(build_date[4:6]):02d}-{int(build_date[6:8]):02d}"
                self._version["text"] = self._get_stockfish_version_from_build_date(
                    date_string
                )

            # check if version is a development build, eg. 280322
            if len(self._version["text"]) == 6:
                self._version["is_dev_build"] = True

                # parse version number from DDMMYY
                self._version["patch"] = self._version["text"]

                # parse build date from dev version text
                build_date = self._version["text"]
                date_string = f"20{build_date[4:6]}-{build_date[2:4]}-{build_date[0:2]}"
                self._version["text"] = self._get_stockfish_version_from_build_date(
                    date_string
                )

            # parse version number for all versions
            self._version["major"] = int(self._version["text"].split(".")[0])
            try:
                self._version["minor"] = int(self._version["text"].split(".")[1])
            except IndexError:
                self._version["minor"] = 0
            self._version["full"] = self._version["major"] + self._version["minor"] / 10
        except Exception as e:
            raise Exception(
                "Unable to parse Stockfish version. You may be using an unsupported version of Stockfish."
            )

    def _get_stockfish_version_from_build_date(
        self, date_string: str = ""
    ) -> str | None:
        # Convert date string to datetime object
        date_object = datetime.datetime.strptime(date_string, "%Y-%m-%d")

        # Convert release date strings to datetime objects
        releases_datetime = {
            key: datetime.datetime.strptime(value, "%Y-%m-%d")
            for key, value in self._RELEASES.items()
        }

        # Find the key for the given date
        key_for_date = None
        for key, value in releases_datetime.items():
            if value <= date_object:
                if key_for_date is None or value > releases_datetime[key_for_date]:
                    key_for_date = key

        if key_for_date is None:
            raise Exception(
                "There was a problem with finding the release associated with the engine publish date."
            )

        return key_for_date

    def send_quit_command(self) -> None:
        """Sends the `quit` command to the Stockfish engine, getting the process to stop."""

        if self._stockfish.poll() is None:
            self._put("quit")
            while self._stockfish.poll() is None:
                pass

    def __del__(self) -> None:
        Stockfish._del_counter += 1
        self.send_quit_command()

    class Piece(Enum):
        WHITE_PAWN = "P"
        BLACK_PAWN = "p"
        WHITE_KNIGHT = "N"
        BLACK_KNIGHT = "n"
        WHITE_BISHOP = "B"
        BLACK_BISHOP = "b"
        WHITE_ROOK = "R"
        BLACK_ROOK = "r"
        WHITE_QUEEN = "Q"
        BLACK_QUEEN = "q"
        WHITE_KING = "K"
        BLACK_KING = "k"

    class Capture(Enum):
        DIRECT_CAPTURE = "direct capture"
        EN_PASSANT = "en passant"
        NO_CAPTURE = "no capture"

    @dataclass
    class BenchmarkParameters:
        ttSize: int = 16
        threads: int = 1
        limit: int = 13
        fenFile: str = "default"
        limitType: str = "depth"
        evalType: str = "mixed"

        def __post_init__(self):
            self.ttSize = self.ttSize if self.ttSize in range(1, 128001) else 16
            self.threads = self.threads if self.threads in range(1, 513) else 1
            self.limit = self.limit if self.limit in range(1, 10001) else 13
            self.fenFile = (
                self.fenFile
                if self.fenFile.endswith(".fen") and os.path.isfile(self.fenFile)
                else "default"
            )
            self.limitType = (
                self.limitType
                if self.limitType in ["depth", "perft", "nodes", "movetime"]
                else "depth"
            )
            self.evalType = (
                self.evalType
                if self.evalType in ["mixed", "classical", "NNUE"]
                else "mixed"
            )

    def benchmark(self, params: BenchmarkParameters) -> str:
        """This function will run the `bench` command with BenchmarkParameters.
        It is an additional custom non-UCI command, mainly for debugging.
        Do not use this command during a search!

        Args:
            params:
                An instance of the `Stockfish.BenchmarkParameters` class, that specifies
                the parameters with which you want to run the `bench` command.

        Returns:
            The final line of Stockfish's output from running the bench. I.e., the line
            starting with "Nodes/second".
        """
        if type(params) != self.BenchmarkParameters:
            params = self.BenchmarkParameters()

        self._put(
            f"bench {params.ttSize} {params.threads} {params.limit} {params.fenFile} {params.limitType} {params.evalType}"
        )
        while True:
            text = self._read_line()
            if text.split(" ")[0] == "Nodes/second":
                return text


class StockfishException(Exception):
    pass
