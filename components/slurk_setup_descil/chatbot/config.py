# -*- coding: utf-8 -*-
"""File contains global variables meant to be used read-only."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# This many game rounds will be played per room and player pair.
N = 1
# Set this seed to make the random process reproducible.
SEED = None

# All below *TIME_* variables are in minutes.
# They indicate how long a situation has to persist for something to happen.

# Remind the player to send the /ready command if they have not done so until then.
TIME_READY = 1.0
# Reset the status 'done' to 'ready' of one player if the other does not agree
# that they have found the difference.
TIME_DONE = 0.5
# A participant remaining in the waiting room will be remunerated with an AMT Token.
TIME_WAITING = 5.0
# One player did not answer their partner.
# The game will be ended and only the partner receives an AMT Token.
TIME_ANSWER = 2.0
# The participants will be asked to come to an end.
# Counted per game round and not per game.
TIME_GAME = 5.5
# The participants will be moved back to the waiting room after the game finished.
TIME_CLOSE = 0.25


TASK_TITLE = "Play with the AI."

TASK_GREETING = ["Hi everyone!"]
