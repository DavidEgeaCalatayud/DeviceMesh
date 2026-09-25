import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

from app.core.metrics import db_query_duration


def instrument_engine(engine: Engine) -> None:
    @event.listens_for(engine, "before_cursor_execute")
    def before(connection: Any, cursor: Any, statement: Any, parameters: Any,
               context: Any, executemany: Any) -> None:
        context._devicemesh_started = time.perf_counter()

    @event.listens_for(engine, "after_cursor_execute")
    def after(connection: Any, cursor: Any, statement: Any, parameters: Any,
              context: Any, executemany: Any) -> None:
        db_query_duration.observe(time.perf_counter() - context._devicemesh_started)
