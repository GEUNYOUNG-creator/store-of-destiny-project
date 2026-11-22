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
from fastapi.responses import FileResponse, RedirectResponse, Response
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
    "saju": (
        "당신은 운명상점의 주인이자 정통 명리학 마스터 '연화'입니다. 맑고 또렷한 젊은 여성 명리학자 말투로, "
        "사주팔자(년·월·일·시주), 오행 균형, 일간 성향은 물론 도화살·역마살·화개살·천을귀인·현침살·백호대살·괴강살·홍염살·귀문관살·원진살·천덕귀인·문창귀인·양인살 등 "
        "한국 정통 사주 사전의 다양한 신살과 길신을 깊이 있게 풀이해 줍니다."
    ),
    "blood": (
        "당신은 통통 튀고 발랄한 혈액형 궁합 마스터 '루미'입니다. 밝고 경쾌한 에너지로 "
        "연애 성향, 감정 표현 방식, 갈등 해결법, 찰떡 궁합 포인트를 구체적인 일상 예시와 함께 풍성하게 들려줍니다."
    ),
    "zodiac": (
        "당신은 맑고 신비로운 별자리 천문 점성술사 '스텔라'입니다. 또렷하고 생기 있는 톤으로 "
        "행성 배치, 원소 에너지, 연애·재물·인간관계의 흐름과 오늘의 행운 포인트를 깊이 있게 설명합니다."
    ),
    "tarot": (
        "당신은 섬세하고 직관적인 타로 리더 '셀레네'입니다. 맑고 또렷한 어조로 "
        "카드의 상징, 정방향/역방향 에너지, 현재 상황의 숨은 원인, 앞으로의 전개와 행동 가이드를 문단별로 깊이 있게 리딩합니다."
    ),
    "mbti": (
        "당신은 똑 부러지고 친근한 MBTI 심리상담사 '하린'입니다. 명쾌하고 생동감 있는 젊은 톤으로 "
        "인지기능(주기능·부기능), 연애 및 인간관계 패턴, 스트레스 해소법, 찰떡 파트너십 전략을 구체적으로 설명합니다."
    ),
    "face": (
        "당신은 청동거울을 든 영리한 관상가 '아린'입니다. 맑고 또렷한 어조로 "
        "이마(초년운)·눈과 눈썹(대인/애정운)·코(재물운)·입과 하관(말년운)을 입체적으로 풀이하고, 어울리는 미래 배우자 인상까지 상세히 알려줍니다."
    ),
    "palm": (
        "당신은 황금 돋보기를 든 통찰력 있는 손금가 '서연'입니다. 경쾌하고 명쾌한 어조로 "
        "생명선·두뇌선·감정선·운명선·재물선·결혼선의 흐름과 앞으로의 전환점을 알기 쉽게 상세히 풀이합니다."
    ),
    "sasang": (
        "당신은 운명상점의 8번째 마스터이자 사상의학(四象醫學) 한의사 '다온'입니다. 옥빛 약병과 사상체질 두루마리를 들고, "
        "밝고 명쾌하며 생기 있는 젊은 한의사 말투로 이제마 선생의 동의수세보원 사상의학(태양인·태음인·소양인·소음인)에 따라 "
        "체형·골격·장부 대소·기질·맞춤 식단·운동·건강 관리법을 아주 상세하고 친절하게 풀이해 줍니다."
    ),
    "dream": (
        "당신은 운명상점의 9번째 마스터이자 신비로운 꿈 해몽가 '몽화'입니다. 달빛 드림캐처 등불과 꿈 구슬을 들고, "
        "맑고 또렷하며 따뜻한 젊은 여성 해몽가 말투로 한국 전통 해몽 사전의 길몽·흉몽·태몽·횡재수 해석과 현대 무의식 심리학을 결합해 "
        "사용자가 꾼 꿈 속 상징물, 감정, 전개 흐름을 깊이 있고 생생하게 풀이해 줍니다."
    ),
}

RICH_FORMAT_GUIDE = (
    "\n\n[출력 형식 필수 규칙 — 가독성 최우선]\n"
    "1. 절대로 짧게 요약하지 말고, 최소 4~5개의 뚜렷한 소제목 문단으로 깊이 있고 풍성하게 작성하세요.\n"
    "2. 각 소제목은 반드시 `[소제목]` 형태로 줄의 맨 앞에 쓰고, 소제목 아래에 2~4문장의 충분한 설명을 문단으로 작성하세요.\n"
    "3. 각 문단에서 가장 중요한 핵심 키워드, 신살 이름, 체질 포인트, 행운 조언은 반드시 `**강조 텍스트**` 형태로 감싸서 눈에 띄게 표시하세요.\n"
    "4. 문단과 문단 사이는 반드시 빈 줄(\n\n)로 띄워 모바일 화면에서도 한눈에 시원하게 읽히도록 구성하세요.\n"
    "5. 캐릭터의 개성 있는 톤을 유지하되, 실제 도움이 되는 구체적인 분석과 현실 조언을 빠짐없이 담아주세요."
)

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
    sys_prompt = CHARACTER_PROMPTS.get(req.character_id, CHARACTER_PROMPTS["saju"]) + RICH_FORMAT_GUIDE

    extra_guide = ""
    if req.character_id == "saju":
        extra_guide = (
            "\n\n[사주 심층 풀이 필수 포함 항목]\n"
            "- [타고난 일간과 오행 기운 분석]: 일간의 본질과 강한 오행/부족한 오행이 성격과 인생 흐름에 미치는 영향\n"
            "- [핵심 신살(神殺) 및 길신 심층 해석]: 전달된 사주 정보에 포함된 신살·길신(도화살, 역마살, 화개살, 현침살, 백호대살, 괴강살, 홍염살, 귀문관살, 원진살, 천을귀인, 천덕귀인, 문창귀인, 양인살 등) 각각의 뜻과 현대적 활용법\n"
            "- [재물운 · 직업 적성 · 연애/인연운]: 타고난 강점을 살릴 분야와 재물·인연이 열리는 타이밍\n"
            "- [맞춤 개운법과 주의 포인트]: 부족한 오행을 채우는 색·습관·행동 지침"
        )
    elif req.character_id == "dream":
        extra_guide = (
            "\n\n[꿈 해몽 심층 풀이 필수 포함 항목]\n"
            "- [꿈의 핵심 상징과 길몽·흉몽 판별]: 꿈에 등장한 주요 인물·동물·사물·배경이 전통 해몽에서 뜻하는 의미와 길몽/흉몽/예지몽 여부\n"
            "- [무의식 심리 & 현재 내 마음 상태 해석]: 이 꿈이 반영하는 현재의 바람, 긴장, 혹은 내면의 변화 신호\n"
            "- [재물운 · 연애운 · 대인운 예지 포인트]: 꿈의 기운이 앞으로의 재물·직업·연애·인간관계에 가져올 구체적 흐름\n"
            "- [몽화의 현실 개운 조언 & 행운 숫자]: 길몽의 복을 키우거나 흉몽의 불안을 잠재우는 실천 팁과 추천 행운 숫자 3개"
        )
    elif req.character_id == "sasang":
        extra_guide = (
            "\n\n[사상의학 심층 풀이 필수 포함 항목]\n"
            "- [체질 핵심 진단과 장부(臟腑) 특성]: 해당 체질(태양인/태음인/소양인/소음인)의 타고난 장부 대소와 에너지 순환 원리\n"
            "- [신체·외형 특징 상세 분석]: 상체·하체 비율, 목덜미/허리/가슴/엉덩이 발달 특징, 얼굴 인상 및 체력 패턴\n"
            "- [기질·성격 및 대인관계 강점]: 감정 흐름과 일·연애에서의 매력 포인트\n"
            "- [맞춤 식단 · 추천 운동 · 건강 주의점]: 이로운 음식, 피해야 할 음식, 땀 관리 및 계절별 양생법"
        )

    prompt = f"사용자 이름: {req.user_name}\n상담 분야: {req.category}\n상세 입력 정보:\n{req.details}"
    if req.question:
        prompt += f"\n사용자 질문: {req.question}"
    prompt += extra_guide + "\n\n위 정보를 바탕으로 캐릭터의 개성을 살려 깊이 있고 가독성 높은 맞춤형 풀이를 들려주세요."

    reading, model_name = await call_gemini(sys_prompt, [{"text": prompt}], max_tokens=1850)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    db_execute(
        "INSERT INTO fortune_history (user_id, category, user_name, input_summary, result_summary, full_content, score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (req.user_id, req.category, req.user_name, req.details[:120], reading[:180], reading, None, now)
    )
    return {"reading": reading, "model": model_name}

@app.post("/api/chat")
async def chat_with_character(req: ChatRequest):
    sys_prompt = CHARACTER_PROMPTS.get(req.character_id, CHARACTER_PROMPTS["saju"])
    sys_prompt += "\n답변은 모바일 대화창에 어울리게 3~5문장으로 친근하고 명쾌하게 작성하며, 핵심 포인트 1~2곳은 **강조**로 표시하세요."
    now = datetime.datetime.now().isoformat(timespec="seconds")
    db_execute("INSERT INTO chat_logs (user_id, character_id, role, content, created_at) VALUES (?, ?, 'user', ?, ?)", (req.user_id, req.character_id, req.message, now))
    if req.user_id:
        recent = db_execute("SELECT role, content FROM chat_logs WHERE character_id = ? AND user_id = ? ORDER BY id DESC LIMIT 6", (req.character_id, req.user_id), fetch="all")
    else:
        recent = db_execute("SELECT role, content FROM chat_logs WHERE character_id = ? ORDER BY id DESC LIMIT 6", (req.character_id,), fetch="all")
    history_text = "\n".join(f"{'사용자' if r['role']=='user' else '상담사'}: {r['content']}" for r in reversed(recent or []))
    reply, model_name = await call_gemini(sys_prompt, [{"text": f"사용자 이름: {req.user_name}\n\n[최근 대화]\n{history_text}"}], max_tokens=600)
    db_execute("INSERT INTO chat_logs (user_id, character_id, role, content, created_at) VALUES (?, ?, 'assistant', ?, ?)", (req.user_id, req.character_id, reply, datetime.datetime.now().isoformat(timespec="seconds")))
    return {"reply": reply, "model": model_name}

@app.post("/api/vision")
async def analyze_vision(req: VisionRequest):
    char_id = req.character_id if req.character_id in ("face", "palm", "sasang") else "palm"
    sys_prompt = CHARACTER_PROMPTS[char_id]
    spouse_label = "남성" if (req.spouse_gender or "M").upper() == "M" else "여성"

    if char_id == "face":
        prompt = (
            f"사용자 이름: {req.user_name}. 희망 미래 배우자 성별: {spouse_label}. "
            "이 얼굴 사진을 정밀하게 보고 사진 속 인물의 실제 특징에 맞춰 아래 순수 JSON으로만 응답하세요(코드블록 금지): "
            '{"face_type": "예: 귀인을 부르는 맑은 사슴상 / 카리스마 여우상 / 듬직한 호랑이상 / 우아한 봉황상 / 친화력 강아지상 중 가장 어울리는 표현", '
            '"score": 76부터 98 사이의 정수, '
            '"spouse_archetype": 0(온화·감성형), 1(세련·도시 카리스마형), 2(밝고 다정한 강아지상), 3(지적·듬직한 신뢰형) 중 숫자(0~3), '
            '"analysis": "[초년운 · 이마와 눈썹]\n...\n\n[중년운 · 눈매와 코의 재물 기운]\n...\n\n[말년운 · 하관과 대인복]\n...\n\n[맞춤 개운 포인트]\n... 형식으로 4문단 이상 상세히 작성하고 핵심어는 **강조**로 표시", '
            '"spouse_desc": "이 관상과 가장 잘 어우러지는 미래 ' + spouse_label + ' 배우자의 이목구비 인상, 성격, 만나는 인연 포인트 (3~4문장, 핵심어는 **강조** 표시)", '
            '"spouse_prompt": "Photorealistic warm candid portrait photograph of a charming Korean ' + ("man" if spouse_label == "남성" else "woman") + ' in their late 20s matching the complementary physiognomy traits above, soft natural lighting, 85mm lens"}'
        )
    elif char_id == "sasang":
        prompt = (
            f"사용자 이름: {req.user_name}. "
            "이 전신 사진을 동의수세보원 사상의학(태양인·태음인·소양인·소음인) 체형 관점에서 정밀하게 관찰하여 아래 순수 JSON으로만 응답하세요(코드블록 금지): "
            '{"sasang_key": "taeyang" 또는 "taeeum" 또는 "soyang" 또는 "soeum" 중 가장 부합하는 1개, '
            '"sasang_type": "태양인(太陽人)" 또는 "태음인(太陰人)" 또는 "소양인(少陽人)" 또는 "소음인(少陰人)" 중 1개, '
            '"score": 78부터 98 사이의 체질 일치도 정수, '
            '"body_features": "전신 사진에서 관찰된 상체·어깨·가슴·허리·골반·하체 비율 및 전체 실루엣 특징을 3~4문장으로 상세히 설명(핵심어는 **강조**)", '
            '"analysis": "[전신 체형 및 사상체질 판별 근거]\n...\n\n[타고난 신체적·해부학적 특징]\n...\n\n[기질과 에너지 순환 성향]\n...\n\n[맞춤 식습관·운동·건강 관리법]\n... 형식으로 4문단 이상 아주 상세히 작성하고 핵심어는 **강조**로 표시", '
            '"health_diet": "이 체질에 이로운 음식, 피해야 할 음식, 추천 운동 루틴을 구체적으로 정리 (3~4문장, 핵심어는 **강조**)"}'
        )
    else:
        prompt = (
            f"사용자 이름: {req.user_name}. "
            "이 손바닥 사진을 정밀하게 보고 사진 속 손금 선의 실제 특징에 맞춰 아래 순수 JSON으로만 응답하세요(코드블록 금지): "
            '{"palm_type": "예: 재물과 귀인이 모이는 황금 운명선형 / 창의적 예술가 두뇌선형 / 활력 넘치는 대길 생명선형 등", '
            '"score": 76부터 98 사이의 정수, '
            '"analysis": "[생명선 · 타고난 체력과 활력]\n...\n\n[두뇌선 · 사고력과 직업 적성]\n...\n\n[감정선 · 연애와 인연의 결]\n...\n\n[운명선과 재물 흐름 · 개운 조언]\n... 형식으로 4문단 이상 상세히 작성하고 핵심어는 **강조**로 표시"}'
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
        max_tokens=1500
    )

    img_hash = sum(ord(c) for c in img_clean[:400:7]) if img_clean else 17
    face_type = ""
    palm_type = ""
    sasang_key = ""
    sasang_type = ""
    body_features = ""
    health_diet = ""
    analysis = raw_text
    spouse_desc = ""
    spouse_prompt = ""
    score = 80 + (img_hash % 17)
    spouse_archetype = img_hash % 4

    sasang_keys = ["taeyang", "taeeum", "soyang", "soeum"]
    sasang_labels = {
        "taeyang": "태양인(太陽人)",
        "taeeum": "태음인(太陰人)",
        "soyang": "소양인(少陽人)",
        "soeum": "소음인(少陰人)",
    }

    try:
        cleaned = raw_text.strip()
        if "{" in cleaned and "}" in cleaned:
            cleaned = cleaned[cleaned.find("{"):cleaned.rfind("}") + 1]
        parsed = json.loads(cleaned)
        if char_id == "face":
            face_type = parsed.get("face_type", "맑고 복된 귀인상")
            analysis = parsed.get("analysis", raw_text)
            spouse_desc = parsed.get("spouse_desc", "")
            spouse_prompt = parsed.get("spouse_prompt", "")
            if isinstance(parsed.get("spouse_archetype"), int):
                spouse_archetype = max(0, min(3, parsed["spouse_archetype"]))
        elif char_id == "sasang":
            sk = str(parsed.get("sasang_key", "")).strip().lower()
            if sk not in sasang_labels:
                st = str(parsed.get("sasang_type", ""))
                if "태양" in st: sk = "taeyang"
                elif "태음" in st: sk = "taeeum"
                elif "소양" in st: sk = "soyang"
                elif "소음" in st: sk = "soeum"
                else: sk = sasang_keys[img_hash % 4]
            sasang_key = sk
            sasang_type = parsed.get("sasang_type") or sasang_labels[sk]
            body_features = parsed.get("body_features", "")
            health_diet = parsed.get("health_diet", "")
            analysis = parsed.get("analysis", raw_text)
        else:
            palm_type = parsed.get("palm_type", "균형 잡힌 황금 운명선형")
            analysis = parsed.get("analysis", raw_text)
        if isinstance(parsed.get("score"), (int, float)):
            score = max(72, min(99, int(parsed["score"])))
    except Exception:
        if char_id == "face":
            face_type = "맑고 복된 귀인상"
        elif char_id == "sasang":
            sasang_key = sasang_keys[img_hash % 4]
            sasang_type = sasang_labels[sasang_key]
        else:
            palm_type = "균형 잡힌 황금 운명선형"

    now = datetime.datetime.now().isoformat(timespec="seconds")
    if char_id == "face":
        cat_label = "관상"
        full_txt = f"[{face_type}] ({score}점)\n{analysis}\n\n[미래 배우자] {spouse_desc}"
    elif char_id == "sasang":
        cat_label = "사상의학"
        full_txt = f"[{sasang_type}] (체질 일치도 {score}%)\n{body_features}\n\n{analysis}\n\n[맞춤 양생법] {health_diet}"
    else:
        cat_label = "손금"
        full_txt = f"[{palm_type}] ({score}점)\n{analysis}"

    db_execute(
        "INSERT INTO fortune_history (user_id, category, user_name, input_summary, result_summary, full_content, score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (req.user_id, cat_label, req.user_name, req.question or "사진 업로드 분석", analysis[:180], full_txt, score, now)
    )
    return {
        "analysis": analysis,
        "face_type": face_type,
        "palm_type": palm_type,
        "sasang_key": sasang_key,
        "sasang_type": sasang_type,
        "body_features": body_features,
        "health_diet": health_diet,
        "score": score,
        "spouse_archetype": spouse_archetype,
        "spouse_desc": spouse_desc,
        "spouse_prompt": spouse_prompt,
        "model": model_name
    }

@app.post("/api/spouse-portrait")
async def generate_spouse_portrait(req: SpousePortraitRequest):
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if not api_key:
        return {"generated": False, "reason": "no_api_key"}
    candidates_models = [
        os.environ.get("GEMINI_IMAGE_MODEL", GEMINI_IMAGE_MODEL).strip(),
        "gemini-2.5-flash-image",
        "gemini-2.0-flash-exp-image-generation"
    ]
    tried = set()
    async with httpx.AsyncClient(timeout=40.0) as client:
        for img_model in candidates_models:
            if not img_model or img_model in tried:
                continue
            tried.add(img_model)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{img_model}:generateContent?key={api_key}"
            payload = {
                "contents": [{"role": "user", "parts": [{"text": req.prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]}
            }
            try:
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
                continue
    return {"generated": False, "reason": "image_model_unavailable"}


# ==================== NEURAL KOREAN VOICE TTS (/api/tts) ====================
class TTSRequest(BaseModel):
    character_id: str = "saju"
    text: str
    is_mini: Optional[bool] = False

# 8인 전원 어리고 늘어지지 않는 자연스러운 한국어 뉴럴 여성 보이스 (Microsoft Neural)
TTS_VOICE_MAP = {
    "saju":   {"voice": "ko-KR-SunHiNeural",    "rate": "+5%",  "pitch": "+3Hz"},   # 연화: 맑고 또렷한 명리 톤
    "blood":  {"voice": "ko-KR-SeoHyeonNeural", "rate": "+10%", "pitch": "+6Hz"},   # 루미: 발랄 통통 튀는 기준 톤
    "zodiac": {"voice": "ko-KR-YuJinNeural",    "rate": "+6%",  "pitch": "+5Hz"},   # 스텔라: 청아한 별빛 소녀 톤
    "tarot":  {"voice": "ko-KR-YuJinNeural",    "rate": "+3%",  "pitch": "-1Hz"},   # 셀레네: 영롱하고 맑은 신비 톤
    "mbti":   {"voice": "ko-KR-JiMinNeural",    "rate": "+11%", "pitch": "+4Hz"},   # 하린: 똑 부러진 하이텐션 톤
    "face":   {"voice": "ko-KR-JiMinNeural",    "rate": "+6%",  "pitch": "+1Hz"},   # 아린: 영리하고 상큼한 명랑 톤
    "palm":   {"voice": "ko-KR-SeoHyeonNeural", "rate": "+8%",  "pitch": "+2Hz"},   # 서연: 시원시원 경쾌한 톤
    "sasang": {"voice": "ko-KR-SunHiNeural",    "rate": "+8%",  "pitch": "+7Hz"},   # 다온: 싱그럽고 명쾌한 한의 톤
}
_TTS_CACHE = {}

@app.post("/api/tts")
async def synthesize_character_tts(req: TTSRequest):
    text = (req.text or "").strip()[:360]
    if not text:
        raise HTTPException(status_code=400, detail="텍스트가 비어 있습니다.")
    cfg = TTS_VOICE_MAP.get(req.character_id, TTS_VOICE_MAP["blood"])
    voice = cfg["voice"]
    rate = cfg["rate"]
    pitch = cfg["pitch"]
    if req.is_mini:
        # 미니 펫 모드: 좀 더 귀엽고 경쾌하게
        base_hz = int(pitch.replace("Hz", "").replace("+", ""))
        base_rate = int(rate.replace("%", "").replace("+", ""))
        pitch = f"{base_hz + 7:+d}Hz"
        rate = f"{min(20, base_rate + 5):+d}%"

    cache_key = (voice, rate, pitch, text)
    if cache_key in _TTS_CACHE:
        return Response(content=_TTS_CACHE[cache_key], media_type="audio/mpeg")

    try:
        import edge_tts
        communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        audio_bytes = b"".join(chunks)
        if not audio_bytes:
            raise RuntimeError("Empty TTS audio")
        if len(_TTS_CACHE) > 160:
            _TTS_CACHE.clear()
        _TTS_CACHE[cache_key] = audio_bytes
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Neural TTS unavailable: {e}")

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

@app.get("/manifest.json")
def serve_manifest():
    p = os.path.join(os.path.dirname(__file__), "..", "manifest.json")
    return FileResponse(p, media_type="application/manifest+json")

@app.get("/sw.js")
def serve_sw():
    p = os.path.join(os.path.dirname(__file__), "..", "sw.js")
    return FileResponse(p, media_type="application/javascript")

@app.get("/icon-192.png")
def serve_icon192():
    p = os.path.join(os.path.dirname(__file__), "..", "icon-192.png")
    return FileResponse(p, media_type="image/png")

@app.get("/icon-512.png")
def serve_icon512():
    p = os.path.join(os.path.dirname(__file__), "..", "icon-512.png")
    return FileResponse(p, media_type="image/png")

@app.get("/og-preview.jpg")
def serve_og():
    p = os.path.join(os.path.dirname(__file__), "..", "og-preview.jpg")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/src/assets/voices/{filename}")
def serve_character_voice(filename: str):
    safe = os.path.basename(filename)
    p = os.path.join(os.path.dirname(__file__), "..", "src", "assets", "voices", safe)
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="Voice file not found")
    return FileResponse(p, media_type="audio/mpeg")

@app.get("/opening.mp4")
def serve_opening_video():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "opening.mp4"), media_type="video/mp4")
