# GoGauge — AppGallery Listing Copy (English, ready to paste)

> For AppGallery / HarmonyOS Developer Center → App information / Version information.
> Bundle name: `io.github.yphyphyph.gogauge`　Version: 1.0.0 (versionCode 1000000)
> Character limits per Huawei docs (2026-10): one-line intro ≤17 characters for Chinese, ≤80 for other languages; app description ≤8,000 characters; what's new (mainland China) ≤500 characters.
> Source: <https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-app-intro-0000002313477961> (the actual AGC UI hints prevail)

---

## 1. Basic fields

| Field | Value | Notes |
| --- | --- | --- |
| App name (English) | `GoGauge` | Must match `app_name` in the package |
| App name (Chinese) | `GoGauge` | Same name |
| Default language | Simplified Chinese | Chosen when creating the app in AGC |
| One-line intro | `OpenCode Go usage dashboard` | **27 characters** (limit 80 for non-Chinese) |
| Category | App → Tools → Tools | Fixed after app creation |
| Tags | main: `Tools`; secondary: `AI` | Up to 5 tags; main tag tied to secondary category |
| Supported devices | Phone, Tablet, PC/2in1 | Must match `deviceTypes` in `module.json5` |
| Age rating | 3+ (per AGC questionnaire) | No ads, no IAP, no user-generated content |

**One-line intro alternatives (all ≤80 chars)**

| Copy | Chars | Note |
| --- | --- | --- |
| `OpenCode Go usage dashboard` | 27 | Recommended |
| `Quota, usage and records at a glance` | 37 | Benefit-oriented |
| `Track your OpenCode Go quota in one place` | 41 | Longer variant |

> Avoid superlatives, "free", "best", and words like "test/demo/beta" — the review checklist rejects such copy.

---

## 2. App description (≤8,000 characters)

> ~3,465 characters (limit 8,000); paste as-is into the "App description" field.

GoGauge is a usage dashboard for OpenCode Go. It puts quota windows, token composition, model spending and request records on one screen so you know exactly where your quota stands before it runs out.

**HIGHLIGHTS**
• Quota windows: used ratio, remaining quota and reset countdown for the rolling 5-hour, weekly and monthly windows.
• Usage overview: six KPIs — cache hit rate, cached tokens, total tokens (cached included), requests, cost (with average per request) and sessions — with a Today / Last 7 days / Last 30 days / Current cycle / All range switch.
• Today's trend: 24-hour input/output bar chart to spot usage peaks.
• Usage stats: token composition donut (input / output / reasoning / cache read / cache write / sessions), model usage donut and ranking (by input / output / cost, with request counts and hit rate) and 30-day cost / request / token trends.
• Daily heatmap: last 6 months of daily usage (switch between total tokens / requests / cost) with peak, current streak and longest streak.
• Model usage trend: 30-day stacked area chart comparing models at a glance.
• Usage records: session-grouped and request-level views with model filtering, pagination, key names and per-request cost.
• Multi-account: add, switch, rename, delete and re-login; usage data is isolated per account — handy for multiple workspaces or team accounts.
• Auto sync: foreground incremental sync at 1 / 5 / 15 / 30-minute intervals and background sync every 20 minutes; sync range of 30 / 60 / 90 / 180 days or all, plus a manual "Full sync now" action.
• Dual theme and bilingual UI: light / dark mode, Chinese / English UI and USD / CNY currency, switchable anytime.
• One app for every screen: phone, tablet and PC/2in1 layouts with bottom navigation on narrow screens and side navigation on wide screens.
• Local-first: all data stays in the app-private directory on your device. The login credential is stored only in the local database and used solely to call official opencode.ai APIs; nothing is uploaded to a developer server. No ads, no analytics SDK, no in-app purchases.

**HOW TO USE**
1. Open the app and tap "Sign in".
2. Complete sign-in on the opencode.ai console login page shown inside the app (you need your own OpenCode account with an OpenCode Go subscription).
3. The app stores the session credential and syncs your data automatically; return to Home to see it.
4. Adjust sync interval, sync range, language, theme and currency in Settings.

**SYSTEM REQUIREMENTS**
• HarmonyOS NEXT (HarmonyOS 6.1.1 / API 24 or later)
• Phone, tablet and PC/2in1 devices

**NOTES & DISCLAIMER**
• This is an unofficial third-party client. It is not affiliated with, endorsed by, or acting as an agent of OpenCode / OpenCode Go, and it does not provide account registration, top-ups, recharges or account sharing.
• Data comes from official opencode.ai console APIs and may be temporarily unavailable if those APIs change; the official website is authoritative.
• Cost figures are USD values returned by the API converted with a live FX rate, for reference only — not a billing statement.
• The app does not collect or upload user data to a developer server. See the privacy policy for details.
• Open source under the MIT license: https://github.com/w-PiaoPiao/opencode-go-gauge (upstream: https://github.com/yphyphyph/opencode-go-gauge)

**FEEDBACK**
Issues & suggestions: https://github.com/w-PiaoPiao/opencode-go-gauge/issues
Contact email: `<TBD: email>`

> Measured length: ~3,465 characters (limit 8,000).

---

## 3. What's new (1.0.0, ≤500 characters)

> Optional for the first release; this copy is ~150 characters.

First HarmonyOS NEXT release: quota windows, usage overview, today's trend, usage stats, usage records, multi-account, auto sync, dual theme and bilingual UI. All data stays on your device.

---

## 4. Do NOT claim these (not implemented in HarmonyOS 1.0.0)

- Command Code / GOAT provider (including `usage_charts` aggregation);
- Account overview panel (cross-account aggregated KPIs / 7-day trend comparison).

Source: `harmonyos/README.md` difference table and `harmonyos/docs/verification-summary.md` §1.1.
