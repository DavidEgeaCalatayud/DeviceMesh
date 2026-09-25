"""Redis fan-out; PostgreSQL remains the durable event timeline after disconnects."""
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime

import redis
import redis.asyncio as async_redis

from app.domain.events.models import DeviceEvent, EventSeverity

logger = logging.getLogger(__name__)


class RedisEventPublisher:
    def __init__(self, url: str) -> None:
        self.url = url
        self.channel = "devicemesh:events:v1"
        self.writer = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        pass  # Redis carries events independently of the current API's event loop.

    def unbind(self) -> None:
        self.writer.close()

    def publish(self, event: DeviceEvent) -> None:
        try:
            self.writer.publish(self.channel, json.dumps({
                "device_id": event.device_id, "name": event.name,
                "timestamp": event.timestamp.isoformat(), "severity": event.severity.value,
                "attributes": event.attributes,
            }))
        except redis.RedisError:
            logger.warning("realtime publish unavailable; durable timeline retained")

    async def events(self) -> AsyncIterator[DeviceEvent]:
        delay = 1
        while True:
            try:
                async with (
                    async_redis.Redis.from_url(self.url, socket_connect_timeout=2) as client,
                    client.pubsub() as subscription,
                ):
                    await subscription.subscribe(self.channel)
                    delay = 1
                    async for message in subscription.listen():
                        if message["type"] != "message":
                            continue
                        try:
                            raw = json.loads(message["data"])
                            yield DeviceEvent(device_id=raw["device_id"], name=raw["name"],
                                              timestamp=datetime.fromisoformat(raw["timestamp"]),
                                              severity=EventSeverity(raw["severity"]),
                                              attributes=raw["attributes"])
                        except (ValueError, KeyError, TypeError):
                            logger.warning("invalid realtime message discarded")
            except redis.RedisError:
                logger.warning("realtime subscription unavailable; retrying")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
