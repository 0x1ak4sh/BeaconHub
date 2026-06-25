"""
Event logger and WebSocket broadcaster.
Central logging system that captures events and broadcasts them to connected clients.
"""

import asyncio
import functools
import logging
import threading
import time
from typing import List, Set, Dict, Any
from datetime import datetime
from collections import deque

logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus that stores log entries and broadcasts to WebSocket clients.
    Thread-safe via asyncio.
    """

    def __init__(self, max_history: int = 500):
        self._history: deque = deque(maxlen=max_history)
        self._subscribers: Set[asyncio.Queue] = set()
        self._lock = threading.Lock()

    def _append_and_broadcast(self, entry: dict):
        """Thread-safe append to history + broadcast to all subscribers."""
        with self._lock:
            dead_queues = set()
            for queue in self._subscribers:
                try:
                    queue.put_nowait(entry)
                except asyncio.QueueFull:
                    pass
                except Exception:
                    dead_queues.add(queue)
            self._subscribers -= dead_queues
            self._history.append(entry)

    async def publish(self, level: str, source: str, message: str):
        """Publish an event from async context offloaded to thread pool."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "source": source,
            "message": message,
        }
        await asyncio.to_thread(self._append_and_broadcast, entry)

    def publish_sync(self, level: str, source: str, message: str):
        """Synchronous publish for use from non-async contexts."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "source": source,
            "message": message,
        }
        self._append_and_broadcast(entry)

    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to events. Returns a queue that will receive events."""
        queue = asyncio.Queue(maxsize=100)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._subscribe_sync, queue)
        return queue

    def _subscribe_sync(self, queue: asyncio.Queue):
        with self._lock:
            self._subscribers.add(queue)

    async def unsubscribe(self, queue: asyncio.Queue):
        """Unsubscribe from events."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._unsubscribe_sync, queue)

    def _unsubscribe_sync(self, queue: asyncio.Queue):
        with self._lock:
            self._subscribers.discard(queue)

    def get_history(self, count: int = 50) -> List[Dict[str, Any]]:
        """Get recent event history."""
        entries = list(self._history)
        return entries[-count:]

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# Global event bus instance
event_bus = EventBus()
