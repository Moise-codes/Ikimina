"""Shared, framework-free helpers used across the application.

Modules here (phone handling, money arithmetic, pagination, clock) have no
dependency on FastAPI or the ORM so they can be reused, tested in isolation and
imported freely by services, workers and tests.
"""
