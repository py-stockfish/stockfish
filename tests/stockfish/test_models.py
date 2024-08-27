import pytest
from timeit import default_timer
import time
from typing import List, Optional, Dict, Callable, Type, Any
import platform
import operator

from stockfish import Stockfish, StockfishException


def compare(first, second, op: Callable[[Any, Any], bool], expected_type: Type) -> bool:
    return all(isinstance(x, expected_type) for x in (first, second)) and op(
        first, second
    )


class TestStockfish:
    @pytest.fixture
    def stockfish(self) -> Stockfish:
        return Stockfish()

    # change to `autouse=True` to have the below fixture called before each test function, and then
    # the code after the 'yield' to run after each test.
    @pytest.fixture(autouse=False)
    def autouse_fixture(self, stockfish: Stockfish):
        yield stockfish
        # Some assert statement testing something about the stockfish object here.

    def test_constructor_defaults(self):
        sf = Stockfish()
        assert sf is not None and sf._path == "stockfish"
        assert sf._parameters == sf._DEFAULT_STOCKFISH_PARAMS
        assert sf._depth == 15 and sf._num_nodes == 1000000
        assert sf._turn_perspective is True

    def test_constructor_options(self):
        sf = Stockfish(
            depth=20,
            num_nodes=1000,
            turn_perspective=False,
            parameters={"Threads": 2, "UCI_Elo": 1500},
        )
        assert sf._depth == 20 and sf._num_nodes == 1000
        assert sf._turn_perspective is False
        assert sf._parameters["Threads"] == 2 and sf._parameters["UCI_Elo"] == 1500

    @pytest.mark.parametrize(
        "parameters",
        [{"depth": "20"}, {"num_nodes": "100"}, {"turn_perspective": "False"}],
    )
    def test_constructor_raises_type_errors(self, parameters):
        with pytest.raises(TypeError):
            Stockfish(**parameters)

    def test_get_best_move_first_move(self, stockfish: Stockfish):
        best_move = stockfish.get_best_move()
        assert best_move in ("e2e3", "e2e4", "g1f3", "b1c3", "d2d4")

    def test_get_best_move_time_first_move(self, stockfish: Stockfish):
        best_move = stockfish.get_best_move_time(1000)
        assert best_move in ("e2e3", "e2e4", "g1f3", "b1c3", "d2d4")

    @pytest.mark.slow
    def test_get_best_move_remaining_time_first_move(self, stockfish: Stockfish):
        best_move = stockfish.get_best_move(wtime=1000)
        assert best_move in ("a2a3", "d2d4", "e2e4", "g1f3", "c2c4")
        best_move = stockfish.get_best_move(btime=1000)
        assert best_move in ("g1f3", "d2d4", "e2e4", "c2c4")
        best_move = stockfish.get_best_move(wtime=1000, btime=1000)
        assert best_move in ("g2g3", "g1f3", "e2e4", "d2d4", "c2c4", "e2e3")
        best_move = stockfish.get_best_move(wtime=5 * 60 * 1000, btime=1000)
        assert best_move in ("e2e3", "e2e4", "g1f3", "b1c3", "d2d4")

    def test_make_moves_from_start_resets_info(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6"])
        stockfish.get_best_move()
        assert stockfish.info != ""
        stockfish.make_moves_from_start(["e2e4", "e7e6"])
        assert stockfish.info == ""

    def test_get_best_move_not_first_move(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6"])
        best_move = stockfish.get_best_move()
        assert best_move in ("d2d4", "g1f3")

    def test_get_best_move_time_not_first_move(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6"])
        best_move = stockfish.get_best_move_time(1000)
        assert best_move in ("d2d4", "g1f3")

    @pytest.mark.slow
    def test_get_best_move_remaining_time_not_first_move(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6"])
        best_move = stockfish.get_best_move(wtime=1000)
        assert best_move in ("d2d4", "a2a3", "d1e2", "b1c3")
        best_move = stockfish.get_best_move(btime=1000)
        assert best_move in ("d2d4", "b1c3", "g1f3")
        best_move = stockfish.get_best_move(wtime=1000, btime=1000)
        assert best_move in ("d2d4", "b1c3", "g1f3")
        best_move = stockfish.get_best_move(wtime=5 * 60 * 1000, btime=1000)
        assert best_move in ("e2e3", "e2e4", "g1f3", "b1c3", "d2d4")

    def test_get_best_move_checkmate(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["f2f3", "e7e5", "g2g4", "d8h4"])
        assert stockfish.get_best_move() is None

    def test_get_best_move_time_checkmate(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["f2f3", "e7e5", "g2g4", "d8h4"])
        assert stockfish.get_best_move_time(1000) is None

    def test_get_best_move_remaining_time_checkmate(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["f2f3", "e7e5", "g2g4", "d8h4"])
        assert stockfish.get_best_move(wtime=1000) is None
        assert stockfish.get_best_move(btime=1000) is None
        assert stockfish.get_best_move(wtime=1000, btime=1000) is None
        assert stockfish.get_best_move(wtime=5 * 60 * 1000, btime=1000) is None

    def test_set_fen_position(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "7r/1pr1kppb/2n1p2p/2NpP2P/5PP1/1P6/P6K/R1R2B2 w - - 1 27"
        )
        assert stockfish.is_move_correct("f4f5") is True
        assert stockfish.is_move_correct("a1c1") is False

    def test_castling(self, stockfish: Stockfish):
        assert stockfish.is_move_correct("e1g1") is False
        stockfish.set_fen_position(
            "rnbqkbnr/ppp3pp/3ppp2/8/4P3/5N2/PPPPBPPP/RNBQK2R w KQkq - 0 4"
        )
        assert stockfish.is_move_correct("e1g1") is True

    def test_set_fen_position_mate(self, stockfish: Stockfish):
        stockfish.set_fen_position("8/8/8/6pp/8/4k1PP/8/r3K3 w - - 12 53")
        assert stockfish.get_best_move() is None
        assert stockfish.info == "info depth 0 score mate 0"

    def test_clear_info_after_set_new_fen_position(self, stockfish: Stockfish):
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("8/8/8/6pp/8/4k1PP/r7/4K3 b - - 11 52")
        stockfish.get_best_move()
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("8/8/8/6pp/8/4k1PP/8/r3K3 w - - 12 53")
        assert stockfish.info == ""

        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("8/8/8/6pp/8/4k1PP/r7/4K3 b - - 11 52")
        stockfish.get_best_move()
        stockfish.set_fen_position("8/8/8/6pp/8/4k1PP/8/r3K3 w - - 12 53")
        assert stockfish.info == ""

    def test_set_fen_position_starts_new_game(self, stockfish: Stockfish):
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position(
            "7r/1pr1kppb/2n1p2p/2NpP2P/5PP1/1P6/P6K/R1R2B2 w - - 1 27"
        )
        stockfish.get_best_move()
        assert stockfish.info != ""
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("3kn3/p5rp/1p3p2/3B4/3P1P2/2P5/1P3K2/8 w - - 0 53")
        assert stockfish.info == ""

    def test_set_fen_position_second_argument(self, stockfish: Stockfish):
        stockfish.set_depth(16)
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position(
            "rnbqk2r/pppp1ppp/3bpn2/8/3PP3/2N5/PPP2PPP/R1BQKBNR w KQkq - 0 1"
        )
        assert stockfish.get_best_move() == "e4e5"

        stockfish.set_fen_position(
            "rnbqk2r/pppp1ppp/3bpn2/4P3/3P4/2N5/PPP2PPP/R1BQKBNR b KQkq - 0 1"
        )
        assert stockfish.get_best_move() in ("d6e7", "d6b4")

        stockfish.set_fen_position(
            "rnbqk2r/pppp1ppp/3bpn2/8/3PP3/2N5/PPP2PPP/R1BQKBNR w KQkq - 0 1"
        )
        assert stockfish.get_best_move() == "e4e5"

    def test_is_move_correct_first_move(self, stockfish: Stockfish):
        assert stockfish.is_move_correct("e2e1") is False
        assert stockfish.is_move_correct("a2a3") is True

    def test_is_move_correct_not_first_move(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6"])
        assert stockfish.is_move_correct("e2e1") is False
        assert stockfish.is_move_correct("a2a3") is True

    # fmt: off
    @pytest.mark.parametrize(
        "value",
        [
            "info", "depth", "seldepth", "multipv", "score", "mate", "-1", "nodes",
            "nps", "tbhits", "time", "pv", "h2g1", "h4g3"
        ]
    )
    # fmt: on
    def test_last_info(self, stockfish: Stockfish, value):
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("r6k/6b1/2b1Q3/p6p/1p5q/3P2PP/5r1K/8 w - - 1 31")
        stockfish.get_best_move()
        assert value in stockfish.info

    def test_set_skill_level(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "rnbqkbnr/ppp2ppp/3pp3/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1"
        )

        assert stockfish.get_engine_parameters()["Skill Level"] == 20

        stockfish.set_skill_level(1)
        # fmt: off
        assert stockfish.get_best_move() in (
            "b2b3", "d2d3", "d2d4", "b1c3", "d1e2", "g2g3", "c2c4", "f1e2", "c2c3", "h2h3"
        )
        # fmt: on
        assert stockfish.get_engine_parameters()["Skill Level"] == 1
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is False
        assert stockfish._on_weaker_setting()

        stockfish.set_skill_level(20)
        assert stockfish.get_best_move() in ("d2d4", "c2c4")
        assert stockfish.get_engine_parameters()["Skill Level"] == 20
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is False
        assert not stockfish._on_weaker_setting()

    def test_set_elo_rating(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "rnbqkbnr/ppp2ppp/3pp3/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 1"
        )

        assert stockfish.get_engine_parameters()["UCI_Elo"] == 1350
        assert not stockfish._on_weaker_setting()

        stockfish.set_elo_rating(2000)
        # fmt: off
        assert stockfish.get_best_move() in (
            "d2d4", "b1c3", "d1e2", "c2c4", "f1e2", "h2h3", "c2c3", "f1d3", "a2a3", "a2a4"
        )
        # fmt: on
        assert stockfish.get_engine_parameters()["UCI_Elo"] == 2000
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is True
        assert stockfish._on_weaker_setting()

        stockfish.set_elo_rating(1350)
        # fmt: off
        assert stockfish.get_best_move() in (
            "d1e2", "b1c3", "d2d3", "d2d4", "c2c4", "f1e2", "c2c3", "f1b5", "g2g3", "h2h3"
        )
        # fmt: on
        assert stockfish.get_engine_parameters()["UCI_Elo"] == 1350
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is True
        assert stockfish._on_weaker_setting()

        stockfish.set_elo_rating(2850)
        major_version = stockfish.get_stockfish_major_version()

        expected_best_moves = ["d2d4", "b1c3", "c2c3", "c2c4", "f1b5", "f1e2"]
        if major_version >= 12 and not stockfish.is_development_build_of_engine():
            expected_best_moves.remove("f1e2")

        assert stockfish.get_best_move() in expected_best_moves

        assert stockfish.get_engine_parameters()["UCI_Elo"] == 2850
        assert stockfish._on_weaker_setting()

    @pytest.mark.slow
    def test_resume_full_strength(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "1r1qrbk1/2pb1pp1/p4n1p/P3P3/3P4/NB4BP/6P1/R2QR1K1 b - - 0 1"
        )
        stockfish.set_depth(13)
        stockfish.set_elo_rating(1350)
        assert stockfish._on_weaker_setting()
        best_moves = ["d7c6", "d7f5"]
        low_elo_moves = [stockfish.get_best_move() for _ in range(15)]
        assert not all(x in best_moves for x in low_elo_moves)
        stockfish.set_skill_level(1)
        assert stockfish._on_weaker_setting()
        low_skill_level_moves = [stockfish.get_best_move() for _ in range(15)]
        assert not all(x in best_moves for x in low_skill_level_moves)
        stockfish.resume_full_strength()
        assert not stockfish._on_weaker_setting()
        full_strength_moves = [stockfish.get_best_move() for _ in range(15)]
        assert all(x in best_moves for x in full_strength_moves)

    def test_specific_params(self, stockfish: Stockfish):
        # fmt: off
        old_parameters = {
            "Debug Log File": "", "Contempt": 0, "Min Split Depth": 0, "Threads": 1,
            "Ponder": False, "Hash": 16, "MultiPV": 1, "Skill Level": 20,
            "Move Overhead": 10, "Minimum Thinking Time": 20, "Slow Mover": 100,
            "UCI_Chess960": False, "UCI_LimitStrength": False, "UCI_Elo": 1350
        }
        # fmt: on
        expected_parameters = old_parameters.copy()
        stockfish.set_skill_level(1)
        expected_parameters["Skill Level"] = 1
        assert stockfish.get_engine_parameters() == expected_parameters
        assert stockfish._DEFAULT_STOCKFISH_PARAMS == old_parameters
        stockfish.set_skill_level(20)
        expected_parameters["Skill Level"] = 20
        assert stockfish.get_engine_parameters() == old_parameters
        assert stockfish._DEFAULT_STOCKFISH_PARAMS == old_parameters

        stockfish.update_engine_parameters({"Threads": 4})
        expected_parameters["Threads"] = 4
        assert stockfish.get_engine_parameters() == expected_parameters
        stockfish.update_engine_parameters({"Hash": 128})
        expected_parameters["Hash"] = 128
        assert stockfish.get_engine_parameters() == expected_parameters
        stockfish.update_engine_parameters({"Hash": 256, "Threads": 3})
        expected_parameters.update({"Hash": 256, "Threads": 3})
        assert stockfish.get_engine_parameters() == expected_parameters

    def test_update_engine_parameters_wrong_vals(self, stockfish: Stockfish):
        assert set(stockfish.get_engine_parameters().keys()) <= set(
            Stockfish._PARAM_RESTRICTIONS.keys()
        )
        max_hash = 2 ** (25 if "64" in platform.machine() else 11)
        bad_values: Dict[str, List] = {
            "Threads": ["1", False, 0, -1, 1025, 1.0],
            "UCI_Chess960": ["true", "false", "True", 1],
            "Contempt": [-101, 101, "0", False],
            "UCI_LimitStrength": ["true", "false", "False", 1, 0],
            "Ponder": ["true", "false", "True", "False", 0],
            "Hash": [-1, max_hash * 2, max_hash + 1, -2048, True, 0],
            "Not key": [0],
        }
        for name in bad_values:
            for val in bad_values[name]:
                with pytest.raises(ValueError):
                    stockfish.update_engine_parameters({name: val})
                with pytest.raises(ValueError):
                    stockfish._set_option(name, val)

    def test_deprecated_get_parameters(self, stockfish: Stockfish):
        with pytest.raises(ValueError):
            stockfish.get_parameters()

    def test_chess960_position(self, stockfish: Stockfish):
        assert "KQkq" in stockfish.get_fen_position()
        old_parameters = stockfish.get_engine_parameters()
        expected_parameters = stockfish.get_engine_parameters()
        expected_parameters["UCI_Chess960"] = True
        stockfish.update_engine_parameters({"UCI_Chess960": True})
        assert "HAha" in stockfish.get_fen_position()
        assert stockfish.get_engine_parameters() == expected_parameters
        stockfish.set_fen_position("4rkr1/4p1p1/8/8/8/8/8/4nK1R w K - 0 100")
        assert stockfish.get_best_move() == "f1h1"
        stockfish.set_turn_perspective(False)
        assert stockfish.get_evaluation() == {"type": "mate", "value": 2}
        stockfish.set_turn_perspective()
        assert stockfish.get_evaluation() == {"type": "mate", "value": 2}
        assert stockfish.will_move_be_a_capture("f1h1") is Stockfish.Capture.NO_CAPTURE
        assert (
            stockfish.will_move_be_a_capture("f1e1") is Stockfish.Capture.DIRECT_CAPTURE
        )
        stockfish.update_engine_parameters({"UCI_Chess960": False})
        assert stockfish.get_engine_parameters() == old_parameters
        assert stockfish.get_best_move() == "f1g1"
        stockfish.set_turn_perspective(False)
        assert stockfish.get_evaluation() == {"type": "mate", "value": 2}
        stockfish.set_turn_perspective()
        assert stockfish.get_evaluation() == {"type": "mate", "value": 2}
        assert stockfish.will_move_be_a_capture("f1g1") is Stockfish.Capture.NO_CAPTURE

    def test_get_board_visual_white(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6", "d2d4", "d7d5"])
        if stockfish.get_stockfish_major_version() >= 12:
            expected_result = (
                "+---+---+---+---+---+---+---+---+\n"
                "| r | n | b | q | k | b | n | r | 8\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| p | p | p |   |   | p | p | p | 7\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   | p |   |   |   | 6\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | p |   |   |   |   | 5\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | P | P |   |   |   | 4\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   |   |   |   |   | 3\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| P | P | P |   |   | P | P | P | 2\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| R | N | B | Q | K | B | N | R | 1\n"
                "+---+---+---+---+---+---+---+---+\n"
                "  a   b   c   d   e   f   g   h\n"
            )
        else:
            expected_result = (
                "+---+---+---+---+---+---+---+---+\n"
                "| r | n | b | q | k | b | n | r |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| p | p | p |   |   | p | p | p |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   | p |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | p |   |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | P | P |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   |   |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| P | P | P |   |   | P | P | P |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| R | N | B | Q | K | B | N | R |\n"
                "+---+---+---+---+---+---+---+---+\n"
            )

        assert stockfish.get_board_visual() == expected_result

        stockfish._put("d")
        stockfish._read_line()  # skip a line
        assert "+---+---+---+" in stockfish._read_line()
        # Tests that the previous call to get_board_visual left no remaining lines to be read. This means
        # the second line read after stockfish._put("d") now will be the +---+---+---+ of the new outputted board.

    def test_get_board_visual_black(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6", "d2d4", "d7d5"])
        if stockfish.get_stockfish_major_version() >= 12:
            expected_result = (
                "+---+---+---+---+---+---+---+---+\n"
                "| R | N | B | K | Q | B | N | R | 1\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| P | P | P |   |   | P | P | P | 2\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   |   |   |   |   | 3\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | P | P |   |   |   | 4\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   | p |   |   |   | 5\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | p |   |   |   |   | 6\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| p | p | p |   |   | p | p | p | 7\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| r | n | b | k | q | b | n | r | 8\n"
                "+---+---+---+---+---+---+---+---+\n"
                "  h   g   f   e   d   c   b   a\n"
            )
        else:
            expected_result = (
                "+---+---+---+---+---+---+---+---+\n"
                "| R | N | B | K | Q | B | N | R |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| P | P | P |   |   | P | P | P |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   |   |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | P | P |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   |   | p |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "|   |   |   | p |   |   |   |   |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| p | p | p |   |   | p | p | p |\n"
                "+---+---+---+---+---+---+---+---+\n"
                "| r | n | b | k | q | b | n | r |\n"
                "+---+---+---+---+---+---+---+---+\n"
            )

        assert stockfish.get_board_visual(False) == expected_result

        stockfish._put("d")
        stockfish._read_line()  # skip a line
        assert "+---+---+---+" in stockfish._read_line()
        # Tests that the previous call to get_board_visual left no remaining lines to be read. This means
        # the second line read after stockfish._put("d") now will be the +---+---+---+ of the new outputted board.

    def test_get_fen_position(self, stockfish: Stockfish):
        assert (
            stockfish.get_fen_position()
            == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        stockfish._put("d")
        stockfish._read_line()  # skip a line
        assert "+---+---+---+" in stockfish._read_line()

    def test_get_fen_position_after_some_moves(self, stockfish: Stockfish):
        stockfish.make_moves_from_start(["e2e4", "e7e6"])
        assert (
            stockfish.get_fen_position()
            == "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        )

    @pytest.mark.slow
    def test_get_evaluation_cp(self, stockfish: Stockfish):
        stockfish.set_depth(20)
        stockfish.set_fen_position(
            "r4rk1/pppb1p1p/2nbpqp1/8/3P4/3QBN2/PPP1BPPP/R4RK1 w - - 0 11"
        )
        evaluation = stockfish.get_evaluation()
        assert (
            compare(evaluation["type"], "cp", operator.eq, str)
            and compare(evaluation["value"], 60, operator.ge, int)
            and compare(evaluation["value"], 150, operator.le, int)
        )
        stockfish.set_skill_level(1)
        with pytest.warns(UserWarning):
            evaluation = stockfish.get_evaluation()
        assert (
            compare(evaluation["type"], "cp", operator.eq, str)
            and compare(evaluation["value"], 60, operator.ge, int)
            and compare(evaluation["value"], 150, operator.le, int)
        )

    @pytest.mark.slow
    def test_get_evaluation_time(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "r4rk1/pppb1p1p/2nbpqp1/8/3P4/3QBN2/PPP1BPPP/R4RK1 w - - 0 11"
        )
        start = time.time()
        evaluation = stockfish.get_evaluation(searchtime=5000)

        assert round(time.time() - start) == 5
        assert evaluation["type"] == "cp"
        assert 30 < evaluation["value"] < 120  # type: ignore

    def test_get_evaluation_checkmate(self, stockfish: Stockfish):
        stockfish.set_fen_position("1nb1k1n1/pppppppp/8/6r1/5bqK/6r1/8/8 w - - 2 2")
        assert stockfish.get_evaluation() == {"type": "mate", "value": 0}

    def test_get_evaluation_stalemate(self, stockfish: Stockfish):
        stockfish.set_fen_position("1nb1kqn1/pppppppp/8/6r1/5b1K/6r1/8/8 w - - 2 2")
        assert stockfish.get_evaluation() == {"type": "cp", "value": 0}
        stockfish.set_turn_perspective(not stockfish.get_turn_perspective())
        assert stockfish.get_evaluation() == {"type": "cp", "value": 0}

    def test_get_static_eval(self, stockfish: Stockfish):
        stockfish.set_turn_perspective(False)
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("r7/8/8/8/8/5k2/4p3/4K3 w - - 0 1")
        assert compare(stockfish.get_static_eval(), -3.0, operator.lt, float)
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("r7/8/8/8/8/5k2/4p3/4K3 b - - 0 1")
        assert compare(stockfish.get_static_eval(), -3.0, operator.lt, float)
        stockfish.set_turn_perspective()
        assert compare(stockfish.get_static_eval(), 3.0, operator.gt, float)
        stockfish.send_ucinewgame_command()
        stockfish.set_fen_position("r7/8/8/8/8/5k2/4p3/4K3 w - - 0 1")
        assert compare(stockfish.get_static_eval(), -3.0, operator.lt, float)
        if stockfish.get_stockfish_major_version() >= 12:
            stockfish.send_ucinewgame_command()
            stockfish.set_fen_position("8/8/8/8/8/4k3/4p3/r3K3 w - - 0 1")
            assert stockfish.get_static_eval() is None
        stockfish.send_ucinewgame_command()
        stockfish.make_moves_from_start(None)
        stockfish.get_static_eval()
        stockfish._put("go depth 2")
        assert stockfish._read_line() != ""

    def test_set_depth(self, stockfish: Stockfish):
        stockfish.set_depth(12)
        assert stockfish._depth == 12
        stockfish.get_best_move()
        assert "depth 12" in stockfish.info
        stockfish.set_depth()
        assert stockfish._depth == 15
        stockfish.get_best_move()
        assert "depth 15" in stockfish.info

    @pytest.mark.parametrize("depth", ["12", True, 12.1, 0, None])
    def test_set_depth_raises_type_error(self, stockfish: Stockfish, depth):
        with pytest.raises(TypeError):
            stockfish.set_depth(depth)

    def test_get_depth(self, stockfish: Stockfish):
        stockfish.set_depth(12)
        assert stockfish.get_depth() == 12
        assert stockfish._depth == 12
        stockfish.set_depth(20)
        assert stockfish.get_depth() == 20
        assert stockfish._depth == 20

    def test_set_num_nodes(self, stockfish: Stockfish):
        stockfish.set_num_nodes(100)
        assert stockfish._num_nodes == 100
        stockfish.set_num_nodes()
        assert stockfish._num_nodes == 1000000

    @pytest.mark.parametrize("num_nodes", ["100", 100.1, None, True])
    def test_set_num_nodes_raises_type_error(self, stockfish: Stockfish, num_nodes):
        with pytest.raises(TypeError):
            stockfish.set_num_nodes(num_nodes)

    def test_get_num_nodes(self, stockfish: Stockfish):
        stockfish.set_num_nodes(100)
        assert stockfish.get_num_nodes() == 100
        stockfish.set_num_nodes()
        assert stockfish.get_num_nodes() == 1000000

    def test_get_best_move_wrong_position(self, stockfish: Stockfish):
        stockfish.set_depth(2)
        wrong_fen = "3kk3/8/8/8/8/8/8/3KK3 w - - 0 0"
        stockfish.set_fen_position(wrong_fen)
        assert stockfish.get_best_move() in ("d1e2", "d1c1", "d1c2")

    def test_constructor(self, stockfish: Stockfish):
        # Will also use a new stockfish instance in order to test sending
        # params to the constructor.

        stockfish_2 = Stockfish(
            depth=16, parameters={"MultiPV": 2, "UCI_Elo": 2850, "UCI_Chess960": True}
        )
        assert (
            stockfish_2.get_fen_position()
            == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w HAha - 0 1"
        )
        assert (
            stockfish.get_fen_position()
            == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )

        stockfish_2.get_best_move()
        stockfish.get_best_move()

        assert "multipv 2" in stockfish_2.info and "depth 16" in stockfish_2.info
        assert "multipv 1" in stockfish.info and "depth 15" in stockfish.info
        assert stockfish_2._depth == 16 and stockfish._depth == 15

        stockfish_1_params = stockfish.get_engine_parameters()
        stockfish_2_params = stockfish_2.get_engine_parameters()
        for key in stockfish_2_params.keys():
            if key == "MultiPV":
                assert stockfish_2_params[key] == 2 and stockfish_1_params[key] == 1
            elif key == "UCI_Elo":
                assert stockfish_2_params[key] == 2850
                assert stockfish_1_params[key] == 1350
            elif key == "UCI_LimitStrength":
                assert stockfish_2_params[key] is True
                assert stockfish_1_params[key] is False
            elif key == "UCI_Chess960":
                assert stockfish_2_params[key] is True
                assert stockfish_1_params[key] is False
            else:
                assert stockfish_2_params[key] == stockfish_1_params[key]

    def test_parameters_functions(self, stockfish: Stockfish):
        old_parameters = stockfish.get_engine_parameters()
        stockfish.set_fen_position("4rkr1/4p1p1/8/8/8/8/8/5K1R w H - 0 100")
        assert stockfish.get_best_move() == "f1g1"  # ensures Chess960 param is false.
        assert stockfish.get_fen_position() == "4rkr1/4p1p1/8/8/8/8/8/5K1R w K - 0 100"
        assert "multipv 1" in stockfish.info
        stockfish.update_engine_parameters(
            {
                "Minimum Thinking Time": 10,
                "Hash": 32,
                "MultiPV": 2,
                "UCI_Chess960": True,
            }
        )
        assert stockfish.get_fen_position() == "4rkr1/4p1p1/8/8/8/8/8/5K1R w H - 0 100"
        assert stockfish.get_best_move() == "f1h1"
        assert "multipv 2" in stockfish.info
        updated_parameters = stockfish.get_engine_parameters()
        for key, value in updated_parameters.items():
            if key == "Minimum Thinking Time":
                assert value == 10
            elif key == "Hash":
                assert value == 32
            elif key == "MultiPV":
                assert value == 2
            elif key == "UCI_Chess960":
                assert value is True
            else:
                assert updated_parameters[key] == old_parameters[key]
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is False
        stockfish.update_engine_parameters({"UCI_Elo": 2000, "Skill Level": 19})
        assert stockfish.get_engine_parameters()["UCI_Elo"] == 2000
        assert stockfish.get_engine_parameters()["Skill Level"] == 19
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is False
        stockfish.update_engine_parameters({"UCI_Elo": 2000})
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is True
        stockfish.update_engine_parameters({"Skill Level": 20})
        assert stockfish.get_engine_parameters()["UCI_LimitStrength"] is False
        assert stockfish.get_fen_position() == "4rkr1/4p1p1/8/8/8/8/8/5K1R w H - 0 100"
        stockfish.reset_engine_parameters()
        assert stockfish.get_engine_parameters() == old_parameters
        assert stockfish.get_fen_position() == "4rkr1/4p1p1/8/8/8/8/8/5K1R w K - 0 100"
        with pytest.raises(ValueError):
            stockfish.update_engine_parameters({"Not an existing key", "value"})  # type: ignore

    def test_get_top_moves(self, stockfish: Stockfish):
        stockfish.set_depth(15)
        stockfish._set_option("MultiPV", 4)
        stockfish.set_fen_position("1rQ1r1k1/5ppp/8/8/1R6/8/2r2PPP/4R1K1 w - - 0 1")
        assert stockfish.get_top_moves(2) == [
            {"Move": "e1e8", "Centipawn": None, "Mate": 1},
            {"Move": "c8e8", "Centipawn": None, "Mate": 2},
        ]
        stockfish.set_fen_position("8/8/8/8/8/3r2k1/8/6K1 w - - 0 1")
        assert stockfish.get_top_moves(2) == [
            {"Move": "g1f1", "Centipawn": None, "Mate": -2},
            {"Move": "g1h1", "Centipawn": None, "Mate": -1},
        ]
        stockfish.set_elo_rating()
        with pytest.warns(UserWarning):
            top_moves = stockfish.get_top_moves(2)
        assert top_moves == [
            {"Move": "g1f1", "Centipawn": None, "Mate": -2},
            {"Move": "g1h1", "Centipawn": None, "Mate": -1},
        ]

    def test_get_top_moves_mate(self, stockfish: Stockfish):
        stockfish.set_depth(10)
        stockfish._set_option("MultiPV", 3)
        stockfish.set_fen_position("8/8/8/8/8/6k1/8/3r2K1 w - - 0 1")
        assert stockfish.get_top_moves() == []
        assert stockfish.get_engine_parameters()["MultiPV"] == 3

    def test_get_top_moves_verbose(self, stockfish: Stockfish):
        stockfish.set_depth(15)
        stockfish.set_fen_position("1rQ1r1k1/5ppp/8/8/1R6/8/2r2PPP/4R1K1 w - - 0 1")
        assert stockfish.get_top_moves(2, verbose=False) == [
            {"Move": "e1e8", "Centipawn": None, "Mate": 1},
            {"Move": "c8e8", "Centipawn": None, "Mate": 2},
        ]
        moves = stockfish.get_top_moves(2, verbose=True)
        assert all(
            k in moves[0]
            for k in (
                "Move",
                "Centipawn",
                "Mate",
                "MultiPVLine",
                "NodesPerSecond",
                "Nodes",
                "SelectiveDepth",
                "Time",
            )
        )
        if stockfish.does_current_engine_version_have_wdl_option():
            assert "WDL" in moves[0]

    def test_get_top_moves_num_nodes(self, stockfish: Stockfish):
        stockfish.set_fen_position("8/2q2pk1/4b3/1p6/7P/Q1p3P1/2B2P2/6K1 b - - 3 50")
        moves = stockfish.get_top_moves(2, num_nodes=1000000, verbose=True)
        assert int(moves[0]["Nodes"]) >= 1000000

    def test_get_top_moves_preserve_globals(self, stockfish: Stockfish):
        stockfish._set_option("MultiPV", 4)
        stockfish.set_num_nodes(2000000)
        stockfish.set_fen_position("1rQ1r1k1/5ppp/8/8/1R6/8/2r2PPP/4R1K1 w - - 0 1")
        stockfish.get_top_moves(2, num_nodes=100000)
        assert stockfish.get_num_nodes() == 2000000
        assert stockfish.get_engine_parameters()["MultiPV"] == 4

    def test_get_top_moves_raises_value_error(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        )
        with pytest.raises(ValueError):
            stockfish.get_top_moves(0)
        assert len(stockfish.get_top_moves(2)) == 2
        assert stockfish.get_engine_parameters()["MultiPV"] == 1

    @pytest.mark.parametrize(
        "depth, expected_num_nodes", [(1, 20), (2, 400), (3, 8902), (6, 119060324)]
    )
    def test_get_perft_number_nodes(
        self, stockfish: Stockfish, depth: int, expected_num_nodes: int
    ):
        num_nodes, move_possibilities = stockfish.get_perft(depth)
        assert num_nodes == expected_num_nodes
        assert sum(move_possibilities.values()) == expected_num_nodes

    def test_get_perft(self, stockfish: Stockfish):
        move_possibilities = stockfish.get_perft(1)[1]
        assert len(move_possibilities) == 20
        assert all(k in move_possibilities.keys() for k in ("a2a3", "g1h3"))
        assert set(move_possibilities.values()) == {1}

        move_possibilities2 = stockfish.get_perft(3)[1]
        assert move_possibilities.keys() == move_possibilities2.keys()
        assert min(move_possibilities2.values()) == 380
        assert max(move_possibilities2.values()) == 600
        assert move_possibilities2["f2f3"] == 380 and move_possibilities2["e2e3"] == 599

    @pytest.mark.parametrize("depth", [True, 0, "foo", 16.2])
    def test_get_perft_raises_type_error(self, stockfish: Stockfish, depth):
        with pytest.raises(TypeError):
            stockfish.get_perft(depth)

    def test_get_perft_different_position(self, stockfish: Stockfish):
        stockfish.set_fen_position("1k6/7Q/1K6/8/8/8/8/8 w - - 0 1")
        num_nodes, move_possibilities = stockfish.get_perft(3)
        assert num_nodes == 1043
        assert move_possibilities["h7g8"] == 0
        assert move_possibilities["h7b1"] == 48

    def test_flip(self, stockfish: Stockfish):
        stockfish.flip()
        assert (
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR b KQkq - 0 1"
            == stockfish.get_fen_position()
        )
        stockfish.set_fen_position("8/4q1k1/8/8/8/8/2K5/8 w - - 0 1")
        stockfish.flip()
        assert "b" in stockfish.get_fen_position()
        stockfish.flip()
        assert "w" in stockfish.get_fen_position()
        stockfish.make_moves_from_current_position(["c2c3"])
        stockfish.flip()
        assert "w" in stockfish.get_fen_position()

    def test_turn_perspective(self, stockfish: Stockfish):
        stockfish.set_depth(15)
        stockfish.set_fen_position("8/2q2pk1/4b3/1p6/7P/Q1p3P1/2B2P2/6K1 b - - 3 50")
        assert stockfish.get_turn_perspective()
        moves = stockfish.get_top_moves(1)
        assert moves[0]["Centipawn"] > 0
        assert compare(stockfish.get_evaluation()["value"], 0, operator.gt, int)
        stockfish.set_turn_perspective(False)
        assert stockfish.get_turn_perspective() is False
        moves = stockfish.get_top_moves(1)
        assert moves[0]["Centipawn"] < 0
        assert compare(stockfish.get_evaluation()["value"], 0, operator.lt, int)

    def test_turn_perspective_raises_type_error(self, stockfish: Stockfish):
        with pytest.raises(TypeError):
            stockfish.set_turn_perspective("not a bool")  # type: ignore

    def test_make_moves_from_current_position(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 0 1"
        )
        fen_1 = stockfish.get_fen_position()
        stockfish.make_moves_from_current_position([])
        assert fen_1 == stockfish.get_fen_position()

        stockfish.make_moves_from_current_position(["e1g1"])
        assert (
            stockfish.get_fen_position()
            == "r1bqkb1r/pppp1ppp/2n2n2/1B2p3/4P3/5N2/PPPP1PPP/RNBQ1RK1 b kq - 1 1"
        )

        stockfish.make_moves_from_current_position(
            ["f6e4", "d2d4", "e4d6", "b5c6", "d7c6", "d4e5", "d6f5"]
        )
        assert (
            stockfish.get_fen_position()
            == "r1bqkb1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNBQ1RK1 w kq - 1 5"
        )

        stockfish.make_moves_from_current_position(
            ["d1d8", "e8d8", "b1c3", "d8e8", "f1d1", "f5e7", "h2h3", "f7f5"]
        )
        assert (
            stockfish.get_fen_position()
            == "r1b1kb1r/ppp1n1pp/2p5/4Pp2/8/2N2N1P/PPP2PP1/R1BR2K1 w - f6 0 9"
        )

        stockfish.set_fen_position(
            "r1bqk2r/pppp1ppp/8/8/1b2n3/2N5/PPP2PPP/R1BQK2R w Qkq - 0 1"
        )

        invalid_moves = ["d1e3", "e1g1", "c3d5", "c1d4", "a7a6", "e1d2", "word"]

        current_fen = stockfish.get_fen_position()
        stockfish.make_moves_from_current_position(invalid_moves)
        assert current_fen == stockfish.get_fen_position()
        for invalid_move in invalid_moves:
            stockfish.make_moves_from_current_position([invalid_move])
            assert current_fen == stockfish.get_fen_position()

    @pytest.mark.slow
    def test_not_resetting_hash_table_speed(self, stockfish: Stockfish):
        """Tests that not resetting the hash table between related positions makes SF faster."""

        stockfish.set_depth(16)
        positions_considered = []
        stockfish.set_fen_position(
            "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 0 2"
        )

        total_time_calculating_first = 0.0
        for i in range(5):
            start = default_timer()
            chosen_move = stockfish.get_best_move()
            assert isinstance(chosen_move, str)
            total_time_calculating_first += default_timer() - start
            positions_considered.append(stockfish.get_fen_position())
            stockfish.make_moves_from_current_position([chosen_move])

        total_time_calculating_second = 0.0
        for i in range(len(positions_considered)):
            stockfish.send_ucinewgame_command()
            stockfish.set_fen_position(positions_considered[i])
            start = default_timer()
            stockfish.get_best_move()
            total_time_calculating_second += default_timer() - start

        assert total_time_calculating_first < total_time_calculating_second

    def test_get_wdl_stats(self, stockfish: Stockfish):
        stockfish.set_depth(15)
        stockfish._set_option("MultiPV", 2)
        if stockfish.does_current_engine_version_have_wdl_option():
            stockfish.get_wdl_stats()  # Testing that this doesn't raise a RuntimeError.
            stockfish.set_fen_position("7k/4R3/4P1pp/7N/8/8/1q5q/3K4 w - - 0 1")
            wdl_stats = stockfish.get_wdl_stats()
            assert isinstance(wdl_stats, list)
            assert wdl_stats[1] > wdl_stats[0] * 7
            assert abs(wdl_stats[0] - wdl_stats[2]) / wdl_stats[0] < 0.15

            stockfish.send_ucinewgame_command()
            stockfish.set_fen_position(
                "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            )
            wdl_stats_2 = stockfish.get_wdl_stats()
            assert isinstance(wdl_stats_2, list)
            assert wdl_stats_2[1] > wdl_stats_2[0] * 3.5
            assert wdl_stats_2[0] > wdl_stats_2[2] * 1.8

            stockfish.set_fen_position("8/8/8/8/8/6k1/6p1/6K1 w - - 0 1")
            assert stockfish.get_wdl_stats() is None

            stockfish.send_ucinewgame_command()
            stockfish.set_fen_position(
                "rnbqkb1r/pp3ppp/3p1n2/1B2p3/3NP3/2N5/PPP2PPP/R1BQK2R b KQkq - 0 6"
            )
            wdl_stats_3 = stockfish.get_wdl_stats()
            assert isinstance(wdl_stats_3, list) and len(wdl_stats_3) == 3

            stockfish.send_ucinewgame_command()
            stockfish._prepare_for_new_position()
            wdl_stats_4 = stockfish.get_wdl_stats(get_as_tuple=True)
            assert isinstance(wdl_stats_4, tuple) and len(wdl_stats_4) == 3
            assert wdl_stats_3 == list(wdl_stats_4)
            assert tuple(wdl_stats_3) == wdl_stats_4

            stockfish.set_fen_position("8/8/8/8/8/3k4/3p4/3K4 w - - 0 1")
            assert stockfish.get_wdl_stats() is None

            stockfish.set_skill_level(1)
            with pytest.warns(UserWarning):
                stockfish.get_wdl_stats()
        else:
            with pytest.raises(RuntimeError):
                stockfish.get_wdl_stats()

    def test_does_current_engine_version_have_wdl_option(self, stockfish: Stockfish):
        if stockfish.get_stockfish_major_version() <= 11:
            assert not stockfish.does_current_engine_version_have_wdl_option()
            with pytest.raises(RuntimeError):
                stockfish.get_wdl_stats()

    @pytest.mark.slow
    def test_benchmark_result_with_defaults(self, stockfish: Stockfish):
        params = stockfish.BenchmarkParameters()
        result = stockfish.benchmark(params)
        # result should contain the last line of a successful method call
        assert result.split(" ")[0] == "Nodes/second"

    @pytest.mark.slow
    def test_benchmark_result_with_valid_options(self, stockfish: Stockfish):
        params = stockfish.BenchmarkParameters(
            ttSize=64, threads=2, limit=1000, limitType="movetime", evalType="classical"
        )
        result = stockfish.benchmark(params)
        # result should contain the last line of a successful method call
        assert result.split(" ")[0] == "Nodes/second"

    @pytest.mark.slow
    def test_benchmark_result_with_invalid_options(self, stockfish: Stockfish):
        params = stockfish.BenchmarkParameters(
            ttSize=2049,
            threads=0,
            limit=0,
            fenFile="./fakefile.fen",
            limitType="fghthtr",
            evalType="",
        )
        result = stockfish.benchmark(params)
        # result should contain the last line of a successful method call
        assert result.split(" ")[0] == "Nodes/second"

    @pytest.mark.slow
    def test_benchmark_result_with_invalid_type(self, stockfish: Stockfish):
        params = {
            "ttSize": 16,
            "threads": 1,
            "limit": 13,
            "fenFile": "./fakefile.fen",
            "limitType": "depth",
            "evalType": "mixed",
        }
        result = stockfish.benchmark(params)  # type: ignore
        # result should contain the last line of a successful method call
        assert result.split(" ")[0] == "Nodes/second"

    def test_multiple_calls_to_del(self, stockfish: Stockfish):
        assert stockfish._stockfish.poll() is None
        assert not stockfish._has_quit_command_been_sent
        stockfish.__del__()
        assert stockfish._stockfish.poll() is not None
        assert stockfish._has_quit_command_been_sent
        stockfish.__del__()
        assert stockfish._stockfish.poll() is not None
        assert stockfish._has_quit_command_been_sent

    def test_multiple_quit_commands(self, stockfish: Stockfish):
        # Test multiple quit commands, and include a call to del too. All of
        # them should run without causing some Exception.
        assert stockfish._stockfish.poll() is None
        assert not stockfish._has_quit_command_been_sent
        stockfish._put("quit")
        assert stockfish._has_quit_command_been_sent
        stockfish._put("quit")
        assert stockfish._has_quit_command_been_sent
        stockfish.__del__()
        assert stockfish._stockfish.poll() is not None
        assert stockfish._has_quit_command_been_sent
        stockfish._put(f"go depth {10}")
        # Should do nothing, and change neither of the values below.
        assert stockfish._stockfish.poll() is not None
        assert stockfish._has_quit_command_been_sent

    def test_what_is_on_square(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "rnbq1rk1/ppp1ppbp/5np1/3pP3/8/BPN5/P1PP1PPP/R2QKBNR w KQ d6 0 6"
        )
        # fmt: off
        squares_and_contents: Dict[str, Optional[Stockfish.Piece]] = {
            "a1": Stockfish.Piece.WHITE_ROOK, "a8": Stockfish.Piece.BLACK_ROOK,
            "g8": Stockfish.Piece.BLACK_KING, "e1": Stockfish.Piece.WHITE_KING,
            "h2": Stockfish.Piece.WHITE_PAWN, "f8": Stockfish.Piece.BLACK_ROOK,
            "d6": None, "h7": Stockfish.Piece.BLACK_PAWN, "c3": Stockfish.Piece.WHITE_KNIGHT,
            "a3": Stockfish.Piece.WHITE_BISHOP, "h8": None, "d1": Stockfish.Piece.WHITE_QUEEN,
            "d4": None, "f6": Stockfish.Piece.BLACK_KNIGHT, "g7": Stockfish.Piece.BLACK_BISHOP,
            "d8": Stockfish.Piece.BLACK_QUEEN,
        }
        # fmt: on
        for notation, piece in squares_and_contents.items():
            assert stockfish.get_what_is_on_square(notation) is piece
        with pytest.raises(ValueError):
            stockfish.get_what_is_on_square("i1")
        with pytest.raises(ValueError):
            stockfish.get_what_is_on_square("b9")

    def test_13_return_values_from_what_is_on_square(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "rnbq1rk1/ppp1ppbp/5np1/3pP3/8/BPN5/P1PP1PPP/R2QKBNR w KQ d6 0 6"
        )
        # fmt: off
        expected_enum_members = [
            "WHITE_PAWN", "BLACK_PAWN", "WHITE_KNIGHT", "BLACK_KNIGHT", "WHITE_BISHOP",
            "BLACK_BISHOP", "WHITE_ROOK", "BLACK_ROOK", "WHITE_QUEEN", "BLACK_QUEEN",
            "WHITE_KING", "BLACK_KING",
        ]
        # fmt: on
        rows = ["a", "b", "c", "d", "e", "f", "g", "h"]
        cols = ["1", "2", "3", "4", "5", "6", "7", "8"]
        for row in rows:
            for col in cols:
                val = stockfish.get_what_is_on_square(row + col)
                assert val is None or val.name in expected_enum_members

    def test_will_move_be_a_capture(self, stockfish: Stockfish):
        stockfish.set_fen_position(
            "1nbq1rk1/Ppp1ppbp/5np1/3pP3/8/BPN5/P1PP1PPP/R2QKBNR w KQ d6 0 6"
        )
        c3d5_result = stockfish.will_move_be_a_capture("c3d5")
        assert (
            c3d5_result is Stockfish.Capture.DIRECT_CAPTURE
            and c3d5_result.name == "DIRECT_CAPTURE"
            and c3d5_result.value == "direct capture"
        )
        e5d6_result = stockfish.will_move_be_a_capture("e5d6")
        assert (
            e5d6_result is Stockfish.Capture.EN_PASSANT
            and e5d6_result.name == "EN_PASSANT"
            and e5d6_result.value == "en passant"
        )
        f1e2_result = stockfish.will_move_be_a_capture("f1e2")
        assert (
            f1e2_result is Stockfish.Capture.NO_CAPTURE
            and f1e2_result.name == "NO_CAPTURE"
            and f1e2_result.value == "no capture"
        )
        e5f6_result = stockfish.will_move_be_a_capture("e5f6")
        assert (
            e5f6_result is Stockfish.Capture.DIRECT_CAPTURE
            and e5f6_result.name == "DIRECT_CAPTURE"
            and e5f6_result.value == "direct capture"
        )
        a3d6_result = stockfish.will_move_be_a_capture("a3d6")
        assert (
            a3d6_result is Stockfish.Capture.NO_CAPTURE
            and a3d6_result.name == "NO_CAPTURE"
            and a3d6_result.value == "no capture"
        )
        a7a8q_result = stockfish.will_move_be_a_capture("a7a8q")
        assert (
            a7a8q_result is Stockfish.Capture.NO_CAPTURE
            and a7a8q_result.name == "NO_CAPTURE"
            and a7a8q_result.value == "no capture"
        )
        a7a8b_result = stockfish.will_move_be_a_capture("a7a8b")
        assert (
            a7a8b_result is Stockfish.Capture.NO_CAPTURE
            and a7a8b_result.name == "NO_CAPTURE"
            and a7a8b_result.value == "no capture"
        )
        a7b8q_result = stockfish.will_move_be_a_capture("a7b8q")
        assert (
            a7b8q_result is Stockfish.Capture.DIRECT_CAPTURE
            and a7b8q_result.name == "DIRECT_CAPTURE"
            and a7b8q_result.value == "direct capture"
        )
        a7b8r_result = stockfish.will_move_be_a_capture("a7b8r")
        assert (
            a7b8r_result is Stockfish.Capture.DIRECT_CAPTURE
            and a7b8r_result.name == "DIRECT_CAPTURE"
            and a7b8r_result.value == "direct capture"
        )

        with pytest.raises(ValueError):
            stockfish.will_move_be_a_capture("c3c5")

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "fen",
        [
            "2k2q2/8/8/8/8/8/8/2Q2K2 w - - 0 1",
            "8/8/8/3k4/3K4/8/8/8 b - - 0 1",
            "1q2nB2/pP1k2KP/NN1Q1qP1/8/1P1p4/4p1br/3R4/6n1 w - - 0 1",
            "3rk1n1/ppp3pp/8/8/8/8/PPP5/1KR1R3 w - - 0 1",
        ],
    )
    def test_invalid_fen_king_attacked(self, stockfish: Stockfish, fen):
        # Each of these FENs have correct syntax, but
        # involve a king being attacked while it's the opponent's turn.
        old_del_counter = Stockfish._del_counter
        assert Stockfish._is_fen_syntax_valid(fen)
        if (
            fen == "8/8/8/3k4/3K4/8/8/8 b - - 0 1"
            and stockfish.get_stockfish_major_version() >= 14
        ):
            # Since for this FEN, more recent versions of SF (some dev versions of 14 and later)
            # output a best move without crashing.
            return
        if (
            fen == "2k2q2/8/8/8/8/8/8/2Q2K2 w - - 0 1"
            and stockfish.get_stockfish_major_version() >= 15
        ):
            # Development versions post SF 15 seem to output a bestmove for this fen.
            return
        assert not stockfish.is_fen_valid(fen)
        assert Stockfish._del_counter == old_del_counter + 2

        stockfish.set_fen_position(fen)
        with pytest.raises(StockfishException):
            stockfish.get_evaluation()

    @pytest.mark.slow
    def test_is_fen_valid(self, stockfish: Stockfish):
        old_params = stockfish.get_engine_parameters()
        old_info = stockfish.info
        old_depth = stockfish._depth
        old_fen = stockfish.get_fen_position()
        correct_fens: List[Optional[str]] = [
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "r1bQkb1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNB2RK1 b kq - 0 8",
            "4k3/8/4K3/8/8/8/8/8 w - - 10 50",
            "r1b1kb1r/ppp2ppp/3q4/8/P2Q4/8/1PP2PPP/RNB2RK1 w kq - 8 15",
            "4k3/8/4K3/8/8/8/8/8 w - - 99 50",
        ]
        invalid_syntax_fens = [
            "r1bQkb1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNB2RK b kq - 0 8",
            "rnbqkb1r/pppp1ppp/4pn2/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq - 3",
            "rn1q1rk1/pbppbppp/1p2pn2/8/2PP4/5NP1/PP2PPBP/RNBQ1RK1 w w - 5 7",
            "4k3/8/4K3/71/8/8/8/8 w - - 10 50",
            "r1bQkb1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNB2R2 b kq - 0 8",
            "r1bQ1b1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNB2RK1 b kq - 0 8",
            "4k3/8/4K3/8/8/8/8/8 w - - 100 50",
            "4k3/8/4K3/8/8/8/8/8 w - - 101 50",
            "4k3/8/4K3/8/8/8/8/8 w - - -1 50",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 0",
            "r1b1kb1r/ppp2ppp/3q4/8/P2Q4/8/1PP2PPP/RNB2RK1 w kq - - 8 15",
            "r1b1kb1r/ppp2ppp/3q4/8/P2Q4/8/1PP2PPP/RNB2RK1 w kq 8 15",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR W KQkq - 0 1",
            "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR - KQkq - 0 1",
            "r1bQkb1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNB2RK1 b kq - - 8",
            "r1bQkb1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNB2RK1 b kq - 0 -",
            "r1bQkb1r/ppp2ppp/2p5/4Pn2/8/5N2/PPP2PPP/RNB2RK1 b kq - -1 8",
            "4k3/8/4K3/8/8/8/8/8 w - - 99 e",
            "4k3/8/4K3/8/8/8/8/8 w - - 99 ee",
        ]
        correct_fens.extend([None] * (len(invalid_syntax_fens) - len(correct_fens)))
        assert len(correct_fens) == len(invalid_syntax_fens)
        for correct_fen, invalid_syntax_fen in zip(correct_fens, invalid_syntax_fens):
            old_del_counter = Stockfish._del_counter
            if correct_fen is not None:
                assert stockfish.is_fen_valid(correct_fen)
                assert stockfish._is_fen_syntax_valid(correct_fen)
            assert not stockfish.is_fen_valid(invalid_syntax_fen)
            assert not stockfish._is_fen_syntax_valid(invalid_syntax_fen)
            assert Stockfish._del_counter == old_del_counter + (
                2 if correct_fen is not None else 0
            )

        time.sleep(2.0)
        assert stockfish._stockfish.poll() is None
        assert stockfish.get_engine_parameters() == old_params
        assert stockfish.info == old_info
        assert stockfish._depth == old_depth
        assert stockfish.get_fen_position() == old_fen

    def test_send_quit_command(self, stockfish: Stockfish):
        assert stockfish._stockfish.poll() is None
        old_del_counter = Stockfish._del_counter
        stockfish.send_quit_command()
        assert stockfish._stockfish.poll() is not None
        stockfish.__del__()
        assert stockfish._stockfish.poll() is not None
        assert Stockfish._del_counter == old_del_counter + 1

    def test_set_stockfish_version(self, stockfish: Stockfish):
        stockfish._set_stockfish_version()
        assert stockfish.get_stockfish_full_version() > 0
        assert stockfish.get_stockfish_major_version() in (8, 9, 10, 11, 12, 13, 14, 15)
        assert stockfish.get_stockfish_minor_version() >= 0

    def test_get_stockfish_major_version(self, stockfish: Stockfish):
        assert stockfish.get_stockfish_major_version() in (8, 9, 10, 11, 12, 13, 14, 15)

    @pytest.mark.parametrize(
        "info",
        [
            ["dev-20221219-61ea1534", 15.1, "20221219", "61ea1534", True],
            ["280322", 14.1, "280322", "", True],
            ["15.1", 15.1, "", "", False],
            ["14", 14.0, "", "", False],
            ["16", 16.0, "", "", False],
            ["250723", 16.0, "250723", "", True],
        ],
    )
    def test_parse_stockfish_version(self, stockfish: Stockfish, info):
        stockfish._parse_stockfish_version(info[0])
        assert stockfish.get_stockfish_full_version() == info[1]
        assert stockfish.get_stockfish_major_version() == int(info[1])
        assert stockfish.get_stockfish_minor_version() == round(
            10 * (info[1] - int(info[1]))
        )
        assert stockfish.get_stockfish_patch_version() == info[2]
        assert stockfish.get_stockfish_sha_version() == info[3]
        assert stockfish.is_development_build_of_engine() is info[4]

    def test_parse_stockfish_version_raise_exception(self, stockfish: Stockfish):
        with pytest.raises(Exception):
            stockfish._parse_stockfish_version("not a version")

    def test_get_stockfish_version_from_build_date_raise_exception(
        self, stockfish: Stockfish
    ):
        with pytest.raises(Exception):
            stockfish._get_stockfish_version_from_build_date("2015-12-19")

    def test_set_option(self, stockfish: Stockfish):
        stockfish._set_option("MultiPV", 3)
        assert stockfish.get_engine_parameters()["MultiPV"] == 3
        stockfish._set_option("MultiPV", 6, False)  # update_parameters_attribute
        assert stockfish.get_engine_parameters()["MultiPV"] == 3

    def test_pick(self, stockfish: Stockfish):
        info = "info depth 10 seldepth 15 multipv 1 score cp -677 wdl 0 0 1000"
        line = info.split(" ")
        assert stockfish._pick(line, "depth") == "10"
        assert stockfish._pick(line, "multipv") == "1"
        assert stockfish._pick(line, "wdl", 3) == "1000"

    def test_get_engine_parameters(self, stockfish: Stockfish):
        params = stockfish.get_engine_parameters()
        params.update({"Skill Level": 10})
        assert params["Skill Level"] == 10
        assert stockfish._parameters["Skill Level"] == 20

    @pytest.mark.slow
    def test_uci_new_game_wait(self, stockfish: Stockfish):
        stockfish.update_engine_parameters({"Hash": 2048})
        start = time.time_ns()
        stockfish.send_ucinewgame_command()
        assert time.time_ns() - start > 1000000

    def test_hash_size_platform(self, stockfish: Stockfish):
        max_hash = stockfish._PARAM_RESTRICTIONS["Hash"][2]
        assert max_hash == 2 ** (25 if "64" in platform.machine() else 11)

    def test_threefold_detection(self, stockfish: Stockfish):
        stockfish.set_depth(5)
        stockfish.make_moves_from_current_position(
            ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8", "g1f3"]
        )
        assert compare(stockfish.get_evaluation()["value"], 0, operator.eq, int)
        stockfish.make_moves_from_start(
            ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6", "f3g1", "f6g8", "g1f3"]
        )
        assert compare(stockfish.get_evaluation()["value"], 0, operator.eq, int)
        stockfish.make_moves_from_start(["g1f3", "g8f6", "f3g1", "f6g8", "g1f3"])
        assert compare(stockfish.get_evaluation()["value"], 0, operator.lt, int)
        stockfish.make_moves_from_current_position(["g8f6", "f3g1", "f6g8", "g1f3"])
        assert compare(stockfish.get_evaluation()["value"], 0, operator.lt, int)
