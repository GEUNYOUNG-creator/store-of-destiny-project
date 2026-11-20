"""
운명상점 (Fortune Shop) — FastAPI + SQLite DB + Free Gemini API (Default) / Local Ollama Backend
Render 무료 호스팅 및 로컬 PC 모두 지원!
환경변수:
  - GEMINI_API_KEY : Google AI Studio 무료 API 키 (설정 시 Gemini API 우선 사용)
  - GEMINI_MODEL   : 기본값 'gemini-3.5-flash-lite' (채팅 + 관상/손금 비전 모두 지원)
  - OLLAMA_URL     : GEMINI_API_KEY가 없을 때 로컬 Ollama 폴백 주소 (기본 http://127.0.0.1:11434)
"""
import os
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
OLLAMA_BASE_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_CHAT = os.environ.get("OLLAMA_CHAT_MODEL", "qwen2.5:7b")
DEFAULT_OLLAMA_VISION = os.environ.get("OLLAMA_VISION_MODEL", "llama3.2-vision")

app = FastAPI(title="운명상점 Full-Stack API (Gemini API + SQLite)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHARACTER_PROMPTS = {
    "saju": "당신은 동양풍 '운명상점'의 주인 '연화'입니다. 사주 명리 전문가로서 고풍스럽고 다정한 존댓말로 사용자의 사주와 운명을 깊이 있게 상담해 주세요.",
    "blood": "당신은 발랄하고 장난기 많은 혈액형 궁합 마스터 '루미'입니다. 친근한 반말과 귀여운 이모티콘(♥, ~)을 섞어 혈액형 성격과 연애 케미를 재밌게 알려주세요.",
    "zodiac": "당신은 반짝이는 별자리 천문 점성술사 '스텔라'입니다. 밝고 에너지 넘치는 말투로 별자리 운세와 성좌 궁합을 희망차게 들려주세요.",
    "tarot": "당신은 신비로운 타로 리더 '셀레네'입니다. 차분하고 몽환적인 존댓말로 타로 카드의 상징과 내면의 조언을 전해 주세요.",
    "mbti": "당신은 따뜻한 MBTI 심리상담사 '하린'입니다. 공감 어린 다정한 말투로 성격 유형별 관계 고민과 소통 팁을 위로하며 알려주세요.",
    "face": "당신은 예리하고 우아한 젊은 관상가 '아린'입니다. 얼굴의 이마(초년운), 눈썹·눈(중년운·인복), 코(재물운), 입·하관(말년운)을 품격 있고 긍정적으로 풀이해 주세요.",
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

class ChatRequest(BaseModel):
    character_id: str
    message: str
    user_name: Optional[str] = "방문자"
    model: Optional[str] = None
    context: Optional[str] = ""

class VisionRequest(BaseModel):
    character_id: str
    image_base64: str
    user_name: Optional[str] = "방문자"
    question: Optional[str] = ""
    model: Optional[str] = None

async def call_gemini(system_prompt: str, user_parts: list, model_name: str):
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 설정되지 않았습니다.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": user_parts}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 600}
    }
    async with httpx.AsyncClient(timeout=45.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return "운명의 기운을 읽는 중 잠시 흐려졌습니다. 다시 한 번 질문해 주실래요?"
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()

@app.get("/api/health")
async def health():
    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    provider = "gemini" if api_key else "ollama"
    return {
        "status": "ok",
        "db": "sqlite",
        "provider": provider,
        "gemini_ready": bool(api_key),
        "ollama_connected": bool(api_key),
        "default_model": DEFAULT_GEMINI_MODEL if api_key else DEFAULT_OLLAMA_CHAT
    }

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

@app.post("/api/chat")
async def chat_with_character(req: ChatRequest):
    sys_prompt = CHARACTER_PROMPTS.get(req.character_id, CHARACTER_PROMPTS["saju"])
    sys_prompt += "\n답변은 모바일 앱 대화창에 어울리게 2~4문장으로 자연스럽고 따뜻하게 한국어로 작성하세요."

    conn = get_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn.execute("INSERT INTO chat_logs (character_id, role, content, created_at) VALUES (?, 'user', ?, ?)", (req.character_id, req.message, now))
    recent = conn.execute("SELECT role, content FROM chat_logs WHERE character_id = ? ORDER BY id DESC LIMIT 6", (req.character_id,)).fetchall()
    conn.commit()

    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if api_key:
        model_name = req.model if (req.model and req.model.startswith("gemini")) else DEFAULT_GEMINI_MODEL
        history_text = "\n".join(f"{'사용자' if r['role']=='user' else '상담사'}: {r['content']}" for r in reversed(recent))
        try:
            reply = await call_gemini(sys_prompt, [{"text": f"사용자 이름: {req.user_name}\n\n[최근 대화]\n{history_text}"}], model_name)
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=503, detail=f"Gemini API 오류: {str(e)}")
    else:
        model_name = req.model or DEFAULT_OLLAMA_CHAT
        messages = [{"role": "system", "content": sys_prompt}] + [{"role": r["role"], "content": r["content"]} for r in reversed(recent)]
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json={"model": model_name, "messages": messages, "stream": False})
                resp.raise_for_status()
                reply = resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=503, detail=f"Ollama 연결 실패: {str(e)}")

    conn.execute("INSERT INTO chat_logs (character_id, role, content, created_at) VALUES (?, 'assistant', ?, ?)", (req.character_id, reply, datetime.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return {"reply": reply, "model": model_name}

@app.post("/api/vision")
async def analyze_vision(req: VisionRequest):
    is_face = req.character_id == "face"
    sys_prompt = CHARACTER_PROMPTS["face" if is_face else "palm"]
    prompt = (
        f"사용자 이름: {req.user_name}. "
        + ("이 얼굴 사진을 보고 관상(이마·눈썹과 눈·코·입과 하관, 전체 인상과 운세 흐름)을 한국어로 4~5문장으로 품격 있고 긍정적으로 풀이해 주세요."
           if is_face else
           "이 손바닥 사진을 보고 손금(생명선·두뇌선·감정선·운명선과 앞으로의 재물·연애·건강 흐름)을 한국어로 4~5문장으로 상세하고 희망적으로 풀이해 주세요.")
    )
    if req.question:
        prompt += f" 추가 질문: {req.question}"

    mime = "image/jpeg"
    if req.image_base64.startswith("data:") and ";" in req.image_base64:
        mime = req.image_base64.split(";")[0].replace("data:", "")
    img_clean = req.image_base64.split(",")[-1]

    api_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
    if api_key:
        model_name = req.model if (req.model and req.model.startswith("gemini")) else DEFAULT_GEMINI_MODEL
        try:
            analysis = await call_gemini(
                sys_prompt,
                [{"text": prompt}, {"inlineData": {"mimeType": mime, "data": img_clean}}],
                model_name
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Gemini Vision API 오류: {str(e)}")
    else:
        model_name = req.model or DEFAULT_OLLAMA_VISION
        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(
                    f"{OLLAMA_BASE_URL}/api/chat",
                    json={"model": model_name, "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": prompt, "images": [img_clean]}], "stream": False}
                )
                resp.raise_for_status()
                analysis = resp.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Ollama Vision 실패: {str(e)}")

    conn = get_db()
    conn.execute(
        "INSERT INTO fortune_history (category, user_name, input_summary, result_summary, score, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("관상" if is_face else "손금", req.user_name, req.question or "사진 업로드 분석", analysis[:160], 92, datetime.datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    conn.close()
    return {"analysis": analysis, "model": model_name}

@app.get("/")
def serve_index():
    index_path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "운명상점 API 서버가 실행 중입니다."}
