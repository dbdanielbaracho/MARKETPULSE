# Locale-aware number and time formatting decision

Reviewed 2026-08-23 against W3C language-negotiation guidance and MDN ECMAScript Internationalization guidance.

Decision: **ADOPT** browser-standard `Intl` formatting, while keeping venue contract titles canonical.

PrediBeacon already negotiates the initial language from `Accept-Language`, persists an explicit manual override, and falls back to English. The remaining presentation gap on the market-detail page was hardcoded US number formatting and English-only compact/relative time strings.

The market page now derives formatting from the final document language (`document.documentElement.lang`) and uses:

- `Intl.NumberFormat` with ISO currency `USD` for reported USD volume;
- `Intl.RelativeTimeFormat` for time remaining and last-observed age;
- the existing canonical provider title unchanged, because translating a venue contract title could change its legal/economic meaning.

This deliberately does **not** infer a user's currency from their language or location. A USD-denominated venue volume remains USD and is only formatted according to the user's locale conventions. Currency conversion would create a separate financial-data requirement and is not silently performed.

Primary guidance reviewed:
- W3C, When to use language negotiation: https://www.w3.org/International/questions/qa-when-lang-neg
- W3C, Setting language preferences in a browser: https://www.w3.org/International/questions/qa-lang-priorities
- MDN, `Intl.NumberFormat`: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Intl/NumberFormat/NumberFormat
- MDN, JavaScript Internationalization: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Internationalization
