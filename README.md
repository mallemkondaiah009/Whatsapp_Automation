# WhatsApp Automation (Playwright)

A Python script that drives WhatsApp Web with Playwright to send text messages
and images/documents (with captions) to a list of contacts from a CSV file.

> **Important:** This automates WhatsApp Web outside WhatsApp's official
> Business API. That's against WhatsApp's Terms of Service, and accounts doing
> bulk/automated sends — even with randomized delays — can get flagged or
> banned. Only use this on a small, consented contact list (people who've
> agreed to receive messages from you). For anything at scale, use the
> official WhatsApp Cloud API instead.

## Requirements

```bash
pip install playwright pillow
playwright install chromium
```

## Files

- `main.py` — the automation script
- `numbers.csv` — your contact list and message content (you create this)
- `whatsapp_profile/` — created automatically; stores your logged-in session
  so you don't have to scan the QR code every run

## numbers.csv format

```csv
phone,message,file_path
918008332745,Hi there!,C:\Users\you\Documents\Whatsapp_Automation\files\download.jpg
919999999999,Just a text message,
```

- `phone` — number with country code, no `+` or spaces (e.g. `91XXXXXXXXXX`)
- `message` — text to send. If `file_path` is also set, this becomes the
  **caption** on the image/document (sent as one combined bubble, not two
  separate messages)
- `file_path` — absolute path to an image, video, or document to send. Leave
  blank to send text only

## Running it

```bash
python main.py
```

**First run:** a Chromium window opens to WhatsApp Web. Scan the QR code with
your phone, then press Enter in the terminal to continue. Your session is
saved in `whatsapp_profile/`.

**Later runs:** if a valid session already exists in `whatsapp_profile/`, the
script detects it and skips the QR wait automatically. If the session expired
(logged out, too much time passed, etc.), it'll fall back to asking you to
scan again.

The script then works through `numbers.csv` top to bottom, opening each
contact's chat, sending the text or file+caption, and waiting a short random
delay before moving to the next one.

## How chat-opening works

For each number, the script tries two ways to open the conversation:

1. **In-app search** (fast, no page reload) — works only if you've already
   messaged that number before, since it just looks up an existing chat
   thread.
2. **Deep-link reload** (`web.whatsapp.com/send?phone=...`) — the fallback,
   used automatically when search doesn't find an existing thread. Required
   for messaging a number for the first time.

If search selectors ever stop matching (WhatsApp changes its DOM structure
periodically), the script just falls through to the reload method — so
sending still works, just slower for repeat contacts.

## Debug screenshots

The script saves screenshots automatically when things go wrong, so you can
see exactly what WhatsApp Web looked like at the point of failure:

- `debug_timeout_<phone>.png` — chat never finished loading
- `debug_no_preview.png` — media attach flow didn't show the expected caption
  box
- `debug_after_send.png` — state right after clicking send
- `error_<phone>.png` — saved whenever a contact's send throws an exception

If a send fails or behaves oddly, check the matching screenshot first — it's
usually the fastest way to tell what changed.

## Known fragile points

WhatsApp Web's front-end changes fairly often, which can break CSS selectors
over time. If sends start failing after previously working:

- Right-click → **Inspect** on the relevant element in the actual browser
  window Playwright opens (search box, send button, caption box, etc.)
- Compare its `aria-label`, `data-testid`, or `role` attributes against what
  the script is looking for
- Update the corresponding selector in `main.py`

`data-testid` attributes tend to be the most stable across WhatsApp's UI
updates; raw CSS class names (the long `x1a2b3c...` strings) change often and
should be avoided as selectors.

## Tuning speed vs. safety

- `time.sleep(random.uniform(3, 6))` between contacts — the main lever for
  speed. Lower it and sends go faster, but higher send velocity is one of the
  stronger signals WhatsApp uses to detect automated/bulk accounts. Don't drop
  this much below a few seconds for anything beyond a handful of contacts.
- Various `wait_for(..., timeout=...)` calls — these block until an element
  is actually ready rather than guessing with a fixed sleep, so they're
  generally safe to leave as-is.