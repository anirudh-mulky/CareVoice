"""Outcomes uses the shared tables in app/core/models.py (reports, messages, discharges).

What happened is recorded as events (report.alert, remedy.approved, doctor.replied,
alert.handled, episode.closed), not in tables of its own.
"""
