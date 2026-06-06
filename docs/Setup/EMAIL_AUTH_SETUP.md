# Email verification & password reset

## Backend endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/forgot-password` | No | Sends reset email if account has a password |
| POST | `/auth/reset-password` | No | Body: `{ "token", "password" }` |
| GET | `/auth/reset-password/form?token=` | No | Browser form to set a new password |
| POST | `/auth/verify-email` | No | Body: `{ "token" }` (app / API) |
| GET | `/auth/verify-email/confirm?token=` | No | Browser link from verification email |
| POST | `/auth/resend-verification` | Bearer | Resend verification for password accounts |

Registration creates `email_verified=false` and sends a verification email. Google sign-in marks the email verified automatically.

## Environment variables

```bash
# Required (existing)
JWT_SECRET=...

# Public URL used in email links (use your machine IP for physical devices)
APP_PUBLIC_URL=http://10.0.2.2:8000

# SMTP (optional — without these, links are logged to the API console)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-user
SMTP_PASSWORD=your-password
SMTP_FROM=noreply@yourdomain.com
SMTP_USE_TLS=true
```

Run migrations:

```bash
cd backend && alembic upgrade head
```

## Mobile deep links

Emails include app links:

- `aireminder://verify-email?token=...`
- `aireminder://reset-password?token=...`

Android and iOS are configured for the `aireminder` URL scheme.

## Testing without SMTP

1. Register a new email/password account.
2. In the API logs, find `event=email_dev` with the verification URL.
3. Open the URL in a browser or paste the token into the app reset flow.

Forgot password uses the same logging when SMTP is unset.
