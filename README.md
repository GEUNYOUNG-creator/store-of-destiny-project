# 운명상점 (Fortune Shop) Full-Stack MVP

## 포함 기능
- 7인 3D 마스터 + 7종 3D 미니 캐릭터 (사주·혈액형·별자리·타로·MBTI·관상·손금)
- 사주 신살(도화살·역마살·화개살·천을귀인) 성별 맞춤 상황 일러스트
- 타로 22장 메이저 아르카나 부채꼴 3장 뽑기
- 관상 대표 타입 분석 + AI 미래 배우자 얼굴 생성 (`/api/vision` + `/api/spouse-portrait`)
- 로그인 API (Google OAuth / Kakao OAuth / 이메일 회원가입·로그인) + 영구 DB 저장소 (PostgreSQL / SQLite 자동 전환)

## Render 환경변수 설정 (Environment)
- `GEMINI_API_KEY`: Google AI Studio 무료 API 키
- `GEMINI_MODEL`: `gemini-3.5-flash-lite`
- `DATABASE_URL`: Supabase 또는 Neon 무료 PostgreSQL 연결 URI (`postgresql://...`) — 미설정 시 로컬 SQLite 자동 사용
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`: Google OAuth 2.0 (콜백 URL: `https://store-of-destiny-project.onrender.com/api/auth/google/callback`)
- `KAKAO_CLIENT_ID`, `KAKAO_CLIENT_SECRET`: Kakao Developers OAuth (콜백 URL: `https://store-of-destiny-project.onrender.com/api/auth/kakao/callback`)
