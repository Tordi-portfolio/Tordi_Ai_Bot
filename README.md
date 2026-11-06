# Visa AI Assistant (Django)

Flow:
1. A client emails your company Gmail.
2. `python manage.py poll_emails --loop` reads the new email and the AI writes a reply (using YOUR company information).
3. The reply contains a link to the AI chat page.
4. The client chats with the AI. It scores the client from 0-10.
5. At score >= QUALIFY_SCORE (default 7) with a specific visa need, a "Continue on WhatsApp" button appears. It opens WhatsApp to your admin number with a pre-filled message, and you can see the full chat + summary in the admin.

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # then edit .env (see "Things you must edit")
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

In a second terminal (same venv):

```bash
python manage.py poll_emails --loop --interval 60
```

## Things you must edit

### 1. `.env` (everything lives here)
| Key | What to put |
|---|---|
| `COMPANY_NAME` | Your company name (shown in chat, emails, WhatsApp text) |
| `WHATSAPP_NUMBER` | Admin WhatsApp number, international format, digits only (e.g. `2348012345678`) |
| `GMAIL_ADDRESS` | The company Gmail address |
| `GMAIL_APP_PASSWORD` | 16-character Google App Password (steps below) |
| `GEMINI_API_KEY` | Free key from https://aistudio.google.com/apikey |
| `AI_MODEL` | Gemini model name. Pick the one with the best free quota in Google AI Studio (e.g. `gemini-2.5-flash`, `gemini-2.5-flash-lite`) |
| `SITE_URL` | Your PUBLIC https address. The chat link inside emails uses it. `localhost` only works on your own computer |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Your domain (e.g. `visa.example.com` and `https://visa.example.com`) |
| `DJANGO_SECRET_KEY` | Long random string. Set `DJANGO_DEBUG=False` in production |
| `ADMIN_NOTIFY_EMAIL` | Optional: get an email for every qualified client |
| `AUTO_SEND_REPLIES` | Start with `False` (drafts you approve), switch to `True` when happy |

### 2. Gmail App Password
Google Account > Security > turn on 2-Step Verification > App passwords > create one. Paste it into `GMAIL_APP_PASSWORD`. IMAP is on by default for Gmail accounts.

### 3. Company knowledge (the most important part)
Open `/admin/` > Knowledge entries and add entries: services, countries, visa types, requirements, documents, fees, processing times, office address, working hours, FAQs. The AI only states what is written here, so the more accurate this is, the better the replies. Edit it any time, no restart needed.

### 4. Optional code edits
- `assistant/ai.py`: the AI instructions (tone, length, what counts as a serious client, scoring rules).
- `assistant/templates/assistant/*.html`: look of the chat and home pages (CSS is embedded in each template).
- `assistant/emailer.py`: footer text of emails (`build_reply_text`).

## Using the admin
- Chat sessions: sorted by status and score, with name, destination, visa type, AI summary and the full conversation.
- Inbound emails: see every email, its status, and the reply. In draft mode, tick drafts > "Send selected drafts" (you can edit a draft first).
- Check "Opened WhatsApp" status to see who actually reached you.

## Going live
- Host it on a server with HTTPS (VPS, Render, Railway, etc.). Run `python manage.py collectstatic` and serve with `gunicorn visa_assistant.wsgi`.
- Keep `poll_emails --loop` running 24/7 (systemd service, supervisor, or a second worker process). Without it no emails are read.
- Use PostgreSQL instead of SQLite if you expect heavy traffic (change `DATABASES` in `settings.py`).

## Gemini free tier notes
- Every email reply = 1 request and every chat message = 1 request. A client who chats 8 times uses about 9 requests.
- When the daily/minute quota is used up, emails stay unread and are answered automatically on a later poll (quota resets at midnight Pacific time). The chat shows "very busy, try again in a minute".
- Free-tier prompts may be used by Google to improve its products, so avoid putting passport numbers or other sensitive documents into your knowledge entries, and consider a paid key before handling real client data at scale.

## Safety built in
- Skips no-reply, bulk, mailing-list and auto-generated emails, and limits replies per sender per day (stops email loops).
- Each email is answered once (tracked by Message-ID); failed AI calls retry up to 3 times.
- The AI is told not to guarantee approval or invent fees/times, and to ignore instructions hidden in emails or chat.
- Chat has a message limit per session.

## Tests
`python manage.py test`
"# Tordi_Ai_Bot" 
