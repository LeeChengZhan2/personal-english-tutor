"""Personal English Tutor: the local web app, a FastAPI server for the practice app in web/.

It reads lessons from data/batches (written by coach/), keeps progress in data/tutor.db,
and runs the app's AI checks through the Claude Code CLI.
"""

__version__ = "0.2.0"
