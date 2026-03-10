"""In-memory job progress broadcast for WebSocket clients."""

import asyncio
# (job_id_str, payload: {step, message})
_progress_queue: asyncio.Queue[tuple[str, dict]] | None = None
_job_connections: dict[str, list] = {}  # job_id -> list of WebSocket


def get_progress_queue() -> asyncio.Queue[tuple[str, dict]]:
    global _progress_queue
    if _progress_queue is None:
        _progress_queue = asyncio.Queue()
    return _progress_queue


def register_ws(job_id: str, ws) -> None:
    if job_id not in _job_connections:
        _job_connections[job_id] = []
    _job_connections[job_id].append(ws)


def unregister_ws(job_id: str, ws) -> None:
    if job_id in _job_connections:
        try:
            _job_connections[job_id].remove(ws)
        except ValueError:
            pass
        if not _job_connections[job_id]:
            del _job_connections[job_id]


async def broadcast_worker() -> None:
    queue = get_progress_queue()
    while True:
        try:
            job_id, payload = await queue.get()
            for ws in _job_connections.get(job_id, []):
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass
        except asyncio.CancelledError:
            break
        except Exception:
            pass
