import asyncio

from app.application.ports import EventRepository
from app.domain.events.models import DeviceEvent


class InProcessEventPublisher:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._queue: asyncio.Queue[DeviceEvent] | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._queue = asyncio.Queue()

    def unbind(self) -> None:
        self._loop = None
        self._queue = None

    def publish(self, event: DeviceEvent) -> None:
        loop = self._loop
        queue = self._queue
        if loop is None or queue is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(queue.put_nowait, event)

    async def receive(self) -> DeviceEvent:
        queue = self._queue
        if queue is None:
            raise RuntimeError("event publisher is not bound to an application loop")
        return await queue.get()


class PublishingEventRepository:
    def __init__(self, repository: EventRepository, publisher: InProcessEventPublisher) -> None:
        self._repository = repository
        self._publisher = publisher

    def append(self, event: DeviceEvent) -> None:
        self._repository.append(event)
        self._publisher.publish(event)

    def list_recent(self, limit: int = 100) -> list[DeviceEvent]:
        return self._repository.list_recent(limit)
