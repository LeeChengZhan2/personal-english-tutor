"""Personal English Tutor: learn English from the messages you type to Claude Code.

read -> analyze -> practise, started by the app's "Update my lessons" button (run.py):
- capture.py reads Claude Code's conversation files and keeps what the user typed (data/inbox/).
- analyze.py asks Claude to find the English mistakes and turn them into lessons (data/batches/).
- vocab.py adds a vocabulary list to each lesson batch.
The app (server/ and web/) turns the lessons into practice cards.
"""
