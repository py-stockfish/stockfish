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
    while True:
        if command.startswith("position fen"):
            break
        line = process.stdout.readline()
        lines.append(line)
        print(line)
        if line == "":
            break
        if any(x in line for x in ("bestmove", "isready", "readyok", "uciok")):
            break
    print(f"exiting function for {command}. list is: {lines}")
    return lines


class TestStockfish:

    def test_sf_process(self):
        # Start the stockfish process
        process = subprocess.Popen(
            "stockfish",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        send_command(process, "isready")
        send_command(
            process,
            "position fen rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        )
        send_command(process, "isready")
        wtime_lines = send_command(process, "go wtime 1000")
        send_command(process, "isready")
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
