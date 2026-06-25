"""
BeaconHub - Backend API
"""

import asyncio
import logging
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.ap import router as ap_router
from .api.adapters import router as adapters_router
from .api.clients import router as clients_router
from .api.attacks import router as attacks_router
from .api.scenarios import router as scenarios_router
from .api.system import router as system_router
from .api.ws import router as ws_router
from .api.radius import router as radius_router
from .api.capture import router as capture_router
from .core.lab_manager import LabManager
from .core.events import event_bus

# Ensure log directory exists
os.makedirs("/opt/beaconhub/logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/opt/beaconhub/logs/backend.log", mode="a"),
    ]
)
logger = logging.getLogger(__name__)

lab_manager: Optional[LabManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Startup and shutdown."""
    global lab_manager

    logger.info("BeaconHub backend starting...")

    lab_manager = LabManager()
    app.state.lab_manager = lab_manager

    # Initialize — detect interfaces (module already loaded by start.sh)
    try:
        num_radios = int(os.environ.get("BEACONHUB_RADIOS", "6"))
        await lab_manager.initialize(radios=num_radios)
        logger.info("Lab initialized")
    except Exception as e:
        logger.error(f"Init failed: {e}")
        await event_bus.publish("error", "lab", f"Initialization failed: {str(e)}")

    yield

    logger.info("Shutting down...")
    if lab_manager:
        await lab_manager.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(
        title="BeaconHub",
        description="Virtual Wi-Fi Penetration Testing Lab",
        version="2.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system_router, prefix="/api", tags=["system"])
    app.include_router(ap_router, prefix="/api/ap", tags=["access-points"])
    app.include_router(adapters_router, prefix="/api/adapters", tags=["adapters"])
    app.include_router(clients_router, prefix="/api/clients", tags=["clients"])
    app.include_router(attacks_router, prefix="/api/attacks", tags=["attacks"])
    app.include_router(scenarios_router, prefix="/api/scenarios", tags=["scenarios"])
    app.include_router(radius_router, prefix="/api/radius", tags=["radius"])
    app.include_router(ws_router, prefix="/api/ws", tags=["websocket"])
    app.include_router(capture_router, prefix="/api/capture", tags=["capture"])

    return app


app = create_app()
