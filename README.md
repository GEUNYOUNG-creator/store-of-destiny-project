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


## 최근 주요 업그레이드 (v2.0)
- **8번째 사상의학(四象醫學) 캐릭터 '다온' & 미니 펫 '초롱이' 추가**: 전용 3D 포트레이트(`char3d_sasang_open/blink.jpg`, `pet3d_sasang_open/blink.jpg`), **사상의학 도감**(태양인·태음인·소양인·소음인 4대 체질 미리보기), 체질 직접 선택 및 **전신 사진 액티브 가이드라인 촬영 + Vision AI 체질 판별** 및 상세 신체 특징·식단·운동 안내.
- **전 캐릭터(8인) 개성 있는 젊고 경쾌한 보이스(TTS) 시스템**: 루미의 발랄한 기준 톤을 포함해 8명 전원 어리고 늘어지지 않는 전용 음색(pitch/rate) 적용, 상단 보이스 버튼·말풍선 터치·풀이 결과 음성 듣기·환경설정 ON/OFF 지원.
- **전통 사주 신살 13종 대폭 확장 및 전 영역 장문·컬러 포인트 가독성 개편**: 도화살·역마살·화개살·천을귀인 외에 **현침살·백호대살·괴강살·홍염살·귀문관살·원진살·문창귀인·천덕귀인·양인살** 정밀 판별 추가, 문단 분리 및 핵심 포인트 컬러 하이라이트 렌더러(`formatRichReadingHtml`) 적용.
