"""A FastAPI service for a long-running agent: threads, background runs, resumable SSE streams (Lesson 12.04).

No ``from __future__ import annotations`` here: FastAPI reads the dependency annotations at runtime,
and the ``Annotated`` aliases are local to :func:`create_app`.

Endpoints (all but ``/ok`` need ``Authorization: Bearer <key>``):

========================================  ==========================================================
``GET  /ok``, ``/healthz``                 liveness: the process answers (no auth, no model call)
``GET  /ready``                           readiness: started, not draining, database answers (503 otherwise)
``GET  /metrics``                         Prometheus metrics (no auth unless ``METRICS_TOKEN`` is set)
``GET  /threads``                         the caller's threads
``POST /threads``                         create a thread owned by the caller
``GET  /threads/{thread_id}``             the conversation (user and assistant text) and whether it waits for approval
``DELETE /threads/{thread_id}``           delete a thread: its runs, events and checkpoints (the owner's data)
``DELETE /me/data``                       delete all of the caller's threads (spend rows stay: they enforce the caps)
``POST /threads/{thread_id}/runs``        start a run: ``{"message": ...}`` or, for managers, ``{"resume": ...}``;
                                          returns **202** at once; ``Idempotency-Key`` header deduplicates
``GET  /runs/{run_id}``                   status, answer, timings, usage
``GET  /runs/{run_id}/stream``            SSE: ``metadata``, ``token``, ``step``, ``interrupt``, ``end``, ``error``;
                                          reconnect with ``Last-Event-ID`` to resume where you left off
``POST /runs/{run_id}/cancel``            cancel a queued or running run
``GET  /stats``                           run counts and SLOs over this process's runs (managers only)
``GET  /version``                         release, mode and model (no auth): what is deployed right now
``POST /admin/pause``                     kill switch ``{"paused": true}``: refuse new runs with 503 (managers only)
``GET  /ui/``                             the browser UI, when ``create_app(..., ui_dir=...)`` (Lesson 12.09)
========================================  ==========================================================

Every authenticated route is also served under ``/v1`` (``/v1/threads``, ``/v1/runs/{run_id}/stream``, …).

Errors: 401 no, unknown or expired credentials (API key or JWT) · 404 thread or run not yours (not 403: don't reveal that it exists) ·
409 thread busy · 413 message too long · 422 bad body · 429 queue full or over budget (``Retry-After``) ·
503 shutting down or paused (``Retry-After``). Every response carries ``X-Request-ID`` (Lesson 12.07).
"""

import hmac
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, model_validator

from mastery.service.observability import RequestContextMiddleware, ServiceMetrics, configure_logging, log_run
from mastery.service.runs import OverBudget, RunManager, ServiceBusy, ThreadBusy
from mastery.service.settings import Principal, ServiceSettings
from mastery.service.slo import default_slos, evaluate_slo


class RunRequest(BaseModel):
    message: str | None = None
    resume: Any = None

    @model_validator(mode="after")
    def _one_of(self) -> "RunRequest":
        if (self.message is None) == (self.resume is None):
            raise ValueError("send exactly one of 'message' or 'resume'")
        return self


class PauseRequest(BaseModel):
    paused: bool


# The UI only loads its own files and talks to this origin: no inline scripts, no third-party code.
UI_HEADERS = [(b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self'; "
               b"connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"),
              (b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"no-referrer")]


def _secure_static(directory: Any) -> Any:
    """``StaticFiles`` for the UI, with a strict Content-Security-Policy on every response."""
    from fastapi.staticfiles import StaticFiles

    files = StaticFiles(directory=directory, html=True)

    async def app(scope: Any, receive: Any, send: Any) -> None:
        async def with_headers(message: dict) -> None:
            if message["type"] == "http.response.start":
                message["headers"] = [*message.get("headers", []), *UI_HEADERS]
            await send(message)

        await files(scope, receive, with_headers)

    return app


def create_app(build_manager: Callable[[ServiceSettings], Any], settings: ServiceSettings | None = None,
               *, title: str = "Agent service", ui_dir: Any = None) -> FastAPI:
    """Build the app. ``build_manager(settings)`` returns the :class:`RunManager` at startup, or an async
    context manager that yields one (to open and close a database, Lesson 12.05)."""
    settings = settings or ServiceSettings()
    principals = settings.principals()            # malformed keys fail here, at startup
    verifier = settings.token_verifier()          # None unless JWT settings are given (Lesson 12.05)
    log = configure_logging(settings.log_format, settings.log_level)
    metrics = ServiceMetrics()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        built = build_manager(settings)
        if hasattr(built, "__aenter__"):
            async with built as manager:
                await _start(app, manager)
                yield
                await _stop(app, manager)
        else:
            await _start(app, built)
            yield
            await _stop(app, built)

    async def _start(app: FastAPI, manager: RunManager) -> None:
        app.state.manager = manager
        manager.trace_metadata |= {"release": settings.release, "mode": settings.mode}
        metrics.watch(manager)
        manager.listeners.append(log_run)
        app.state.recovered = await manager.recover()
        log.info("service started", extra={"event": "service.started", "count": len(app.state.recovered)})

    async def _stop(app: FastAPI, manager: RunManager) -> None:
        # Graceful shutdown (SIGTERM): refuse new runs, let active ones finish, save the rest as errors.
        cut = await manager.shutdown(settings.drain_s)
        log.info("service stopped", extra={"event": "service.stopped", "count": len(cut)})

    app = FastAPI(title=title, lifespan=lifespan)
    app.state.settings = settings
    app.state.paused = settings.paused
    app.state.metrics = metrics
    app.add_middleware(RequestContextMiddleware, metrics=metrics)
    bearer = HTTPBearer(auto_error=False)

    def caller(request: Request,
               credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Principal:
        token = credentials.credentials if credentials else ""
        principal = principals.get(token) if token else None
        if principal is None and verifier is not None and token.count(".") == 2:
            principal = verifier.principal(token)        # a JWT: signature, expiry, issuer, audience checked
        if principal is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing, unknown or expired credentials",
                                headers={"WWW-Authenticate": "Bearer"})
        request.state.user_id = principal.user_id        # for the access log line
        return principal

    Caller = Annotated[Principal, Depends(caller)]
    api = APIRouter()                 # the authenticated API: served at / and at /v1 (Project 12)

    def manager(request: Request) -> RunManager:
        return request.app.state.manager

    Manager = Annotated[RunManager, Depends(manager)]

    async def owned_thread(thread_id: str, who: Principal, runs: RunManager) -> str:
        owner = await runs.store.thread_owner(thread_id)
        if owner is None or (owner != who.user_id and who.role != "manager"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "thread not found")
        return owner

    async def owned_run(run_id: str, who: Principal, runs: RunManager):
        run = await runs.get(run_id)
        if run is None or (run.user_id != who.user_id and who.role != "manager"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
        return run

    @app.get("/ok")
    @app.get("/healthz", include_in_schema=False)
    async def ok() -> dict[str, bool]:
        return {"ok": True}

    @app.get("/ready")
    async def ready(request: Request) -> JSONResponse:
        runs = getattr(request.app.state, "manager", None)
        problems = []
        if runs is None:
            problems.append("starting")
        elif runs.draining:
            problems.append("shutting down")
        else:
            try:
                await runs.store.ping()
            except Exception as exc:  # noqa: BLE001  (report it, don't crash the probe)
                problems.append(f"database: {type(exc).__name__}")
        code = status.HTTP_503_SERVICE_UNAVAILABLE if problems else status.HTTP_200_OK
        return JSONResponse({"ready": not problems, "problems": problems, "release": settings.release},
                            status_code=code)

    @app.get("/metrics", include_in_schema=False)
    async def prometheus(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Response:
        expected = settings.metrics_token.get_secret_value() if settings.metrics_token else None
        given = credentials.credentials if credentials else ""
        if expected and not hmac.compare_digest(given.encode(), expected.encode()):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "metrics token required",
                                headers={"WWW-Authenticate": "Bearer"})
        body, content_type = metrics.render()
        return Response(body, media_type=content_type)

    @api.get("/threads")
    async def my_threads(who: Caller, runs: Manager) -> dict[str, list[str]]:
        return {"threads": await runs.store.list_threads(who.user_id)}

    @api.post("/threads", status_code=status.HTTP_201_CREATED)
    async def create_thread(who: Caller, runs: Manager) -> dict[str, str]:
        import uuid

        thread_id = f"thread-{uuid.uuid4().hex[:12]}"
        await runs.store.add_thread(thread_id, who.user_id)
        return {"thread_id": thread_id}

    async def erase_thread(thread_id: str, runs: RunManager) -> int:
        active = [r for r in runs.runs.values() if r.thread_id == thread_id and not r.done]
        for run in active:
            await runs.cancel(run.run_id)
        deleted = await runs.store.delete_thread(thread_id)
        for run_id in deleted:
            runs.runs.pop(run_id, None)
        checkpointer = getattr(runs.graph, "checkpointer", None)
        if checkpointer is not None:
            await checkpointer.adelete_thread(thread_id)          # the conversation itself
        return len(deleted)

    @api.delete("/threads/{thread_id}")
    async def delete_thread(thread_id: str, who: Caller, runs: Manager) -> dict[str, Any]:
        await owned_thread(thread_id, who, runs)
        return {"thread_id": thread_id, "deleted_runs": await erase_thread(thread_id, runs)}

    @api.get("/threads/{thread_id}")
    async def thread_history(thread_id: str, who: Caller, runs: Manager) -> dict[str, Any]:
        """The conversation so far (user and assistant text only) and whether it waits for an approval."""
        await owned_thread(thread_id, who, runs)
        state = await runs.graph.aget_state({"configurable": {"thread_id": thread_id}})
        messages = []
        for m in (state.values or {}).get("messages", []):
            role = {"human": "user", "ai": "assistant"}.get(getattr(m, "type", ""))
            if role and isinstance(m.content, str) and m.content.strip():
                messages.append({"role": role, "content": m.content})
        return {"thread_id": thread_id, "messages": messages, "waiting_for_approval": bool(state.interrupts)}

    @api.delete("/me/data")
    async def delete_my_data(who: Caller, runs: Manager) -> dict[str, Any]:
        """Erase every thread of the caller: runs, events, idempotency keys and checkpoints.

        Spend rows (day, user id, dollars) are kept: they enforce the daily caps and hold no conversation data.
        """
        threads = await runs.store.list_threads(who.user_id)
        deleted_runs = 0
        for thread_id in threads:
            deleted_runs += await erase_thread(thread_id, runs)
        return {"user_id": who.user_id, "deleted_threads": len(threads), "deleted_runs": deleted_runs}

    @api.post("/threads/{thread_id}/runs", status_code=status.HTTP_202_ACCEPTED)
    async def start_run(thread_id: str, body: RunRequest, who: Caller, runs: Manager, request: Request,
                        idempotency_key: Annotated[str | None, Header()] = None) -> dict[str, Any]:
        owner = await owned_thread(thread_id, who, runs)
        if request.app.state.paused:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "the agent is paused by the operator; try again later",
                                headers={"Retry-After": "60"})
        if body.message is not None:
            if len(body.message) > settings.max_message_chars:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                                    f"message longer than {settings.max_message_chars} characters")
            graph_input: Any = {"messages": [{"role": "user", "content": body.message}]}
        else:
            if who.role != "manager":            # only a billing manager answers an approval
                raise HTTPException(status.HTTP_403_FORBIDDEN, "only a manager can resume a run")
            from langgraph.types import Command

            graph_input = Command(resume=body.resume)
        try:
            run = await runs.submit(thread_id=thread_id, user_id=owner, input=graph_input,
                                    idempotency_key=idempotency_key)
        except ServiceBusy as exc:
            if runs.draining:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc), headers={"Retry-After": "5"}) from exc
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc), headers={"Retry-After": "5"}) from exc
        except ThreadBusy as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
        except OverBudget as exc:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc), headers={"Retry-After": "5"}) from exc
        return {"run_id": run.run_id, "thread_id": thread_id, "status": run.status}

    @api.get("/runs/{run_id}")
    async def get_run(run_id: str, who: Caller, runs: Manager) -> dict[str, Any]:
        return (await owned_run(run_id, who, runs)).public()

    async def stream_target(run_id: str, who: Caller, runs: Manager) -> Any:
        # Resolved as a dependency so a foreign run is a clean 404 *before* the stream starts;
        # raising inside the generator would cut the connection mid-response instead.
        return await owned_run(run_id, who, runs)

    @api.get("/runs/{run_id}/stream", response_class=EventSourceResponse)
    async def stream_run(run: Annotated[Any, Depends(stream_target)], runs: Manager, request: Request,
                         last_event_id: Annotated[str | None, Header()] = None) -> AsyncIterator[ServerSentEvent]:
        after = int(last_event_id) if last_event_id and last_event_id.isdigit() else -1
        async for event in runs.follow(run.run_id, after=after, heartbeat_s=10):
            if await request.is_disconnected():
                return                          # the client left; the run keeps going server-side
            if event is None:
                yield ServerSentEvent(comment="keep-alive")
            else:
                yield ServerSentEvent(data=event.data, event=event.event, id=str(event.id))

    @api.post("/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
    async def cancel_run(run_id: str, who: Caller, runs: Manager) -> dict[str, Any]:
        run = await runs.cancel((await owned_run(run_id, who, runs)).run_id)
        return {"run_id": run.run_id, "status": run.status}

    @api.get("/stats")
    async def stats(who: Caller, runs: Manager) -> dict[str, Any]:
        if who.role != "manager":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "managers only")
        records = runs.records()
        slos = []
        for slo in default_slos() if records else []:
            result = evaluate_slo(slo, records)
            slos.append({"name": result.name, "target": result.target, "good": result.good,
                         "eligible": result.eligible, "met": result.met if result.eligible else None})
        return {**runs.stats(), "slos": slos}

    @app.get("/version")
    async def version(request: Request) -> dict[str, Any]:
        runs = getattr(request.app.state, "manager", None)
        return {"release": settings.release, "mode": settings.mode, "model": getattr(runs, "model", None),
                "paused": request.app.state.paused}

    @api.post("/admin/pause")
    async def pause(body: PauseRequest, who: Caller, request: Request) -> dict[str, bool]:
        if who.role != "manager":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "managers only")
        request.app.state.paused = body.paused          # this process only; set PAUSED in the platform to persist
        log.warning("kill switch", extra={"event": "service.paused" if body.paused else "service.resumed",
                                          "user_id": who.user_id})
        return {"paused": body.paused}

    app.include_router(api, include_in_schema=False)     # unversioned: the UI and Lessons 12.04-12.09
    app.include_router(api, prefix="/v1")                  # versioned: what clients outside this repo should use

    if ui_dir is not None:
        app.mount("/ui", _secure_static(ui_dir), name="ui")

        @app.get("/", include_in_schema=False)
        async def home() -> RedirectResponse:
            return RedirectResponse("/ui/")

    @app.exception_handler(ValueError)
    async def bad_value(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

    return app


def serve_in_background(app: FastAPI, host: str = "127.0.0.1", port: int = 0) -> tuple[str, Callable[[], None]]:
    """Run ``app`` with uvicorn in a daemon thread (notebooks, tests). Returns ``(base_url, stop)``.

    ``port=0`` picks a free port. ``stop()`` shuts the server down and waits for the thread.
    """
    import threading
    import time

    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if not thread.is_alive() or time.monotonic() > deadline:
            raise RuntimeError("the server did not start (see the log above)")
        time.sleep(0.02)
    bound = server.servers[0].sockets[0].getsockname()[1]

    def stop() -> None:
        server.should_exit = True
        thread.join(timeout=10)

    return f"http://{host}:{bound}", stop
