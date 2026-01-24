# Railway 배포 단계별 가이드

## 1단계: Railway 계정 생성 및 로그인

1. https://railway.app 접속
2. **"Login"** 클릭
3. GitHub 계정으로 로그인 (권장)
4. 로그인 완료

## 2단계: 새 프로젝트 생성

1. Railway 대시보드에서 **"New Project"** 클릭
2. **"Deploy from GitHub repo"** 선택
3. GitHub 저장소 선택 (이미 푸시한 저장소)
4. 또는 **"Empty Project"** 선택 후 수동 배포

## 3단계: GitHub 저장소 연결 (자동 배포)

### 방법 A: GitHub 저장소에서 직접 배포

1. Railway 대시보드 → **"New Project"**
2. **"Deploy from GitHub repo"** 선택
3. 저장소 선택 및 연결
4. Railway가 자동으로 감지하여 배포 시작

### 방법 B: Railway CLI 사용

```bash
# Railway CLI 설치 (이미 설치되어 있다면 생략)
npm i -g @railway/cli

# 로그인
railway login

# 프로젝트 초기화
railway init

# 배포
railway up
```

## 4단계: 환경 변수 설정

Railway 대시보드에서 **Variables** 탭으로 이동하여 다음 환경 변수 추가:

### 필수 환경 변수

```
DATA_DIR=/data
```

### 선택적 환경 변수 (필요시)

```
PORT=8501
```

## 5단계: Volume 설정 (CSV 파일 영구 저장용)

### Volume 생성

1. Railway 대시보드 → 프로젝트 선택
2. **"Volumes"** 탭으로 이동
3. **"New Volume"** 클릭
4. 설정:
   - **Name**: `data-volume`
   - **Mount Path**: `/data`
5. **"Create"** 클릭

### Volume 연결

1. 서비스(Service) 선택
2. **"Settings"** → **"Volumes"**
3. 생성한 Volume 선택 및 마운트 경로 확인 (`/data`)

## 6단계: 배포 확인

1. Railway 대시보드에서 **"Deployments"** 탭 확인
2. 배포 상태가 **"Success"**가 될 때까지 대기
3. **"Settings"** → **"Domains"**에서 생성된 URL 확인
4. URL 클릭하여 앱 접속 테스트

## 7단계: API 키 설정 (자동매매 사용 시)

### 방법 1: Railway 환경 변수 사용 (권장하지 않음)

```
UPBIT_API_KEY=your_api_key
UPBIT_SECRET_KEY=your_secret_key
```

### 방법 2: Railway Volume에 api.json 저장

1. Volume에 `api.json` 파일 업로드
2. 코드에서 Volume 경로의 `api.json` 읽도록 수정

### 방법 3: Railway Secrets 사용

Railway의 **"Variables"** 탭에서 **"New Variable"** → **"Secret"** 선택하여 안전하게 저장

## 8단계: 로그 확인

1. Railway 대시보드 → **"Deployments"** → 최신 배포 선택
2. **"Logs"** 탭에서 배포 로그 확인
3. 에러가 있으면 로그 확인

## 주의사항

⚠️ **중요**:
- `api.json` 파일은 절대 GitHub에 커밋하지 마세요!
- Railway Volume을 사용하지 않으면 CSV 파일이 컨테이너 재시작 시 사라질 수 있습니다
- Streamlit 앱은 무료 플랜에서도 사용 가능하지만, 리소스 제한이 있을 수 있습니다

## 문제 해결

### 배포 실패 시

1. **Logs** 탭에서 에러 메시지 확인
2. `requirements.txt`에 모든 패키지가 포함되어 있는지 확인
3. `Procfile`이 올바른지 확인

### 앱이 실행되지 않는 경우

1. 포트 설정 확인 (Railway는 `$PORT` 환경 변수 사용)
2. `Procfile` 확인: `web: streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
3. 로그에서 에러 메시지 확인

### CSV 파일이 저장되지 않는 경우

1. `DATA_DIR` 환경 변수 확인
2. Volume 마운트 상태 확인
3. 파일 권한 확인
