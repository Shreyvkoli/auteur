"""
Background Worker — Processes edit jobs from Redis queue.
Run with: python worker.py
Supports graceful shutdown via SIGINT/SIGTERM.
"""

import asyncio
import signal
import logging
from services.queue import start_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    shutdown_event = asyncio.Event()

    def _handle_signal():
        logger.info("Shutdown signal received, finishing current job...")
        shutdown_event.set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(start_worker(shutdown_event=shutdown_event))
    except KeyboardInterrupt:
        pass
    finally:
        pending = asyncio.all_tasks(loop)
        for t in pending:
            t.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        logger.info("Worker shut down cleanly")
