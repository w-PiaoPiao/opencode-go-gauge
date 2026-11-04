# GoGauge Privacy Policy (English)

> Applies to: GoGauge for HarmonyOS NEXT 1.0.0 (`versionCode` 1000000, bundle name `io.github.yphyphyph.gogauge`)
> Effective date: `2026-11-04`
> Last updated: `2026-11-04`
>
> ⚠️ The developer name below **must exactly match** the real-name entity of the Huawei developer account (AppGallery review rule 7.1). Current value: Wang Yizhi (王逸之).
>
> This policy mirrors the actual behavior of the code. Source files: `common/auth/Login.ets`, `common/store/AppPrefs.ets`, `data/db/AppDb.ets`, `data/repository/DashboardRepository.ets`, `data/remote/{OpenCodeApi,ExchangeApi,UpdateApi}.ets`, `entry/src/main/module.json5`.


> 📌 In-app version: the text shown on the in-app `pages/PrivacyPage` comes from `common/legal/PrivacyText.ets` (a summarized/equivalent version of this policy). **Before submitting, verify paragraph by paragraph that the in-app text matches both this document and the hosted privacy-policy URL submitted to AGC** (review rule 7.1).

---

## Introduction

GoGauge ("the App") is an **OpenCode Go usage dashboard** for HarmonyOS NEXT developed by **Wang Yizhi (王逸之)** ("we", "us"). It lets you view the quota windows, usage statistics and request records of your own OpenCode account.

**The App has no backend server. We do not collect, receive or upload any personal data or usage data.** All data stays on your device. The App is an **unofficial third-party client** and is not affiliated with, endorsed by, or acting as an agent of OpenCode / OpenCode Go.

## 1. Information we process (locally only)

The App processes the following data **on your device only**, strictly to provide its features. We (the developer) never receive it.

| Data | Content | Storage | Purpose | Uploaded to developer? |
| --- | --- | --- | --- | --- |
| Login credential | Session cookie captured from opencode.ai after you sign in in the in-app WebView (currently `__Host-console_session=…`; legacy `auth=…` also supported) | App-private database, `accounts.token` | Authenticate requests to opencode.ai on your behalf, read your own account data | No |
| Usage data | Request logs (time, model, input/output/reasoning/cached tokens, cost, session/key identifiers), quota windows, sync state, key-name cache | App-private database (4 RDB tables) | Render Home / Stats / Records | No |
| Preferences | Language (zh/en), dark mode, currency (USD/CNY) | App-private preferences | Remember display settings | No |
| Workspace identifier | Your opencode.ai workspace ID / hint | App-private database | Fetch data for the right workspace | No |

**We do NOT collect** contacts, SMS, call logs, location, photos, camera, microphone, clipboard, device identifiers (IMEI/OAID/MAC, etc.), installed-app lists, browsing/search history, advertising IDs or biometric data. We do not build user profiles or provide personalized recommendations.

> Note on credential storage: the session cookie is stored in the app-private system database (security level S2) protected by the HarmonyOS app sandbox. The App does not apply additional custom encryption to it. Please avoid using the App on rooted or untrusted devices.

## 2. Network requests and third-party services

The App connects **directly** to the following third-party services. Requests originate from your device (not from a developer server) and include network-layer information such as your IP address, which is processed by each provider under its own privacy policy.

1. **opencode.ai (https://opencode.ai)** — required
   - Login page `https://opencode.ai/console/login` loaded in the in-app WebView; the sign-in itself is handled by opencode.ai.
   - APIs: `/console/api/go/status` (quota), `/request-logs` (usage), `/orgs` (workspaces), `/service-accounts` (key names).
   - Requests carry your session cookie **only** to read your own account data. No other personal data is sent.
   - The App clears WebView cookies right after a successful login, and again on logout.

2. **open.er-api.com (https://open.er-api.com/v6/latest/USD)** — optional currency conversion.
   - A plain GET request (cached for 6 hours) with only `User-Agent: GoGauge/1.0`. **No cookie, account or usage data is sent.**

3. **GitHub (api.github.com / github.com)** — only when you tap "Check for updates" in Settings.
   - Fetches the Releases list/feed of `w-PiaoPiao/opencode-go-gauge`. **No cookie, account or usage data is sent.**

**There is no third-party analytics, advertising or push SDK.** The only third-party dependency is the HarmonyOS unit-test framework `@ohos/hypium`, which is used at development time and is not shipped inside the published app.

## 3. Device permissions

| Permission | Type | Purpose |
| --- | --- | --- |
| `ohos.permission.INTERNET` | normal (granted at install) | Access opencode.ai for your quota/usage data; optional exchange-rate API; GitHub only when you check for updates |

The App does **not** request or use location, camera, microphone, contacts, photos, calendar, sensors, clipboard, notifications or any sensitive/restricted permission, and does not read device identifiers.

## 4. Storage and retention

- **Location:** on your HarmonyOS device only, in the app-private sandbox (`/data/app/el2/…/io.github.yphyphyph.gogauge`). We have no server.
- **Retention:** until you delete the data or uninstall the App. There is no automatic expiry; you can delete records older than the configured sync range via Settings → "Purge by sync range".
- **Cross-border transfer:** we do not transfer your personal data. However, your device connects directly to opencode.ai, open.er-api.com and GitHub, which may be located outside your country/region; network requests (including IP address) are handled by those providers.

## 5. How we protect your data

- App data lives inside the HarmonyOS app sandbox, unreadable by other apps;
- The session cookie is stored only in the app-private database — never uploaded, never logged, never written to the clipboard;
- Release builds contain no debug tools or debug logging UI;
- All network traffic uses HTTPS.

No internet transmission is completely secure. Please protect your opencode.ai account and revoke sessions on opencode.ai if you suspect misuse.

## 6. Sharing, transfer and disclosure

We do not sell, share or publicly disclose your personal data. Apart from the direct third-party connections described above, the App performs no data sharing. We have no server, so no server-side data transfer scenario currently exists.

## 7. Your rights

You have full control over the data stored on your device:

1. **Access** — view local usage data and account info on Home / Stats / Records / Settings;
2. **Rectify** — rename accounts or sign in again in Settings → Accounts;
3. **Delete** —
   - **Log out**: clears the current account's credential, its local usage data and sync state, and clears WebView cookies;
   - **Delete account**: removes the account entry and all its local usage data (irreversible);
   - **Purge by sync range**: deletes local records older than the selected range across all accounts;
   - **Uninstall**: removes all data stored by the App;
4. **Withdraw consent** — via the deletion paths above or by uninstalling; withdrawal does not affect prior local processing;
5. **Complaints** — contact us via the details below; we reply within 15 business days.

> The App has no developer-side account system, so there is no "developer account" to cancel. Your opencode.ai account is managed by OpenCode; delete it on opencode.ai.

## 8. Children

The App is a developer-oriented usage viewer and is not directed at children; we do not knowingly collect children's personal data. If you are under 14, please use the App under guardian supervision. Guardians may contact us to request deletion of locally processed children's data.

## 9. Changes to this policy

We may update this policy when features or regulations change. Updates will be announced in-app or via AppGallery release notes; material changes (e.g. new data collection) will require your consent again. The latest version is always available in-app / at the published URL.

## 10. Contact us

- Developer/operator: Wang Yizhi (王逸之)
- Contact: GitHub Issues (https://github.com/w-PiaoPiao/opencode-go-gauge/issues , reply within 15 business days)
- Open-source repository (issues): https://github.com/w-PiaoPiao/opencode-go-gauge/issues
- Upstream project: https://github.com/yphyphyph/opencode-go-gauge

We respond within 15 business days.

---

### Appendix: data deletion quick reference

| Data to delete | Path |
| --- | --- |
| Current account credential + its local usage | Settings → Accounts → current account "Log out" |
| One account's local data (including the entry) | Settings → Accounts → "Delete" (double confirmation) |
| Records older than the sync range (all accounts) | Settings → Sync → "Purge by sync range" (double confirmation) |
| Everything | Uninstall the App (or system Settings → Apps → GoGauge → Storage → Clear data) |
