# Shambles: build notes / handoff

Goal: a Vanish-style GPS changer for iPhone (iOS 26.x), owner on a Windows PC.

## Status (2026-11-13)
- **PC helper** (`pc/`): complete, tested only against a mocked device. `shambles.py` (FastAPI, pymobiledevice3 11.55.0
  pinned), `web/index.html` (Leaflet, vendored), `Start Shambles.bat`. Also pushes an iloader-exported pairing file
  into the iPhone app's Documents (`/api/place-pairing`).
- **iPhone app** (`ios/`): modified copy of StikDebug (AGPL-3.0, see `ios/NOTICE.md`). Xcode target and scheme are
  still named `StikDebug`; only display name, bundle id (`com.ashvikt.shambles`), icon, tabs and a few strings changed.
  Uses the Xcode 27 JSON project format, so CI runs on the `xcode-27` runner.
  `.github/workflows/build-ios.yml` builds an unsigned IPA and republishes it as release tag `latest`.
  First build passed. Not yet installed on a real phone.
- **Not done / ideas**: joystick in the phone app, a SideStore source JSON for one-tap install and updates,
  packaging the PC helper as a single .exe.

## Owner setup status
- iTunes + iloader installed on the Windows PC. SideStore not yet installed. iPhone on iOS 26.x.
