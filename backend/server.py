"""
운명상점 (Fortune Shop) MVP — FastAPI + SQLite DB + Google Gemini API (All 7 Fortunes + Chat + Vision + AI Spouse Portrait)
"""
import os
import json
import sqlite3
import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx

DB_PATH = os.path.join(os.path.dirname(__file__), "fortune_shop.db")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
DEFAULT_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_IMAGE_MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

app = FastAPI(title="운명상점 MVP API (Gemini + SQLite)")

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

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS fortune_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            user_name TEXT,
            input_summary TEXT,
            result_summary TEXT,
            score INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS chat_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            character_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()

init_db()

class HistoryRecord(BaseModel):
    category: str
    user_name: Optional[str] = "방문자"
    input_summary: str
    result_summary: str
    score: Optional[int] = None

class FortuneRequest(BaseModel):
    character_id: str
    category: str
    user_name: Optional[str] = "방문자"
    details: str
    question: Optional[str] = ""

class ChatRequest(BaseModel):
    character_id: str
    message: str
    user_name: Optional[str] = "방문자"

class VisionRequest(BaseModel):
    character_id: str
    image_base64: str
    user_name: Optional[str] = "방문자"
    question: Optional[str] = ""
    spouse_gender: Optional[str] = "M"

class SpousePortraitRequest(BaseModel):
    prompt: str
    spouse_gender: Optional[str] = "M"

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

@app.get("/api/health")
async def health():
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    return {
        "status": "ok",
        "db": "sqlite",
        "gemini_ready": bool(api_key),
        "model": os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    }

@app.post("/api/fortune")
async def generate_fortune(req: FortuneRequest):
    sys_prompt = CHARACTER_PROMPTS.get(req.character_id, CHARACTER_PROMPTS["saju"])
    sys_prompt += "\n답변은 모바일 화면에서 읽기 좋게 마크다운 기호 없이 깔끔한 문단으로 4~6문장 이내로 구체적이고 생생하게 한국어로 작성하세요."
    prompt = f"사용자 이름: {req.user_name}\n분야: {req.category}\n입력 정보: {req.details}"
    if req.question:
        prompt += f"\n사용자의 고민/질문: {req.question}"
    prompt += "\n위 정보를 바탕으로 캐릭터의 개성을 살려 맞춤형 운세/궁합 풀이와 실질적인 행운 조언을 들려주세요."

    reading, model_name = await call_gemini(sys_prompt, [{"text": prompt}], max_tokens=750)

    conn = get_db()
    conn.execute(
        "INSERT INTO fortune_history (category, user_name, input_summary, result_summary, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (req.category, req.user_name, req.details[:100], reading[:180], None, datetime.datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()
    return {"reading": reading, "model": model_name}

@app.post("/api/chat")
async def chat_with_character(req: ChatRequest):
    sys_prompt = CHARACTER_PROMPTS.get(req.character_id, CHARACTER_PROMPTS["saju"])
    sys_prompt += "\n답변은 모바일 대화창에 어울리게 2~4문장으로 자연스럽고 따뜻하게 한국어로 작성하세요."

    conn = get_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute("INSERT INTO chat_logs (character_id, role, content, created_at) VALUES (?, 'user', ?, ?)", (req.character_id, req.message, now))
    recent = conn.execute("SELECT role, content FROM chat_logs WHERE character_id = ? ORDER BY id DESC LIMIT 6", (req.character_id,)).fetchall()
    conn.commit()

    history_text = "\n".join(f"{'사용자' if r['role']=='user' else '상담사'}: {r['content']}" for r in reversed(recent))
    reply, model_name = await call_gemini(sys_prompt, [{"text": f"사용자 이름: {req.user_name}\n\n[최근 대화]\n{history_text}"}], max_tokens=450)

    conn.execute("INSERT INTO chat_logs (character_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)", (req.character_id, reply, datetime.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
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

    conn = get_db()
    conn.execute(
        "INSERT INTO fortune_history (category, user_name, input_summary, result_summary, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("관상" if is_face else "손금", req.user_name, req.question or "사진 업로드 분석", analysis[:180], 93, datetime.datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()
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
    conn = get_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO fortune_history (category, user_name, input_summary, result_summary, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (rec.category, rec.user_name, rec.input_summary, rec.result_summary, rec.score, now)
    )
    conn.commit()
    conn.close()
    return {"saved": True, "created_at": now}

@app.get("/api/history")
def list_history(limit: int = 20):
    conn = get_db()
    rows = conn.execute(
        "SELECT id, category, user_name, input_summary, result_summary, score, created_at FROM fortune_history ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}

@app.get("/")
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "운명상점 MVP API 서버가 실행 중입니다."}
