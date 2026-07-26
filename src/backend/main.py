import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.backend.analytics import compute_aggregate_analytics, compute_friction
from src.backend.generators import CUSTOMER_REGISTRY, generate_dataset, generate_trailing_activity
from src.backend.metrics import ESCALATION_RATE_PCT, HTTP_REQUESTS_TOTAL, RESOLUTION_ACCURACY_PCT
from src.backend.pipeline import run_pipeline
from src.backend.store import EventStore, get_connection

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "src" / "frontend" / "dist"


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        for ws in list(self.active):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(ws)


# The Phase 6 demo centerpiece: cust_006's escalation chain (4 channels,
# tight window) shown scattering, then resolving live, one at a time.
DEMO_SCATTER_REFS = ["app_events:1", "web_events:5", "callcenter_events:2", "inperson_events:1"]
DEMO_ORPHAN_REF = "callcenter_events:5"


def create_app(db_path: str | None = None) -> FastAPI:
    store = EventStore(get_connection(db_path or os.environ["DATABASE_URL"]))
    manager = ConnectionManager()
    state = {"trailing_activity": []}

    def _store_trailing_activity(events):
        for i, e in enumerate(events):
            store.insert(
                e["customer_id"], "trailing_activity", e["action"], e["timestamp"],
                1.0, "deterministic", f"trailing:{i}", "trailing activity ping",
            )

    def _run_seed():
        data = generate_dataset()
        result = run_pipeline(
            data["app_events"], data["web_events"], data["callcenter_events"], data["inperson_events"],
            CUSTOMER_REGISTRY, store,
        )
        activity = generate_trailing_activity()
        _store_trailing_activity(activity)
        state["trailing_activity"] = activity

        correct = sum(
            1 for ref, expected in data["ground_truth"].items()
            if result["resolved"][ref].resolved_customer_id == expected
        )
        accuracy_pct = 100 * correct / len(data["ground_truth"])
        RESOLUTION_ACCURACY_PCT.set(accuracy_pct)

        aggregate = compute_aggregate_analytics(store, activity)
        ESCALATION_RATE_PCT.set(aggregate["escalation_rate_pct"])

        return data, result, accuracy_pct

    def _customer_timeline(customer_id: str) -> list[dict]:
        return [e for e in store.timeline_for_customer(customer_id) if e["channel"] != "trailing_activity"]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if not store.known_customer_ids():
            _run_seed()
        yield

    app = FastAPI(title="Throughline - Cross-Channel Journey Stitching", lifespan=lifespan)

    @app.middleware("http")
    async def _count_requests(request: Request, call_next):
        response = await call_next(request)
        route = request.scope.get("route")
        path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS_TOTAL.labels(method=request.method, path=path, status=response.status_code).inc()
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/seed")
    def seed():
        _data, result, accuracy_pct = _run_seed()
        return {
            "inserted": result["inserted"],
            "pipeline_latency_ms": result["pipeline_latency_ms"],
            "avg_latency_per_event_ms": result["avg_latency_per_event_ms"],
            "resolution_accuracy_pct": accuracy_pct,
        }

    @app.get("/customers")
    def list_customers():
        out = []
        for customer_id in store.known_customer_ids():
            timeline = _customer_timeline(customer_id)
            friction = compute_friction(timeline)
            out.append({
                "customer_id": customer_id,
                "event_count": len(timeline),
                "friction_count": friction["friction_count"],
            })
        return out

    @app.get("/timeline/{customer_id}")
    def get_timeline(customer_id: str):
        timeline = _customer_timeline(customer_id)
        friction = compute_friction(timeline)
        escalation_refs = set(friction["escalation_chain"]["event_refs"]) if friction["escalation_chain"] else set()
        for e in timeline:
            e["is_escalation"] = e["raw_ref"] in escalation_refs
        return {
            "timeline": timeline,
            "repeat_contacts": friction["repeat_contacts"],
            "escalation_chain": friction["escalation_chain"],
            "dropoffs": friction["dropoffs"],
            "friction_count": friction["friction_count"],
        }

    @app.get("/unresolved")
    def get_unresolved():
        return [e for e in store.unresolved_events() if e["channel"] != "trailing_activity"]

    @app.get("/aggregate")
    def get_aggregate():
        return compute_aggregate_analytics(store, state["trailing_activity"])

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    @app.post("/demo/run")
    async def demo_run(delay_seconds: float = 0.6):
        data, result, accuracy_pct = _run_seed()
        resolved = result["resolved"]

        for ref in DEMO_SCATTER_REFS:
            r = resolved[ref]
            await manager.broadcast({
                "type": "scattered", "raw_ref": ref, "channel": r.channel, "timestamp": r.timestamp,
            })
            await asyncio.sleep(delay_seconds)

        for ref in DEMO_SCATTER_REFS:
            r = resolved[ref]
            await manager.broadcast({
                "type": "resolved", "raw_ref": ref, "customer_id": r.resolved_customer_id,
                "confidence": r.confidence, "method": r.method,
            })
            await asyncio.sleep(delay_seconds)

        await manager.broadcast({
            "type": "unresolved_case", "raw_ref": DEMO_ORPHAN_REF,
            "reason": "phone number matches no known customer record",
        })
        await asyncio.sleep(delay_seconds)

        aggregate = compute_aggregate_analytics(store, state["trailing_activity"])
        await manager.broadcast({"type": "aggregate_reveal", "aggregate": aggregate})

        return {"status": "complete", "resolution_accuracy_pct": accuracy_pct}

    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    return app


app = create_app() if os.environ.get("DATABASE_URL") else None
