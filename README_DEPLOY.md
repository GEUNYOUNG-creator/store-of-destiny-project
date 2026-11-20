# 운명상점 (Fortune Shop) MVP v2 배포 가이드

## 포함된 주요 업데이트
- 7종 3D 마스터 + 7종 3D 미니 캐릭터 완비 (사주 아기 옥룡 청옥이, MBTI 구름토끼 모모 포함)
- 22장 메이저 아르카나 부채꼴 타로 덱 + 3장(과거·현재·미래) 일러스트 카드 & Gemini AI 리딩
- 사주 신살(도화살·역마살·화개살·천을귀인) 분석 + 성별 맞춤 상황 일러스트 카드
- 관상 대표 타입 분석 + 미래 배우자 얼굴 AI 생성(`/api/vision`, `/api/spouse-portrait`)

## GitHub 푸시 & Render 자동 배포
1. 이 ZIP 파일의 내용을 로컬 폴더(`store_of_destiny`)에 덮어쓰기 합니다.
2. 터미널에서 아래 명령어를 순서대로 실행합니다:
   ```bash
   git add .
   git commit -m "feat: MVP v2 (7 mini pets, 22 tarot deck, saju sinsal art, AI spouse portrait)"
   git push origin main
   ```
3. Render가 자동으로 새 버전을 배포합니다.
