# db.py
import os
import oracledb   # <-- NEW

"""
Database layer for LetsCycleToRecycle.
"""

ORACLE_USER = "C##LetsCycleToRecycle"
ORACLE_PASSWORD = "Oracle16!a"
ORACLE_DSN = "localhost/XE"   # project service name

def get_connection():
    """
    Returns a new Oracle connection.

    Usage:
        from db import get_connection
        conn = get_connection()
    """
    return oracledb.connect(
        user=ORACLE_USER,
        password=ORACLE_PASSWORD,
        dsn=ORACLE_DSN,
    )