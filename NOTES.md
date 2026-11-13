# Shambles: build notes / handoff

Goal: a Vanish-style GPS changer for iPhone (iOS 26.x), owner on a Windows PC.

## Two parts
1. **PC helper** (`pc/`): Python + pymobiledevice3 (v11.55). No app on the phone, no Apple ID.
   Phone needs: Trust this PC + Developer Mode. Uses the no-admin userspace RSD tunnel
   (`UserspaceRsdTunnel`) -> `auto_mount(rsd)` -> `DvtProvider` -> `LocationSimulation`.
   iOS 17+ resets the location when the DVT channel closes, so the process must stay running.
   Serves a map UI (FastAPI) on port 8765; phones on the same Wi-Fi use `/?t=<token>`.
   - DONE: `pc/shambles.py` (device session, teleport, route-follow, joystick, favorites/recents, token auth).
   - TODO: `pc/web/index.html` (Leaflet map, Nominatim search, OSRM routes, joystick, QR for phone URL),
     `pc/web/manifest.webmanifest`, `pc/web/icon.svg`, `pc/requirements.txt` (pymobiledevice3),
     `pc/Start Shambles.bat` (find Python, make .venv, pip install, run), README.
2. **iPhone app** (`ios/`): works without the PC after one-time setup.
   Pairing file (from iloader / idevice_pair) + LocalDevVPN loopback tunnel + idevice FFI
   (MIT, jkcoxson/idevice) for RSD tunnel, DDI mount, DVT location simulation. SwiftUI + MapKit.
   Built unsigned by GitHub Actions (macos runner), installed with SideStore.
   Prior art: StikDebug, RouteSim (github.com/DasVR/RouteSim), Locus.
   - TODO: everything.

## Owner setup status
- iTunes + iloader installed on PC. SideStore not yet installed. LocalDevVPN status unknown.
- Developer Mode toggle not visible yet (appears after sideloading or via AMFI reveal).
