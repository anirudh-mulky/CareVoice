"""Reports use the shared tables in app/core/models.py (reports, messages).

A report is created when the patient speaks, but stays hidden from the doctor until the
patient says yes to the read-back (confirmed_by_patient). A "no" sets rejected_at.
"""
