# Telegram Music Bot — Render

## Render settings

**Language/Runtime:** Python

**Build Command**
```bash
pip install -r requirements.txt
```

**Start Command**
```bash
uvicorn app:app --host 0.0.0.0 --port $PORT
```

## Environment Variables

Add:

- `BOT_TOKEN` = توکن ربات تلگرام
- `WEBHOOK_URL` = آدرس وبهوک، مثلاً:
  `https://YOUR-SERVICE.onrender.com/telegram/webhook`

بعد از Deploy، صفحه اصلی باید JSON مشابه زیر بدهد:
```json
{"ok":true,"service":"music-bot"}
```

و:
`/webhook-info`
باید آدرس webhook را نشان دهد.

## دستورات ربات

- `/start`
- `/help`
- `/search نام آهنگ`
- `/archive`
- `/add عنوان | خواننده | لینک مستقیم MP3`

نکته: برای جستجوی آنلاین باید یک API مجاز و سازگار با فرمت زیر تنظیم شود:
```json
{
  "results": [
    {
      "title": "Song",
      "artist": "Artist",
      "audio_url": "https://example.com/song.mp3",
      "source_url": "https://example.com"
    }
  ]
}
```

این پروژه دانلودر سایت‌های غیرمجاز یا دور زدن محدودیت کپی‌رایت نیست؛ فقط لینک مستقیم فایل صوتی‌ای را که مجاز به استفاده از آن هستید دریافت می‌کند.

### نکته درباره SQLite در Render Free
SQLite روی دیسک سرویس ذخیره می‌شود و در سرویس‌های بدون دیسک پایدار ممکن است با redeploy/restart از بین برود. برای آرشیو دائمی، بعداً PostgreSQL اضافه کنید.
