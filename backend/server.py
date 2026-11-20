"""
운명상점 (Fortune Shop) Full-Stack MVP
- FastAPI + Persistent DB (PostgreSQL via DATABASE_URL or SQLite fallback)
- Auth API: Google OAuth 2.0, Kakao OAuth 2.0, Email/Password Register & Login, Persistent Sessions
- Gemini API: All 7 Fortunes, Character Chat, Vision (Face + Palm), AI Future Spouse Portrait
"""
import os
import json
import hmac
import hashlib
import secrets
import sqlite3
import datetime
from urllib.parse import urlencode
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
import httpx

try:
    import psycopg2
    import psycopg2.extras
    HAS_PG = True
except Exception:
    HAS_PG = False

DB_PATH = os.path.join(os.path.dirname(__file__), "fortune_shop.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip().strip('"').strip("'")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
if DATABASE_URL and "sslmode=" not in DATABASE_URL and "localhost" not in DATABASE_URL and "127.0.0.1" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"
USE_PG = bool(DATABASE_URL and HAS_PG)
DB_ERROR = ""


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
KAKAO_CLIENT_ID = os.environ.get("KAKAO_CLIENT_ID", "").strip()
KAKAO_CLIENT_SECRET = os.environ.get("KAKAO_CLIENT_SECRET", "").strip()
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

app = FastAPI(title="운명상점 MVP API (Auth + DB + Gemini)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHARACTER_PROMPTS = {
    "saju": "당신은 동양풍 '운명상점'의 주인 '연화'입니다. 사주 명리 마스터로서 고풍스럽고 다정한 존댓말로 사주팔자·오행·신살(도화살·역마살·화개살·천을귀인 등)을 깊이 있고 따뜻하게 풀이해 주세요.",
    "blood": "당신은 발랄하고 장난기 많은 혈액형 궁합 마스터 '루미'입니다. 친근한 반말과 귀여운 이모티콘(♥, ~)을 섞어 두 사람의 혈액형 케미와 연애 꿀팁을 재밌게 알려주세요.",
    "zodiac": "당신은 반짝이는 별자리 천문 점성술사 '스텔라'입니다. 밝고 에너지 넘치는 말투로 별자리 운세와 성좌 궁합을 희망차게 들려주세요.",
    "tarot": "당신은 신비로운 타로 리더 '셀레네'입니다. 차분하고 몽환적인 존댓말로 선택된 3장의 타로 카드(과거·현재·미래)가 이어지는 운명의 서사를 깊이 있게 해석해 주세요.",
    "mbti": "당신은 따뜻한 MBTI 심리상담사 '하린'입니다. 공감 어린 다정한 말투로 두 사람의 성격 유형 궁합, 감정 소통법, 고민 해결 조언을 따뜻하게 전해 주세요.",
    "face": "당신은 예리하고 우아한 젊은 관상가 '아린'입니다. 얼굴을 보고 어떤 동물/귀인 관상인지 짚어주고, 이마(초년운), 눈썹·눈(중년운·인복), 코(재물운), 입·하관(말년운)과 잘 어울리는 미래 배우자의 인상을 품격 있고 긍정적으로 풀이해 주세요.",
    "palm": "당신은 신비로운 젊은 손금가 '서연'입니다. 손바닥의 생명선, 두뇌선, 감정선, 운명선을 다정하고 세밀하게 읽어 희망적인 조언을 건네주세요."
}

# ==================== UNIFIED DB LAYER (POSTGRESQL OR SQLITE) ====================
def _adapt_sql(sql: str) -> str:
    return sql.replace("?", "%s") if USE_PG else sql

def db_execute(sql: str, params: tuple = (), fetch: str = "none"):
    q = _adapt_sql(sql)
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=8, cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            with conn.cursor() as cur:
                cur.execute(q, params)
                res = None
                if fetch == "one":
                    row = cur.fetchone()
                    res = dict(row) if row else None
                elif fetch == "all":
                    res = [dict(r) for r in cur.fetchall()]
            conn.commit()
            return res
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(q, params)
            res = None
            if fetch == "one":
                row = cur.fetchone()
                res = dict(row) if row else None
            elif fetch == "all":
                res = [dict(r) for r in cur.fetchall()]
            conn.commit()
            return res
        finally:
            conn.close()

def init_db():
    pk = "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"
    stmts = [
        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            password_hash TEXT,
            created_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS fortune_history (
            id {pk},
            user_id TEXT,
            category TEXT NOT NULL,
            user_name TEXT,
            input_summary TEXT,
            result_summary TEXT,
            full_content TEXT,
            score INTEGER,
            created_at TEXT NOT NULL
        )""",
        f"""CREATE TABLE IF NOT EXISTS chat_logs (
            id {pk},
            user_id TEXT,
            character_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    ]
    for s in stmts:
        db_execute(s)
    # Safe column migration for existing SQLite DBs
    if not USE_PG:
        for tbl, col in [("fortune_history", "user_id TEXT"), ("fortune_history", "full_content TEXT"), ("chat_logs", "user_id TEXT")]:
            try:
                db_execute(f"ALTER TABLE {tbl} ADD COLUMN {col}")
            except Exception:
                pass

try:
    init_db()
except Exception as _pg_err:
    if USE_PG:
        DB_ERROR = str(_pg_err)
        print(f"[WARN] PostgreSQL init failed ({DB_ERROR}); falling back to SQLite so server stays online.")
        USE_PG = False
        init_db()
    else:
        raise

# ==================== PASSWORD & SESSION HELPERS ====================
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"{salt}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt, hex_dk = stored.split("$", 1)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return hmac.compare_digest(dk.hex(), hex_dk)

def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.datetime.now(datetime.timezone.utc)
    exp = now + datetime.timedelta(days=30)
    db_execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, user_id, now.isoformat(timespec="seconds"), exp.isoformat(timespec="seconds"))
    )
    return token

def upsert_social_user(user_id: str, provider: str, name: str, email: str = "") -> dict:
    existing = db_execute("SELECT id, provider, name, email FROM users WHERE id = ?", (user_id,), fetch="one")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if existing:
        db_execute("UPDATE users SET name = ?, email = ? WHERE id = ?", (name, email or existing.get("email") or "", user_id))
        return {"id": user_id, "provider": provider, "name": name, "email": email or existing.get("email") or ""}
    db_execute(
        "INSERT INTO users (id, provider, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, provider, name, email, "", now)
    )
    return {"id": user_id, "provider": provider, "name": name, "email": email}

def get_base_url(request: Request) -> str:
    if PUBLIC_BASE_URL:
        return PUBLIC_BASE_URL
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8000"))
    return f"{proto}://{host}"

# ==================== REQUEST MODELS ====================
class DemoAuthRequest(BaseModel):
    provider: str = "google"
    name: Optional[str] = ""

class EmailRegisterRequest(BaseModel):
    email: str
    password: str
    name: str

class EmailLoginRequest(BaseModel):
    email: str
    password: str

class HistoryRecord(BaseModel):
    user_id: Optional[str] = None
    category: str
    user_name: Optional[str] = "방문자"
    input_summary: str
    result_summary: str
    full_content: Optional[str] = ""
    score: Optional[int] = None

class FortuneRequest(BaseModel):
    user_id: Optional[str] = None
    character_id: str
    category: str
    user_name: Optional[str] = "방문자"
    details: str
    question: Optional[str] = ""

class ChatRequest(BaseModel):
    user_id: Optional[str] = None
    character_id: str
    message: str
    user_name: Optional[str] = "방문자"

class VisionRequest(BaseModel):
    user_id: Optional[str] = None
    character_id: str
    image_base64: str
    user_name: Optional[str] = "방문자"
    question: Optional[str] = ""
    spouse_gender: Optional[str] = "M"

class SpousePortraitRequest(BaseModel):
    prompt: str
    spouse_gender: Optional[str] = "M"

# ==================== GEMINI HELPER ====================
async def call_gemini(system_prompt: str, user_parts: list, max_tokens: int = 750):
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="서버에 GEMINI_API_KEY가 설정되지 않았습니다.")
    model_name = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": user_parts}],
        "generationConfig": {"temperature": 0.85, "maxOutputTokens": max_tokens}
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return "운명의 기운을 읽는 중 잠시 흐려졌습니다. 다시 한 번 시도해 주세요.", model_name
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip(), model_name

# ==================== HEALTH & AUTH ENDPOINTS ====================
@app.get("/api/health")
async def health():
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    return {
        "status": "ok",
        "db": "postgresql" if USE_PG else "sqlite",
        "db_error": DB_ERROR,
        "google_oauth_ready": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "kakao_oauth_ready": bool(KAKAO_CLIENT_ID),
        "gemini_ready": bool(api_key),
        "google_ready": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "kakao_ready": bool(KAKAO_CLIENT_ID),
        "model": os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    }

@app.get("/api/auth/config")
async def auth_config():
    return {
        "google_ready": bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET),
        "kakao_ready": bool(KAKAO_CLIENT_ID),
        "email_ready": True,
        "db": "postgresql" if USE_PG else "sqlite"
    }

@app.post("/api/auth/register")
async def auth_register(req: EmailRegisterRequest):
    email = req.email.strip().lower()
    name = req.name.strip() or email.split("@")[0]
    if "@" not in email or len(req.password) < 4:
        raise HTTPException(status_code=400, detail="올바른 이메일과 4자 이상의 비밀번호를 입력해 주세요.")
    exists = db_execute("SELECT id FROM users WHERE email = ?", (email,), fetch="one")
    if exists:
        raise HTTPException(status_code=409, detail="이미 가입된 이메일입니다. 로그인해 주세요.")
    user_id = f"email_{secrets.token_hex(8)}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    db_execute(
        "INSERT INTO users (id, provider, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, "email", name, email, hash_password(req.password), now)
    )
    token = create_session(user_id)
    return {"token": token, "user": {"id": user_id, "provider": "email", "name": name, "email": email}}

@app.post("/api/auth/login")
async def auth_login(req: EmailLoginRequest):
    email = req.email.strip().lower()
    row = db_execute("SELECT id, provider, name, email, password_hash FROM users WHERE email = ?", (email,), fetch="one")
    if not row or not verify_password(req.password, row.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    token = create_session(row["id"])
    return {"token": token, "user": {"id": row["id"], "provider": row["provider"], "name": row["name"], "email": row["email"]}}

@app.post("/api/auth/demo")
async def auth_demo(req: DemoAuthRequest):
    provider = req.provider if req.provider in ("google", "kakao") else "google"
    name = (req.name or "").strip() or ("카카오 여행자" if provider == "kakao" else "구글 여행자")
    user_id = f"{provider}_{hashlib.sha256(name.encode('utf-8')).hexdigest()[:12]}"
    user = upsert_social_user(user_id, provider, name, "")
    token = create_session(user_id)
    return {"token": token, "user": user}

@app.get("/api/auth/google")
async def auth_google_start(request: Request):
    if not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
        raise HTTPException(status_code=503, detail="GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET 환경변수가 필요합니다.")
    redirect_uri = f"{get_base_url(request)}/api/auth/google/callback"
    qs = urlencode({
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account"
    })
    return RedirectResponse(f"https://accounts.google.com/o/oauth2/v2/auth?{qs}")

@app.get("/api/auth/google/callback")
async def auth_google_callback(request: Request, code: str = ""):
    if not code:
        return RedirectResponse("/?auth_error=google_cancelled")
    redirect_uri = f"{get_base_url(request)}/api/auth/google/callback"
    async with httpx.AsyncClient(timeout=20.0) as client:
        tok_r = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        })
        tok_r.raise_for_status()
        access_token = tok_r.json().get("access_token")
        info_r = await client.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {access_token}"})
        info_r.raise_for_status()
        info = info_r.json()
    uid = f"google_{info.get('id', secrets.token_hex(6))}"
    name = info.get("name") or info.get("email", "구글 사용자").split("@")[0]
    email = info.get("email", "")
    upsert_social_user(uid, "google", name, email)
    token = create_session(uid)
    return RedirectResponse(f"/?auth_token={token}")

@app.get("/api/auth/kakao")
async def auth_kakao_start(request: Request):
    if not KAKAO_CLIENT_ID:
        raise HTTPException(status_code=503, detail="KAKAO_CLIENT_ID 환경변수가 필요합니다.")
    redirect_uri = f"{get_base_url(request)}/api/auth/kakao/callback"
    qs = urlencode({
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code"
    })
    return RedirectResponse(f"https://kauth.kakao.com/oauth/authorize?{qs}")

@app.get("/api/auth/kakao/callback")
async def auth_kakao_callback(request: Request, code: str = ""):
    if not code:
        return RedirectResponse("/?auth_error=kakao_cancelled")
    redirect_uri = f"{get_base_url(request)}/api/auth/kakao/callback"
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "code": code
    }
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET
    async with httpx.AsyncClient(timeout=20.0) as client:
        tok_r = await client.post("https://kauth.kakao.com/oauth/token", data=data)
        tok_r.raise_for_status()
        access_token = tok_r.json().get("access_token")
        info_r = await client.get("https://kapi.kakao.com/v2/user/me", headers={"Authorization": f"Bearer {access_token}"})
        info_r.raise_for_status()
        info = info_r.json()
    uid = f"kakao_{info.get('id', secrets.token_hex(6))}"
    acct = info.get("kakao_account") or {}
    prof = acct.get("profile") or {}
    name = prof.get("nickname") or "카카오 사용자"
    email = acct.get("email") or ""
    upsert_social_user(uid, "kakao", name, email)
    token = create_session(uid)
    return RedirectResponse(f"/?auth_token={token}")

@app.get("/api/auth/me")
async def auth_me(token: str = ""):
    if not token:
        raise HTTPException(status_code=401, detail="토큰이 없습니다.")
    sess = db_execute("SELECT user_id FROM sessions WHERE token = ?", (token,), fetch="one")
    if not sess:
        raise HTTPException(status_code=401, detail="유효하지 않은 세션입니다.")
    user = db_execute("SELECT id, provider, name, email FROM users WHERE id = ?", (sess["user_id"],), fetch="one")
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return {"user": user}

@app.post("/api/auth/logout")
async def auth_logout(token: str = ""):
    if token:
        db_execute("DELETE FROM sessions WHERE token = ?", (token,))
    return {"logged_out": True}

# ==================== FORTUNE / CHAT / VISION / HISTORY ENDPOINTS ====================
@app.post("/api/fortune")
async def generate_fortune(req: FortuneRequest):
    sys_prompt = CHARACTER_PROMPTS.get(req.character_id, CHARACTER_PROMPTS["saju"])
    sys_prompt += "\n답변은 모바일 화면에서 읽기 좋게 마크다운 기호 없이 깔끔한 문단으로 4~6문장 이내로 구체적이고 생생하게 한국어로 작성하세요."
    prompt = f"사용자 이름: {req.user_name}\n분야: {req.category}\n입력 정보: {req.details}"
    if req.question:
        prompt += f"\n사용자의 고민/질문: {req.question}"
    prompt += "\n위 정보를 바탕으로 캐릭터의 개성을 살려 맞춤형 운세/궁합 풀이와 실질적인 행운 조언을 들려주세요."

    reading, model_name = await call_gemini(sys_prompt, [{"text": prompt}], max_tokens=750)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    db_execute(
        "INSERT INTO fortune_history (user_id, category, user_name, input_summary, result_summary, full_content, score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (req.user_id, req.category, req.user_name, req.details[:120], reading[:180], reading, None, now)
    )
    return {"reading": reading, "model": model_name}

@app.post("/api/chat")
async def chat_with_character(req: ChatRequest):
    sys_prompt = CHARACTER_PROMPTS.get(req.character_id, CHARACTER_PROMPTS["saju"])
    sys_prompt += "\n답변은 모바일 대화창에 어울리게 2~4문장으로 자연스럽고 따뜻하게 한국어로 작성하세요."
    now = datetime.datetime.now().isoformat(timespec="seconds")
    db_execute("INSERT INTO chat_logs (user_id, character_id, role, content, created_at) VALUES (?, ?, 'user', ?, ?)", (req.user_id, req.character_id, req.message, now))
    if req.user_id:
        recent = db_execute("SELECT role, content FROM chat_logs WHERE character_id = ? AND user_id = ? ORDER BY id DESC LIMIT 6", (req.character_id, req.user_id), fetch="all")
    else:
        recent = db_execute("SELECT role, content FROM chat_logs WHERE character_id = ? ORDER BY id DESC LIMIT 6", (req.character_id,), fetch="all")
    history_text = "\n".join(f"{'사용자' if r['role']=='user' else '상담사'}: {r['content']}" for r in reversed(recent or []))
    reply, model_name = await call_gemini(sys_prompt, [{"text": f"사용자 이름: {req.user_name}\n\n[최근 대화]\n{history_text}"}], max_tokens=450)
    db_execute("INSERT INTO chat_logs (user_id, character_id, role, content, created_at) VALUES (?, ?, 'assistant', ?, ?)", (req.user_id, req.character_id, reply, datetime.datetime.now().isoformat(timespec="seconds")))
    return {"reply": reply, "model": model_name}

@app.post("/api/vision")
async def analyze_vision(req: VisionRequest):
    is_face = req.character_id == "face"
    sys_prompt = CHARACTER_PROMPTS["face" if is_face else "palm"]
    spouse_label = "남성" if (req.spouse_gender or "M").upper() == "M" else "여성"

    if is_face:
        prompt = (
            f"사용자 이름: {req.user_name}. 희망 미래 배우자 성별: {spouse_label}. "
            "이 얼굴 사진을 정밀하게 보고 아래 JSON 형식으로만 응답하세요(코드블록 없이 순수 JSON): "
            '{"face_type": "예: 귀인을 부르는 맑은 사슴상 (또는 봉황상/여우상/호랑이상/학상 등)", '
            '"analysis": "이마·눈매·코·하관 기반 초년·중년·말년 관상 풀이 (마크다운 없이 4~5문장)", '
            '"spouse_desc": "이 관상과 가장 잘 어우러지는 미래 ' + spouse_label + ' 배우자의 이목구비 인상, 성격, 만나는 인연 포인트 (2~3문장)", '
            '"spouse_prompt": "Photorealistic warm candid portrait photograph of a charming Korean ' + ("man" if spouse_label == "남성" else "woman") + ' in their late 20s matching the complementary physiognomy traits above, soft golden hour cafe lighting, natural gentle smile, 85mm lens"}'
        )
    else:
        prompt = (
            f"사용자 이름: {req.user_name}. "
            "이 손바닥 사진을 보고 손금(생명선·두뇌선·감정선·운명선과 앞으로의 재물·연애·건강 흐름)을 마크다운 없이 4~5문장으로 상세하고 희망적으로 풀이해 주세요."
        )
    if req.question:
        prompt += f" 추가 질문: {req.question}"

    mime = "image/jpeg"
    if req.image_base64.startswith("data:") and ";" in req.image_base64:
        mime = req.image_base64.split(";")[0].replace("data:", "")
    img_clean = req.image_base64.split(",")[-1]

    raw_text, model_name = await call_gemini(
        sys_prompt,
        [{"text": prompt}, {"inlineData": {"mimeType": mime, "data": img_clean}}],
        max_tokens=850
    )

    face_type = ""
    analysis = raw_text
    spouse_desc = ""
    spouse_prompt = ""
    if is_face:
        try:
            cleaned = raw_text.strip()
            if "{" in cleaned and "}" in cleaned:
                cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
            parsed = json.loads(cleaned)
            face_type = parsed.get("face_type", "귀인을 부르는 복상")
            analysis = parsed.get("analysis", raw_text)
            spouse_desc = parsed.get("spouse_desc", "")
            spouse_prompt = parsed.get("spouse_prompt", "")
        except Exception:
            face_type = "맑고 복된 귀인상"

    now = datetime.datetime.now().isoformat(timespec="seconds")
    full_txt = f"[{face_type}]\n{analysis}\n\n[미래 배우자] {spouse_desc}" if is_face else analysis
    db_execute(
        "INSERT INTO fortune_history (user_id, category, user_name, input_summary, result_summary, full_content, score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (req.user_id, "관상" if is_face else "손금", req.user_name, req.question or "사진 업로드 분석", analysis[:180], full_txt, 93, now)
    )
    return {
        "analysis": analysis,
        "face_type": face_type,
        "spouse_desc": spouse_desc,
        "spouse_prompt": spouse_prompt,
        "model": model_name
    }

@app.post("/api/spouse-portrait")
async def generate_spouse_portrait(req: SpousePortraitRequest):
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if not api_key:
        return {"generated": False, "reason": "no_api_key"}
    img_model = os.environ.get("GEMINI_IMAGE_MODEL", GEMINI_IMAGE_MODEL).strip()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{img_model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": req.prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(url, json=payload)
            if r.status_code == 200:
                data = r.json()
                parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                for part in parts:
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
                        return {"generated": True, "image_base64": f"data:{mime};base64,{inline['data']}", "model": img_model}
    except Exception:
        pass
    return {"generated": False, "reason": "image_model_unavailable"}

@app.post("/api/history")
def save_history(rec: HistoryRecord):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    db_execute(
        "INSERT INTO fortune_history (user_id, category, user_name, input_summary, result_summary, full_content, score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rec.user_id, rec.category, rec.user_name, rec.input_summary, rec.result_summary, rec.full_content or rec.result_summary, rec.score, now)
    )
    return {"saved": True, "created_at": now}

@app.get("/api/history")
def list_history(user_id: Optional[str] = None, limit: int = 30):
    if user_id:
        rows = db_execute(
            "SELECT id, user_id, category, user_name, input_summary, result_summary, full_content, score, created_at FROM fortune_history WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit), fetch="all"
        )
    else:
        rows = db_execute(
            "SELECT id, user_id, category, user_name, input_summary, result_summary, full_content, score, created_at FROM fortune_history ORDER BY id DESC LIMIT ?",
            (limit,), fetch="all"
        )
    return {"items": rows or []}

@app.get("/")
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "운명상점 MVP API 서버가 실행 중입니다."}
