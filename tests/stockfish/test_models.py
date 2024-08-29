import pytest
from timeit import default_timer
import time
from typing import List, Optional, Dict
import subprocess
from subprocess import Popen
import os

def send_command(process: Popen, command):
    process.stdin.write(command + "\n")
    process.stdin.flush()
    response = process.stdout.readline()
    return response


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
            text=True
        )

        send_command(process, "uci")
        send_command(process, "isready")
        send_command(process, "position fen rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1 moves e2e4 e7e6")
        print(send_command(process, "go wtime 1000"))
        print(send_command(process, "go btime 1000"))
        send_command(process, "quit")


