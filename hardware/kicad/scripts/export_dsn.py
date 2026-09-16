#!/usr/bin/env python3
"""Export a Specctra DSN for the autorouter from the current board state.

Usage: python3 export_dsn.py <board.kicad_pcb> <out.dsn>
"""
import sys

import pcbnew

board = pcbnew.LoadBoard(sys.argv[1])
ok = pcbnew.ExportSpecctraDSN(board, sys.argv[2])
print("export dsn:", ok, sys.argv[2])
sys.exit(0 if ok else 1)
