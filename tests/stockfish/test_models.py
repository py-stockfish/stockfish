import pytest
from timeit import default_timer
import time
from typing import List, Optional, Dict

from stockfish import Stockfish, StockfishException


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

    @pytest.mark.slow
    def test_get_best_move_remaining_time_not_first_move(self, stockfish: Stockfish):
        stockfish.make_moves_from_current_position(["e2e4", "e7e6"])
        best_move = stockfish.get_best_move(wtime=1000)
        assert best_move in ("d2d4", "a2a3", "d1e2", "b1c3")
        assert stockfish.get_top_moves(num_top_moves=1, btime=1000)[0]["Move"] in ("d2d4", "b1c3")
        best_move = stockfish.get_best_move(wtime=1000, btime=1000)
        assert best_move in ("d2d4", "b1c3", "g1f3")
        best_move = stockfish.get_best_move(wtime=5 * 60 * 1000, btime=1000)
        assert best_move in ("e2e3", "e2e4", "g1f3", "b1c3", "d2d4")
