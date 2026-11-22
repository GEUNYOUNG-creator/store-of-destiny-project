# 운명상점 Android (Google Play + AdMob) 패키징 가이드

이 프로젝트에는 `window.DestinyAds` 광고 브리지(하단 52px 안전 배너 슬롯 · 2회 풀이당 전면광고 1회 · 보상형 광고 훅)와 백엔드 구독/이용권 권한 API(`/api/user/entitlement`)가 이미 내장되어 있습니다.

## 1. Capacitor Android 프로젝트 초기화
```bash
npm init -y
npm install @capacitor/core @capacitor/cli @capacitor/android @capacitor-community/admob
npx cap init "운명상점" "com.storeofdestiny.app" --web-dir .
npx cap add android
```

## 2. AdMob 앱 ID 등록 (`android/app/src/main/AndroidManifest.xml`)
`<application>` 태그 안에 본인 AdMob 앱 ID를 넣으세요(테스트 시 Google 공식 테스트 앱 ID 사용 가능):
```xml
<meta-data
    android:name="com.google.android.gms.ads.APPLICATION_ID"
    android:value="ca-app-pub-3940256099942544~3347511713"/>
```

## 3. 실서비스 광고 단위 ID 교체 (`index.html`)
`index.html`의 `ADMOB_CONFIG` 객체에서 테스트 ID 3개(`bannerId`, `interstitialId`, `rewardedId`)를 AdMob 콘솔에서 발급받은 실제 단위 ID로 교체하세요.

## 4. Android Studio에서 `.aab` 빌드 후 Google Play Console 업로드
```bash
npx cap sync android
npx cap open android
```
Android Studio → **Build → Generate Signed App Bundle / APK → Android App Bundle (.aab)** 생성 후 Google Play Console에 업로드하시면 됩니다.

## 5. Supabase 영구 DB & Google·카카오 실로그인 연결 (Render 환경변수)
Render 대시보드 → **Environment**에 아래 환경변수를 등록하면 Google/카카오 실계정 로그인과 운세 기록 영구 저장이 즉시 연동됩니다.
- `DATABASE_URL`: Supabase 프로젝트 → Connect → Transaction/Session Pooler URI (`postgresql://...`)
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: Google Cloud Console OAuth 클라이언트 (Redirect URI: `https://store-of-destiny-project.onrender.com/api/auth/google/callback`)
- `KAKAO_CLIENT_ID`: Kakao Developers REST API 키 (Redirect URI: `https://store-of-destiny-project.onrender.com/api/auth/kakao/callback`)
