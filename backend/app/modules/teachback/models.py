"""Teach-back uses the shared tables in app/core/models.py.

Tries are not stored in a table of their own: each scored try is a teachback.scored row in
the append-only events table, and the question and answers are chat messages.
"""
