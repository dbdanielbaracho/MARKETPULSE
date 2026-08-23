# Telegram distribution decision

Reviewed 2026-08-23 against the current official Telegram Bot API documentation (Bot API 10.2, updated July 14, 2026).

Decision: **ADOPT the Telegram Bot API with a fail-closed server-side adapter**.

Why this is the best fit for PrediBeacon:

- Telegram's official Bot API is an HTTPS server API designed for automated bot/channel messaging.
- `sendMessage` is sufficient for the first distribution integration and returns a durable provider message identifier on success.
- PrediBeacon can keep the bot token server-side and does not need to expose it to browsers.
- The existing global social kill switch, explicit platform authorization, editorial approval, country policy and commercial-contract gates remain authoritative before any provider call.

Implementation rules:

- Require both `MP_TELEGRAM_BOT_TOKEN` and an explicit `MP_TELEGRAM_CHAT_ID`; having a token alone is not considered configured.
- Allow only 1–4096 characters, matching the official text-message limit.
- Use `https://api.telegram.org/bot<token>/sendMessage` only.
- Use bounded timeouts and at most three attempts. Retry network/timeouts, HTTP 429 and 5xx only; do not retry arbitrary 4xx mistakes.
- Never return or log the bot token from the adapter.
- No live post is attempted until owner-controlled bot credentials, destination and `MP_TELEGRAM_AUTHORIZED=true` exist.

Primary source reviewed:
- Telegram Bot API: https://core.telegram.org/bots/api

External activation still required:
1. Create/authorize the PrediBeacon bot through Telegram's supported setup flow.
2. Add the bot to the intended channel/chat with the required permissions.
3. Set the production bot token and destination ID as Railway secrets.
4. Explicitly set `MP_TELEGRAM_AUTHORIZED=true` only after that authorization is verified.
