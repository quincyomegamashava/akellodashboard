# USB Debug Testing Guide (Android + iOS)

This guide shows how to run and test the Akello Flutter app on physical Android and iOS devices over USB.

## 1) Prerequisites

- Flutter SDK installed and available on `PATH`
- Project dependencies available in this folder
- For Android:
  - Android Studio installed
  - Android SDK + Platform Tools installed (`adb`)
  - OEM USB driver installed on Windows (Samsung/Xiaomi/etc.) if needed
- For iOS:
  - macOS machine
  - Xcode installed
  - Xcode Command Line Tools installed
  - Apple Developer account/team configured for signing
- Reliable USB cable and unlocked device screen

## 2) Project Setup

From a terminal:

```bash
cd "C:\Users\quincy.mashava\Desktop\Akello\akellodashboard\mobile_app"
flutter pub get
flutter doctor -v
```

Resolve any issues shown by `flutter doctor -v` before continuing (especially Android toolchain, Xcode signing, and connected device detection).

## 3) Android USB Debug Setup

### A. Enable developer mode on phone

1. On Android phone: open **Settings > About phone**.
2. Tap **Build number** 7 times to enable Developer Options.
3. Open **Developer Options** and enable:
   - **USB debugging**
   - (Optional) **Stay awake** for testing convenience.

### B. Connect and authorize

1. Connect phone via USB.
2. If prompted on phone, tap **Allow USB debugging** and optionally **Always allow**.
3. On Windows, if device is not recognized, install OEM USB driver.

### C. Verify device detection

```bash
adb devices
flutter devices
```

- Device should appear as `device` (not `unauthorized` or `offline`).

### D. Run app on Android device

```bash
flutter run -d <android_device_id>
```

You can get `<android_device_id>` from `flutter devices`.

## 4) iOS USB Debug Setup

> iOS physical-device debugging must be done on macOS.

### A. Device trust and developer mode

1. Connect iPhone/iPad to Mac by USB.
2. On device, tap **Trust This Computer**.
3. On iOS 16+, enable **Developer Mode**:
   - **Settings > Privacy & Security > Developer Mode**
   - Restart device if prompted.

### B. Configure Xcode signing

1. Open:
   - `ios/Runner.xcworkspace` in Xcode
2. Select **Runner** target.
3. Go to **Signing & Capabilities**:
   - Set a valid **Team**
   - Ensure **Automatically manage signing** is enabled
   - Update Bundle Identifier if there is a conflict

### C. Verify device detection

```bash
flutter devices
```

### D. Run app on iOS device

```bash
flutter run -d <ios_device_id>
```

If prompted, approve certificates/profiles in Xcode and re-run.

## 5) Test Checklist (Both Platforms)

Use the live backend URL:

- `https://aidashboard.akello.co`

In the app login screen:

1. Confirm Base URL field is `https://aidashboard.akello.co`.
2. Sign in with valid credentials.
3. Validate tab navigation and rendering:
   - **Champions**
   - **Champion Requests**
   - **Administration**
   - **Profile**
4. Pull-to-refresh on list-based screens.
5. Confirm loading, empty, and error states appear appropriately.
6. Test request actions on Champion Requests:
   - Approve
   - Decline
7. Validate logout and login again.

## 6) Hot Reload and Debug Tips

When `flutter run` is active:

- Press `r` for hot reload
- Press `R` for hot restart
- Press `q` to quit

For verbose logs:

```bash
flutter run -v -d <device_id>
```

## 7) Common Issues and Fixes

### Device not listed in `flutter devices`

- Reconnect cable
- Use data-capable USB cable
- Unlock phone screen
- Re-run:
  - `adb devices` (Android)
  - `flutter doctor -v`

### Android device shows `unauthorized`

```bash
adb kill-server
adb start-server
adb devices
```

Then accept the USB debugging prompt on device.

### iOS signing/provisioning errors

- Re-open `ios/Runner.xcworkspace` in Xcode
- Confirm Team is selected
- Ensure unique Bundle Identifier
- Build once in Xcode to let signing assets generate

### API not reachable from physical device

- Confirm Base URL is exactly `https://aidashboard.akello.co`
- Verify internet access on device
- Check SSL date/time on device is correct

### Build cache issues

```bash
flutter clean
flutter pub get
flutter run -d <device_id>
```

## 8) Quick Command Reference

```bash
flutter pub get
flutter doctor -v
flutter devices
adb devices
flutter run -d <device_id>
flutter run -v -d <device_id>
```

