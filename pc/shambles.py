"""
Shambles PC helper.

Fakes an iPhone's GPS location over USB (or Wi-Fi sync) using Apple's developer
location-simulation service, the same mechanism Xcode uses. Nothing is installed on the phone
and no Apple ID is needed: the phone only has to trust this PC and have Developer Mode on.

Run it with "Start Shambles.bat". It serves a map UI at http://localhost:8765 and, for phones on
the same Wi-Fi, at http://<this-pc-ip>:8765/?t=<token> (shown as a QR code in the PC UI).

Important: on iOS 17 and newer the fake location only lasts while this program stays connected to
the phone. Close it (or unplug) and the phone goes back to its real GPS within a few seconds.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import random
import secrets
import socket
import sys
import time
import webbrowser
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from packaging.version import Version
from pydantic import BaseModel

from pymobiledevice3 import usbmux
from pymobiledevice3.exceptions import (
    AlreadyMountedError,
    PairingDialogResponsePendingError,
    PasswordRequiredError,
    PyMobileDevice3Exception,
    UserDeniedPairingError,
)
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.services.mobile_image_mounter import auto_mount
from pymobiledevice3.services.simulate_location import DtSimulateLocation

PORT = int(os.environ.get("SHAMBLES_PORT", "8765"))
HERE = Path(__file__).resolve().parent
WEB = HERE / "web"
DATA_FILE = HERE / "shambles-data.json"

log = logging.getLogger("shambles")

# ---------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------

EARTH_R = 6371000.0


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(h))


def interpolate(a: tuple[float, float], b: tuple[float, float], f: float) -> tuple[float, float]:
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def offset(p: tuple[float, float], heading_deg: float, meters: float) -> tuple[float, float]:
    lat, lon = map(math.radians, p)
    brng = math.radians(heading_deg)
    d = meters / EARTH_R
    lat2 = math.asin(math.sin(lat) * math.cos(d) + math.cos(lat) * math.sin(d) * math.cos(brng))
    lon2 = lon + math.atan2(math.sin(brng) * math.sin(d) * math.cos(lat), math.cos(d) - math.sin(lat) * math.sin(lat2))
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


def lan_ip() -> str:
    with contextlib.suppress(OSError):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        finally:
            s.close()
    return "127.0.0.1"


class UserFacingError(Exception):
    """An error with a message meant for the person using the app."""


def load_data() -> dict[str, Any]:
    if DATA_FILE.exists():
        with contextlib.suppress(Exception):
            return json.loads(DATA_FILE.read_text("utf-8"))
    return {}


def save_data(data: dict[str, Any]) -> None:
    tmp = DATA_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), "utf-8")
    tmp.replace(DATA_FILE)


# ---------------------------------------------------------------------------------------------
# device session
# ---------------------------------------------------------------------------------------------


class DeviceSession:
    """Holds the developer connection to one iPhone and sets its simulated location.

    On iOS 17+ the location only sticks while the DVT channel stays open, so the session is kept
    alive for as long as a fake location is active.
    """

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.stack: Optional[AsyncExitStack] = None
        self.udid: Optional[str] = None
        self.name: Optional[str] = None
        self.version: Optional[str] = None
        self.sim: Any = None  # LocationSimulation or DtSimulateLocation

    @property
    def connected(self) -> bool:
        return self.sim is not None

    async def close(self) -> None:
        stack, self.stack, self.sim = self.stack, None, None
        if stack is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(stack.aclose(), 10)

    async def _open(self, udid: str) -> None:
        await self.close()
        stack = AsyncExitStack()
        try:
            try:
                lockdown = await create_using_usbmux(serial=udid, autopair=True, pair_timeout=60)
            except (PairingDialogResponsePendingError, PasswordRequiredError):
                raise UserFacingError("Unlock your iPhone and tap Trust, then try again.")
            except UserDeniedPairingError:
                raise UserFacingError(
                    "The iPhone said Don't Trust. Unplug it, plug it back in, and tap Trust this time."
                )
            stack.push_async_callback(lockdown.close)

            values = lockdown.all_values
            self.name = values.get("DeviceName") or "iPhone"
            self.version = lockdown.product_version
            ver = Version(self.version)

            if ver >= Version("16.0") and not await lockdown.get_developer_mode_status():
                with contextlib.suppress(Exception):
                    await AmfiService(lockdown).reveal_developer_mode_option_in_ui()
                raise UserFacingError(
                    "Developer Mode is off. On the iPhone go to Settings > Privacy & Security > "
                    "Developer Mode, turn it on, restart, and tap Turn On. "
                    "(Shambles just made that switch show up if it was hidden.)"
                )

            if ver >= Version("17.0"):
                from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel

                tunnel = UserspaceRsdTunnel(serial=udid)
                rsd = await tunnel.aopen()
                stack.push_async_callback(tunnel.aclose)
                await self._mount(rsd)
                dvt = await stack.enter_async_context(DvtProvider(rsd))
                self.sim = await stack.enter_async_context(LocationSimulation(dvt))
            else:
                await self._mount(lockdown)
                self.sim = DtSimulateLocation(lockdown)
            self.stack, self.udid = stack, udid
            log.info("connected to %s (iOS %s)", self.name, self.version)
        except BaseException:
            self.sim = None
            with contextlib.suppress(Exception):
                await stack.aclose()
            raise

    @staticmethod
    async def _mount(provider: Any) -> None:
        try:
            await auto_mount(provider)
        except AlreadyMountedError:
            pass
        except PyMobileDevice3Exception as e:
            # Already-mounted variants differ between iOS versions; only fail if it's clearly not that.
            if "already" not in str(e).lower():
                raise UserFacingError(f"Couldn't set up developer tools on the iPhone: {e}") from e

    async def ensure(self, udid: str) -> None:
        if self.sim is not None and self.udid == udid:
            return
        await self._open(udid)

    async def set(self, udid: str, lat: float, lon: float) -> None:
        async with self.lock:
            for attempt in (1, 2):
                await self.ensure(udid)
                try:
                    await asyncio.wait_for(self.sim.set(lat, lon), 15)
                    return
                except Exception as e:  # connection dropped: reconnect once
                    log.warning("set failed (%r), reconnecting", e)
                    await self.close()
                    if attempt == 2:
                        raise

    async def clear(self) -> None:
        async with self.lock:
            if self.sim is not None:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(self.sim.clear(), 10)
            await self.close()


# ---------------------------------------------------------------------------------------------
# movement engine
# ---------------------------------------------------------------------------------------------


class Mover:
    """Teleport, follow a route at a set speed, or drive with a joystick."""

    TICK = 1.0  # seconds between location updates while moving

    def __init__(self, session: DeviceSession) -> None:
        self.session = session
        self.udid: Optional[str] = None
        self.position: Optional[tuple[float, float]] = None
        self.task: Optional[asyncio.Task] = None
        self.mode = "idle"  # idle | holding | route | joystick
        self.speed = 1.4
        self.paused = False
        self.route: list[tuple[float, float]] = []
        self.route_total = 0.0
        self.route_done = 0.0
        self.loop_route = False
        self.joy_heading = 0.0
        self.joy_active = False
        self.last_error: Optional[str] = None

    async def _apply(self, p: tuple[float, float]) -> None:
        if self.udid is None:
            raise UserFacingError("Pick a device first.")
        await self.session.set(self.udid, p[0], p[1])
        self.position = p

    def _cancel(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
        self.task = None

    async def teleport(self, lat: float, lon: float) -> None:
        self._cancel()
        await self._apply((lat, lon))
        self.mode = "holding"

    async def start_route(self, points: list[tuple[float, float]], speed: float, loop: bool) -> None:
        if len(points) < 2:
            raise UserFacingError("A route needs at least two points.")
        self._cancel()
        self.route = points
        self.route_total = sum(haversine(points[i], points[i + 1]) for i in range(len(points) - 1))
        self.route_done = 0.0
        self.speed = max(0.3, min(speed, 80))
        self.loop_route = loop
        self.paused = False
        await self._apply(points[0])
        self.mode = "route"
        self.task = asyncio.create_task(self._run_route())

    async def _run_route(self) -> None:
        try:
            while True:
                pts = self.route
                seg, dist_into = 0, 0.0
                while seg < len(pts) - 1:
                    await asyncio.sleep(self.TICK)
                    if self.paused:
                        continue
                    step = self.speed * self.TICK * random.uniform(0.9, 1.1)
                    dist_into += step
                    self.route_done += step
                    seg_len = haversine(pts[seg], pts[seg + 1])
                    while seg < len(pts) - 1 and dist_into >= seg_len:
                        dist_into -= seg_len
                        seg += 1
                        if seg < len(pts) - 1:
                            seg_len = haversine(pts[seg], pts[seg + 1])
                    if seg >= len(pts) - 1:
                        p = pts[-1]
                    else:
                        p = interpolate(pts[seg], pts[seg + 1], dist_into / seg_len if seg_len else 1)
                    await self._safe_apply(p)
                if not self.loop_route:
                    break
                self.route = list(reversed(pts))
                self.route_done = 0.0
            self.mode = "holding"
        except asyncio.CancelledError:
            pass

    async def joystick(self, active: bool, heading: float, speed: float) -> None:
        self.joy_active = active
        self.joy_heading = heading
        self.speed = max(0.3, min(speed, 80))
        if self.position is None:
            raise UserFacingError("Teleport somewhere first, then use the joystick.")
        if self.mode != "joystick":
            self._cancel()
            self.mode = "joystick"
            self.task = asyncio.create_task(self._run_joystick())

    async def _run_joystick(self) -> None:
        try:
            while self.mode == "joystick":
                await asyncio.sleep(self.TICK)
                if self.joy_active and self.position is not None:
                    step = self.speed * self.TICK * random.uniform(0.92, 1.08)
                    await self._safe_apply(offset(self.position, self.joy_heading, step))
        except asyncio.CancelledError:
            pass

    async def _safe_apply(self, p: tuple[float, float]) -> None:
        try:
            await self._apply(p)
            self.last_error = None
        except Exception as e:
            self.last_error = str(e)
            log.warning("update failed: %s", e)

    async def keepalive(self) -> None:
        """Re-send a held position now and then, so a dropped connection gets noticed and rebuilt."""
        while True:
            await asyncio.sleep(45)
            if self.mode == "holding" and self.position is not None and not self.session.lock.locked():
                await self._safe_apply(self.position)

    def pause(self, paused: bool) -> None:
        self.paused = paused

    async def stop(self) -> None:
        self._cancel()
        self.mode = "holding" if self.position else "idle"

    async def reset(self) -> None:
        self._cancel()
        self.mode = "idle"
        self.position = None
        await self.session.clear()

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "position": self.position,
            "speed": self.speed,
            "paused": self.paused,
            "route_progress": (self.route_done / self.route_total) if self.route_total else None,
            "route_total_m": self.route_total,
            "error": self.last_error,
        }


# ---------------------------------------------------------------------------------------------
# web app
# ---------------------------------------------------------------------------------------------

data = load_data()
if "token" not in data:
    data["token"] = secrets.token_urlsafe(9)
    save_data(data)
data.setdefault("favorites", [])
data.setdefault("recents", [])

session = DeviceSession()
mover = Mover(session)
app = FastAPI(title="Shambles")


def is_local(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in ("127.0.0.1", "::1", "localhost")


@app.middleware("http")
async def auth(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and not is_local(request):
        token = request.headers.get("x-shambles-token") or request.query_params.get("t")
        if not token or not secrets.compare_digest(token, data["token"]):
            return JSONResponse({"error": "Wrong or missing access code. Scan the QR code on the PC again."}, 401)
    return await call_next(request)


async def run(coro) -> JSONResponse:
    try:
        await coro
        return JSONResponse({"ok": True, **mover.status()})
    except UserFacingError as e:
        return JSONResponse({"ok": False, "error": str(e)}, 400)
    except Exception as e:
        log.exception("request failed")
        return JSONResponse({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)


@app.get("/")
async def index():
    return FileResponse(WEB / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/manifest.webmanifest")
async def manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/icon.svg")
async def icon():
    return FileResponse(WEB / "icon.svg", media_type="image/svg+xml")


@app.get("/api/info")
async def info(request: Request):
    out: dict[str, Any] = {"local": is_local(request)}
    if is_local(request):
        out["phone_url"] = f"http://{lan_ip()}:{PORT}/?t={data['token']}"
    return out


@app.get("/api/devices")
async def devices():
    found = []
    try:
        for d in await usbmux.list_devices():
            found.append({"udid": d.serial, "connection": d.connection_type})
    except Exception as e:
        return {"devices": [], "error": f"Can't see iPhones. Is iTunes installed? ({e})"}
    # de-duplicate (a phone can show up over USB and Wi-Fi at once); prefer USB
    by_udid: dict[str, dict] = {}
    for d in found:
        if d["udid"] not in by_udid or d["connection"] == "USB":
            by_udid[d["udid"]] = d
    result = list(by_udid.values())
    for d in result:
        if d["udid"] == session.udid and session.name:
            d["name"], d["version"] = session.name, session.version
    return {"devices": result, "selected": mover.udid}


class SelectBody(BaseModel):
    udid: str


@app.post("/api/select")
async def select(body: SelectBody):
    async def go():
        if mover.udid != body.udid:
            await mover.reset()
        mover.udid = body.udid
        async with session.lock:
            await session.ensure(body.udid)

    resp = await run(go())
    if session.connected:
        payload = json.loads(resp.body)
        payload.update({"name": session.name, "version": session.version})
        return JSONResponse(payload, resp.status_code)
    return resp


@app.post("/api/reveal-developer-mode")
async def reveal(body: SelectBody):
    async def go():
        ld = await create_using_usbmux(serial=body.udid, autopair=True, pair_timeout=60)
        try:
            await AmfiService(ld).reveal_developer_mode_option_in_ui()
        finally:
            await ld.close()

    return await run(go())


class PointBody(BaseModel):
    lat: float
    lon: float
    label: Optional[str] = None


def remember_recent(p: PointBody) -> None:
    item = {"lat": round(p.lat, 6), "lon": round(p.lon, 6), "label": p.label or f"{p.lat:.5f}, {p.lon:.5f}"}
    data["recents"] = [item] + [r for r in data["recents"] if (r["lat"], r["lon"]) != (item["lat"], item["lon"])][:19]
    save_data(data)


@app.post("/api/teleport")
async def teleport(body: PointBody):
    resp = await run(mover.teleport(body.lat, body.lon))
    if resp.status_code == 200:
        remember_recent(body)
    return resp


class RouteBody(BaseModel):
    points: list[tuple[float, float]]
    speed: float = 1.4
    loop: bool = False


@app.post("/api/route")
async def route(body: RouteBody):
    return await run(mover.start_route([tuple(p) for p in body.points], body.speed, body.loop))


class JoyBody(BaseModel):
    active: bool
    heading: float = 0
    speed: float = 1.4


@app.post("/api/joystick")
async def joystick(body: JoyBody):
    return await run(mover.joystick(body.active, body.heading, body.speed))


class PauseBody(BaseModel):
    paused: bool


@app.post("/api/pause")
async def pause(body: PauseBody):
    mover.pause(body.paused)
    return {"ok": True, **mover.status()}


@app.post("/api/stop")
async def stop():
    return await run(mover.stop())


@app.post("/api/reset")
async def reset():
    return await run(mover.reset())


@app.get("/api/status")
async def status():
    return {
        **mover.status(),
        "device": {"udid": mover.udid, "name": session.name, "version": session.version, "connected": session.connected},
    }


@app.get("/api/places")
async def places():
    return {"favorites": data["favorites"], "recents": data["recents"]}


class FavBody(BaseModel):
    lat: float
    lon: float
    label: str


@app.post("/api/favorites")
async def add_fav(body: FavBody):
    data["favorites"] = [f for f in data["favorites"] if f["label"] != body.label] + [body.model_dump()]
    save_data(data)
    return {"ok": True, "favorites": data["favorites"]}


@app.delete("/api/favorites/{index}")
async def del_fav(index: int):
    if 0 <= index < len(data["favorites"]):
        data["favorites"].pop(index)
        save_data(data)
    return {"ok": True, "favorites": data["favorites"]}


@app.on_event("startup")
async def on_startup():
    app.state.keepalive = asyncio.create_task(mover.keepalive())


@app.on_event("shutdown")
async def on_shutdown():
    with contextlib.suppress(Exception):
        await mover.reset()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S")
    for noisy in ("pymobiledevice3", "uvicorn.access", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    print()
    print("  SHAMBLES is running.")
    print(f"  On this PC:      http://localhost:{PORT}")
    print(f"  On your phone:   http://{lan_ip()}:{PORT}/?t={data['token']}   (same Wi-Fi)")
    print("  Keep this window open while you use a fake location. Close it to go back to real GPS.")
    print()
    if "--no-browser" not in sys.argv:
        with contextlib.suppress(Exception):
            webbrowser.open(f"http://localhost:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
