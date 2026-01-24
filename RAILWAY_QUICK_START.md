# Railway 배포 빠른 시작 가이드

## 🚀 빠른 배포 순서

### 1단계: Railway 계정 생성 및 로그인

1. https://railway.app 접속
2. **"Login"** 클릭
3. **GitHub** 계정으로 로그인 (권장)

### 2단계: 새 프로젝트 생성

1. Railway 대시보드에서 **"New Project"** 클릭
2. **"Deploy from GitHub repo"** 선택
3. GitHub 저장소 선택 (이미 푸시한 저장소)
4. 저장소 선택 후 **"Deploy"** 클릭

### 3단계: 환경 변수 설정

Railway 대시보드 → 프로젝트 → **"Variables"** 탭:

```
DATA_DIR=/data
```

### 4단계: Volume 생성 (CSV 파일 영구 저장용)

1. **"Volumes"** 탭 → **"New Volume"** 클릭
2. 설정:
   - **Name**: `data-volume`
   - **Mount Path**: `/data`
3. **"Create"** 클릭
4. 서비스에 Volume 연결 (자동으로 연결됨)

### 5단계: 배포 확인

1. **"Deployments"** 탭에서 배포 상태 확인
2. **"Settings"** → **"Domains"**에서 생성된 URL 확인
3. URL 클릭하여 앱 접속 테스트

## 📋 필요한 파일 확인

배포 전 다음 파일들이 있는지 확인:

- ✅ `Procfile` (생성 완료)
- ✅ `requirements.txt` (있음)
- ✅ `app.py` (있음)
- ✅ `.gitignore` (있음)

## ⚙️ 환경 변수 목록

### 필수
- `DATA_DIR=/data` (Volume 사용 시)

### 선택 (필요시)
- `PORT=8501` (Railway가 자동 설정)

## 🔐 API 키 설정 (자동매매 사용 시)

⚠️ **중요**: `api.json`은 GitHub에 커밋하지 마세요!

### 방법: Railway Secrets 사용

1. Railway 대시보드 → **"Variables"** 탭
2. **"New Variable"** 클릭
3. **"Secret"** 선택
4. 변수 추가:
   - `UPBIT_API_KEY` = 실제 API 키
   - `UPBIT_SECRET_KEY` = 실제 Secret 키

코드에서 환경 변수로 읽도록 수정 필요 (선택사항)

## 📝 배포 후 확인 사항

1. ✅ 앱이 정상적으로 로드되는지
2. ✅ 로그에 에러가 없는지
3. ✅ CSV 파일이 저장되는지 (Volume 사용 시)
4. ✅ 자동매매가 작동하는지 (API 키 설정 시)

## 🐛 문제 해결

### 배포 실패
- **Logs** 탭에서 에러 확인
- `requirements.txt` 확인
- `Procfile` 확인

### 앱이 실행되지 않음
- 포트 설정 확인
- 로그 확인

### CSV 파일이 저장되지 않음
- `DATA_DIR` 환경 변수 확인
- Volume 마운트 확인
