# Google Sign-In Setup

Google sign-in uses **Firebase Auth** on the mobile app and **Firebase Admin** on the API to verify ID tokens, then issues your app’s normal JWT access/refresh tokens.

## 1. Firebase Console

1. Open [Firebase Console](https://console.firebase.google.com/) → your project.
2. **Authentication** → **Sign-in method** → enable **Google**.
3. **Project settings** → **Your apps**:
   - **Android**: add package name `com.nouman.aireminder` and **SHA-1** (debug + release).
   - **iOS**: add bundle ID and download `GoogleService-Info.plist` into `mobile_app/ios/Runner/`.
   - **Web** (required for Android ID token): note the **Web client ID**  
     (`xxxx.apps.googleusercontent.com`).

4. Download `google-services.json` → `mobile_app/android/app/google-services.json`.

## 2. Backend

Set in `backend/.env`:

```env
FIREBASE_CREDENTIALS_PATH=/absolute/path/to/firebase-service-account.json
JWT_SECRET=your-secret-min-16-chars
```

Run migration:

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

Restart the API after changes.

## 3. Flutter — Web client ID (Android)

Android needs the **Web OAuth client ID** so Google returns an ID token Firebase can verify.

Create `mobile_app/.env` (copy from `mobile_app/.env.example`):

```env
GOOGLE_WEB_CLIENT_ID=YOUR_WEB_CLIENT_ID.apps.googleusercontent.com
```

Then run:

```bash
cd mobile_app
flutter pub get
flutter run
```

Optional: `--dart-define=GOOGLE_WEB_CLIENT_ID=...` overrides `.env`.

## 4. iOS URL scheme

Open `GoogleService-Info.plist` and copy `REVERSED_CLIENT_ID`.

In `mobile_app/ios/Runner/Info.plist`, add (replace with your value):

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleTypeRole</key>
    <string>Editor</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>com.googleusercontent.apps.YOUR_CLIENT_NUMBER</string>
    </array>
  </dict>
</array>
```

## 5. Verify end-to-end

1. Start API with `FIREBASE_CREDENTIALS_PATH` set.
2. Run app with `GOOGLE_WEB_CLIENT_ID` on Android (or iOS simulator with plist + URL scheme).
3. Tap **Continue with Google** on the login screen.
4. Backend logs: `event=google_auth_registered` or `event=google_auth_login`.

## API

`POST /auth/google`

```json
{ "id_token": "<Firebase ID token from mobile>" }
```

Response: same as email login (`access_token`, `refresh_token`).

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| `GOOGLE_WEB_CLIENT_ID` error on Android | Pass `--dart-define=GOOGLE_WEB_CLIENT_ID=...` |
| `Google sign-in is not configured on the server` | Set `FIREBASE_CREDENTIALS_PATH` and restart API |
| `Invalid or expired Google token` | SHA-1 mismatch, wrong Firebase project, or stale token |
| `This account uses Google sign-in` | User registered with Google; use Google button |
| iOS returns immediately / fails | Add `REVERSED_CLIENT_ID` URL scheme to Info.plist |
