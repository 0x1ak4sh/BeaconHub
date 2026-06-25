"""
WebSocket endpoint for real-time event streaming.
"""

import asyncio
import json
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

    try:
        while True:
            # Wait for new events or incoming messages (ping)
            done, pending = await asyncio.wait(
                [asyncio.create_task(queue.get()),
                 asyncio.create_task(websocket.receive_text())],
                return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                result = task.result()
                if isinstance(result, str) and result == '__ping__':
                    await websocket.send_text('__pong__')
                else:
                    await websocket.send_json(result)
            for task in pending:
                task.cancel()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await event_bus.unsubscribe(queue)
