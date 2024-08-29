import pytest
from timeit import default_timer
import time
from typing import List, Optional, Dict
import subprocess
from subprocess import Popen
import os


def send_command(process, command: str):
    process.stdin.write(command + "\n")
    process.stdin.flush()
    lines = []
    if command.startswith("position fen"):
        return []
    while True:
        line = process.stdout.readline()
        lines.append(line)
        print(line)
        if line in ("", "\n"):
            break
        if any(x in line for x in ("bestmove", "isready", "readyok", "uciok")):
            break
    return lines


class TestStockfish:

    def test_sf_process(self):
        # Get the path to the current directory
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Path to the stockfish executable
        stockfish_path = os.path.join(current_dir, "stockfish")

        # Start the stockfish process
        process = subprocess.Popen(
            "stockfish",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        send_command(process, "uci")
        send_command(process, "isready")
        send_command(
            process,
            "position fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        )
        send_command(
            process,
            "position fen rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        )
        send_command(
            process,
            "position fen rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        )
        wtime_lines = send_command(process, "go wtime 1000")
        btime_lines = send_command(process, "go btime 1000")
        send_command(process, "quit")
        assert any(
            x.startswith(f"bestmove {move}")
            for move in ("d2d4", "b1c3")
            for x in wtime_lines
        )
        assert any(
            x.startswith(f"bestmove {move}")
            for move in ("d2d4", "b1c3")
            for x in btime_lines
        )
