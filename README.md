# Shambles

Change where your iPhone thinks it is. Two ways to use it:

| | PC helper (`pc/`) | iPhone app (`ios/`) |
|---|---|---|
| Needs a computer | Yes, the whole time | Only once, for setup |
| App installed on the iPhone | No | Yes (sideloaded) |
| Apple ID needed | No | Yes, to sign the app |
| Status | Working | In progress |

## PC helper (Windows)

What you need: a Windows PC with iTunes installed (for the iPhone drivers), a USB cable, and an iPhone.

1. Download this project (green **Code** button, then **Download ZIP**) and unzip it.
2. Open the `pc` folder and double-click **Start Shambles.bat**.
   The first run installs what it needs (a few minutes). If Python is missing it offers to install it.
3. A map opens in your browser. Plug in the iPhone, unlock it, and tap **Trust**.
4. If it says Developer Mode is off: on the iPhone go to Settings, Privacy & Security, Developer Mode,
   turn it on, and restart. Shambles makes that switch appear if it was hidden.
5. Tap the map or search for a place, then press **Teleport**.

Other things it does:

- **Move there**: travels from where you are to the pin along real roads, at walk, jog, bike or drive speed.
- **Joystick**: steer by hand.
- **Places**: favorites and recent spots.
- **Control from my phone**: shows a QR code. Scan it with any phone on the same Wi-Fi to use the map from
  that phone. If Windows Firewall asks, allow Python on private networks.
- **Real GPS**: turns the fake location off.

Good to know:

- The fake location only lasts while Shambles is running and the iPhone is connected to the PC.
  Close the black window or unplug the phone and it snaps back to the real location in a few seconds.
- Nothing is installed on the iPhone and no Apple ID or password is used.
- Apps and games can detect big jumps in location. Jumping across the world in one second is an easy way
  to get an account flagged.

## How it works

Both parts use Apple's own developer location simulation, the same feature Xcode uses to test apps.
The PC helper talks to it with [pymobiledevice3](https://github.com/doronz88/pymobiledevice3).
