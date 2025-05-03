# EchoMind Backend – Render Deployment Guide

## ✅ Requirements
- GitHub repo with all backend files pushed
- Python 3.11+
- `requirements.txt` or `pyproject.toml`

## ✅ Suggested Repo Structure
```
/echomind/
├── app/
│   ├── main.py
│   ├── models.py
│   ├── database.py
│   ├── get_api_key.py
│   └── routes/
├── alembic/
├── alembic.ini
├── .env.production
├── requirements.txt
└── seed.py
```

## ✅ Render Deployment Steps

1. **Push your repo to GitHub**

2. **Create a new Render Web Service:**
- Runtime: Python
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port 10000`

3. **Add Environment Variables**
Upload contents of `.env.production` or paste manually:
```
DATABASE_URL=...
ECHO_API_KEY=...
...
```

4. **Deploy**
Click “Create Web Service.” Wait for it to boot.

5. **Test it**
Visit `https://your-service-url.onrender.com` and hit `/session/ping` with API key.

---

## ✅ Route Index
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/log-session` | POST | Save agent session log |
| `/log-summary` | POST | Save emotional insight or reflection |
| `/log-milestone` | POST | Save parenting or growth milestones |
| `/get-memory` | POST | Retrieve agent memory snapshot |
| `/get-shared-summary` | GET | Retrieve global summary |
| `/capsule/preview` | GET | Pull 5 latest insights |
| `/admin/stats` | GET | Show total system counts |
| `/flag-queue` | GET | Placeholder moderation view |

---

## ✅ Local Dev (Before Deploying)
```
uvicorn app.main:app --reload
```

Test endpoints locally at `http://localhost:8000`
