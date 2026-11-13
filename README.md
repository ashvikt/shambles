# Shambles

Change where your iPhone thinks it is. Two ways to use it:

| | PC helper (`pc/`) | iPhone app (`ios/`) |
|---|---|---|
| Needs a computer | Yes, the whole time | Only once, for setup |
| App installed on the iPhone | No | Yes (sideloaded) |
| Apple ID needed | No | Yes, to sign the app |
| Status | Built, needs real-phone testing | Built, needs real-phone testing |

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

- You need the PC to set or change the fake location. On some iPhones (seen on iOS 26) the last spot
  stays in place after unplugging. To get the real location back, plug in and press Real GPS, or
  restart the iPhone.
- Nothing is installed on the iPhone and no Apple ID or password is used.
- Apps and games can detect big jumps in location. Jumping across the world in one second is an easy way
  to get an account flagged.

## iPhone app

Works without the PC after a one-time setup. Needs iOS 17.4 or newer.

Download: [Shambles.ipa](https://github.com/ashvikt/shambles/releases/download/latest/Shambles.ipa)
(rebuilt automatically every time the code in `ios/` changes).

One-time setup, with the iPhone plugged into the PC:

1. On the iPhone, install **LocalDevVPN** from the App Store, open it, and tap Connect.
   It is not a real VPN. It lets the phone talk to its own developer service.
2. On the PC, open **iloader**, sign in with an Apple ID, and install **SideStore**.
3. On the iPhone, turn on **Developer Mode** (Settings, Privacy & Security, Developer Mode), restart,
   then trust your Apple ID under Settings, General, VPN & Device Management.
4. Install the app: open the download link above in Safari on the iPhone, then in SideStore go to
   My Apps, tap +, and pick `Shambles.ipa`.
5. Give the app its pairing file: in iloader choose Manage Pairing File, then Export, and save the file.
   Then run the PC helper, click the iPhone button, and choose **Send pairing file to the app**.
   (Or move the file to the phone yourself and use Settings, Import Pairing File inside Shambles.)
6. Open Shambles on the iPhone with LocalDevVPN connected and Wi-Fi on. When it says connected,
   tap the map and start the simulation. After that it keeps working away from the PC.

Good to know:

- With a free Apple ID the app expires every 7 days. SideStore renews it by itself as long as
  LocalDevVPN is connected now and then.
- A big iOS update or a passcode change can break the pairing file. Redo step 5 if the app stops connecting.
- Restarting the iPhone always brings back the real location.

The iPhone app is a modified copy of [StikDebug](https://github.com/StikDebug/StikDebug) and is licensed
under AGPL-3.0. See `ios/NOTICE.md`.

## How it works

Both parts use Apple's own developer location simulation, the same feature Xcode uses to test apps.
The PC helper talks to it with [pymobiledevice3](https://github.com/doronz88/pymobiledevice3).
