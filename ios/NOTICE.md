# Shambles for iPhone

This folder is a modified copy of [StikDebug](https://github.com/StikDebug/StikDebug)
(commit `7a80dfce28eeb501faca6498d1746949ac921e74`), an on-device debugger for iOS by Stephen and contributors,
licensed under the GNU Affero General Public License v3.0. See `LICENSE`.

It talks to the iPhone through [idevice](https://github.com/jkcoxson/idevice) (MIT),
bundled as `StikDebug/idevice/libidevice_ffi.a`.

Changes made for Shambles:

- Renamed the app to Shambles, with its own icon and bundle identifier.
- The location map is the first tab. The JIT, scripts, app launcher and process tools are hidden.
- Added the `shambles://` URL scheme.

Everything in this folder stays under AGPL-3.0, including these changes.
