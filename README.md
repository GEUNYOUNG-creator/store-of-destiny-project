# 운명상점 (Fortune Shop) — Full-Stack 3D AI Fortune App

7명의 3D CGI 마스터(사주·혈액형·별자리·타로·MBTI·관상·손금)와 3종의 무료 미니 3D 펫, SQLite DB, 로컬 Ollama(LLM 채팅 + Vision 사진 분석)가 연동되는 풀스택 앱입니다.

## 폴더 구조
- `index.html`: 단일 완성본 프론트엔드 앱 (GitHub Pages 및 로컬 서버 실행용)
- `backend/server.py`: FastAPI + SQLite DB + Ollama 채팅/비전 연동 백엔드 서버
- `backend/requirements.txt`: 파이썬 패키지 목록
- `src/`: 추후 편집용 분리 소스 및 3D 이미지 에셋

## 로컬 실행 방법 (Windows / macOS)
1. [Ollama](https://ollama.com/) 설치 후 모델 다운로드:
   ```bash
   ollama pull qwen2.5:7b
   ollama pull llama3.2-vision
   ```
2. 백엔드 실행:
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn server:app --host 0.0.0.0 --port 8000 --reload
   ```
3. 브라우저에서 `http://127.0.0.1:8000` 접속 후 앱 우측 상단 **⚙️ 설정**에서 서버 주소(`http://127.0.0.1:8000`) 입력 및 연동 ON.
