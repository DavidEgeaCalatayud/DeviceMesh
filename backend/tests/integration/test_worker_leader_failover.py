from sqlalchemy import text

from app.infrastructure.database import engine

SCHEDULER_LOCK_ID = 684291017


def _try_lock(connection) -> bool:
    return bool(
        connection.scalar(
            text("SELECT pg_try_advisory_lock(:lock_id)"),
            {"lock_id": SCHEDULER_LOCK_ID},
        )
    )


def _unlock(connection) -> None:
    connection.execute(
        text("SELECT pg_advisory_unlock(:lock_id)"),
        {"lock_id": SCHEDULER_LOCK_ID},
    )


def test_scheduler_lock_has_single_leader_and_fails_over_on_session_loss() -> None:
    leader = engine.connect()
    standby = engine.connect()
    try:
        assert _try_lock(leader) is True
        assert _try_lock(standby) is False

        # PostgreSQL advisory locks are session-scoped. Invalidate the leader's
        # DBAPI connection to model a dead worker/process rather than a graceful
        # unlock, and verify the standby can immediately become leader.
        leader.invalidate()
        leader.close()

        assert _try_lock(standby) is True
    finally:
        if not leader.closed:
            leader.invalidate()
            leader.close()
        try:
            _unlock(standby)
        finally:
            standby.close()
