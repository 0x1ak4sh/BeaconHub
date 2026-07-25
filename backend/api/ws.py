"""
WebSocket endpoint for real-time event streaming.
"""

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..core.events import event_bus

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/events")
async def websocket_events(websocket: WebSocket):
    """
    WebSocket endpoint that streams real-time events to connected clients.
    On connect, sends recent history then streams new events.
    
    Uses two concurrent tasks:
    - One reads from the event queue and sends to client
    - One reads from the client (for ping/pong keepalive)
    """
    await websocket.accept()
    logger.info("WebSocket client connected")

    # Send recent history on connect
    history = event_bus.get_history(30)
    for entry in history:
        try:
            await websocket.send_json(entry)
        except Exception:
            return

    # Subscribe to new events
    queue = await event_bus.subscribe()

    async def send_events():
        """Read events from queue and send to WebSocket client."""
        try:
            while True:
                entry = await queue.get()
                await websocket.send_json(entry)
        except Exception:
            pass

    async def receive_messages():
        """Read messages from WebSocket client (ping/pong keepalive)."""
        try:
            while True:
                text = await websocket.receive_text()
                if text == '__ping__':
                    await websocket.send_text('__pong__')
        except WebSocketDisconnect:
            pass
        except Exception:
            pass

    # Run both tasks concurrently - when either finishes, cancel the other
    send_task = asyncio.create_task(send_events())
    recv_task = asyncio.create_task(receive_messages())

    try:
        # Wait for either task to complete (usually recv_task when client disconnects)
        done, pending = await asyncio.wait(
            [send_task, recv_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Cancel the remaining task
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up
        send_task.cancel()
        recv_task.cancel()
        await event_bus.unsubscribe(queue)
        logger.info("WebSocket client disconnected")
