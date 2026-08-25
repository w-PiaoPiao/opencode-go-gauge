# GoGauge — OpenCode Go Usage Dashboard

<p align="center">
  <img src="assets/GoGauge.ico" width="64" alt="GoGauge">
</p>

<p align="center">
  <b>A local-first usage dashboard for OpenCode Go</b>: quota windows, token breakdown, model ranking and usage records — all in one place.
</p>

<p align="center">
  <a href="./README.md">🇨🇳 中文</a>
</p>

> 🔀 This repository is a fork of [yphyphyph/opencode-go-gauge](https://github.com/yphyphyph/opencode-go-gauge),
> adding **macOS** and **Android** support on top of the original Windows app.
> macOS / Android packages are published in this repo's [Releases](releases); the Windows installer is published by the upstream repo.

## 🗺 Platform Support

| Platform | Status | Installer | Docs |
|:---:|:---:|:---|:---|
| **Windows** | ✅ Released | [Upstream Releases](https://github.com/yphyphyph/opencode-go-gauge/releases): `GoGauge.exe` (single file, no install) | — |
| **macOS** | ✅ Released | [This repo's Releases](releases): arm64 / x86_64 packages (see the actual assets on the Releases page) | [docs/macos.md](docs/macos.md) |
| **Android** | ✅ Released | [This repo's Releases](releases): `GoGauge-v2.0.0-android.apk` (APK sideload) | [android/README.md](android/README.md) |

---

## 📸 Screenshots

| Home (Light) | Home (Dark) |
|:---:|:---:|
| ![Home Light](assets/screenshots/home-light.png) | ![Home Dark](assets/screenshots/home-dark.png) |

| Stats | Records |
|:---:|:---:|
| ![Stats](assets/screenshots/stats.png) | ![Records](assets/screenshots/records.png) |

| Settings | Login | About |
|:---:|:---:|:---:|
| ![Settings](assets/screenshots/settings.png) | ![Login](assets/screenshots/login.png) | ![About](assets/screenshots/about.png) |

---

## ✨ Features

- **Quota monitoring**: 5h rolling / weekly / monthly windows with progress bars, remaining % and reset countdown
- **Usage overview**: cache hit rate / hit amount / total tokens (incl. cache hits) / requests / cost / sessions
- **Today's trend**: 24-hour input / output bar chart
- **Usage stats**: token breakdown (input / output / reasoning / cache read / cache write / sessions), model usage donut + ranking, cost / requests / total tokens triple-line trend
- **Session history**: per-session aggregation of requests / input / output / reasoning / total tokens / cost, paginated
- **Usage records**: request-level detail with pagination and model filtering, incl. model / key-name columns
- **Multi-account support**: user management (add / switch / rename / remove / re-login), usage isolated per account, key-name column on records & sessions
- **Accounts overview panel**: toggle in settings, aggregates each account's quota windows and today's usage with cross-account summary KPIs and a 7-day cost trend comparison
- **Built-in WebView login**: independent login window opens the official auth page, auto-fills cookie & workspace — no manual copy-paste
- **Auto sync**: incremental sync (1/5/15/30 min) + sync range (30/60/90/180 days / All)
- **Dual themes**: light / dark toggle; bilingual UI (中文 / English)
- **System tray / menu bar**: closing the window minimizes to the system tray (Windows) or the menu bar (macOS); brand logo icons
- **macOS extras**: menu-bar quick panel for today's usage (30s refresh), semi-automatic updates, launch-at-login — see [docs/macos.md](docs/macos.md)
- **Local-first**: all data stays in local SQLite; credentials are only used to sync official APIs

## 🖥 Quick Start

### Windows

Download `GoGauge.exe` (single file, no install) from the **upstream Releases** in the [platform table](#-platform-support):

1. Double-click to run, click "Login Now" on the welcome page — an official auth window pops up
2. After login, the dashboard loads and usage data syncs automatically
3. Data is stored in the `data\` folder next to the exe

> Requires Windows 10/11 (WebView2 Runtime built-in). Closing the window minimizes to the system tray.
> The Windows installer is maintained and published by the upstream repo.

### macOS

Download the package for your architecture (arm64 / x86_64) from [Releases](releases), unzip and drag `GoGauge.app` into "Applications".

> See [docs/macos.md](docs/macos.md) for the menu-bar quick panel, launch-at-login, semi-automatic updates and the Gatekeeper workaround.

### Android

Download `GoGauge-v2.0.0-android.apk` from [Releases](releases) and allow "install unknown apps" to sideload it.

> The Android app is a native Kotlin + Jetpack Compose implementation with the same features as the desktop version —
> build, tech stack and platform differences are documented in [android/README.md](android/README.md).

### From Source

```bash
pip install -r requirements.txt
python entry.py
```

### Build

**Windows**

```bash
build.bat
```

Output: `dist\GoGauge.exe` (~38 MB, --noconsole, logo icon and tray support included).

**macOS**

```bash
./build_macos.sh
```

Output: `dist/GoGauge.app` (no console window; `.icns` icon and menu-bar tray support included).

> Requires macOS 11+ (built-in WebKit; pywebview uses WKWebView). Closing the window minimizes to the menu bar.
> Dual-arch builds, dependency locking and CI auto-build are detailed in [docs/macos.md](docs/macos.md).

## 📊 Data Notes

- **Source**: opencode.ai workspace usage API (`/_server` server-fn) + quota page HTML parsing
- **Total tokens** = input (incl. cache hits) + output + reasoning
- **Cache hit rate** = hits / (hits + misses)
- **Cost**: raw USD; CNY converted via open.er-api.com live FX rate (24h cache)

## 🔒 Privacy

- Login cookie stays on your machine only — never logged, never uploaded
- Usage data is stored entirely locally; the app contains no telemetry

## 🛠 Tech Stack

Python · pywebview (WebView2 / WKWebView) · SQLite · Chart.js · pystray

## 📬 Contact

- GitHub: [yphyphyph/opencode-go-gauge](https://github.com/yphyphyph/opencode-go-gauge)
- CSDN: [Ying_ph](https://blog.csdn.net/Ying_ph)

## 📄 License

[MIT](LICENSE) © GoGauge