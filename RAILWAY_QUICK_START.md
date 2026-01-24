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

Railway 대시보드에서 환경 변수를 설정합니다:

1. **Railway 대시보드 접속**
   - https://railway.app 접속
   - 로그인 후 프로젝트 선택

2. **Variables 탭으로 이동**
   - 프로젝트 대시보드에서 상단 메뉴의 **"Variables"** 탭 클릭
   - 또는 왼쪽 사이드바에서 **"Variables"** 선택

3. **새 환경 변수 추가**
   - **"+ New Variable"** 또는 **"Add Variable"** 버튼 클릭
   - 변수 이름 입력: `DATA_DIR`
   - 변수 값 입력: `/data`
   - **"Add"** 또는 **"Save"** 버튼 클릭

4. **설정 확인**
   - 추가된 변수가 목록에 표시되는지 확인
   - 변수 이름: `DATA_DIR`
   - 변수 값: `/data`

**참고**: 
- 이 변수는 CSV 파일 저장 경로를 지정합니다
- Volume을 사용하지 않으면 이 변수는 선택사항입니다
- Volume을 사용하는 경우 반드시 설정해야 합니다

### 4단계: Volume 생성 (CSV 파일 영구 저장용)

⚠️ **참고**: Volumes는 Railway의 유료 플랜에서만 사용 가능할 수 있습니다. 무료 플랜에서는 사용할 수 없을 수 있습니다.

**Volumes 탭 찾기**:

1. **방법 A: 프로젝트 레벨에서 찾기**
   - 프로젝트 대시보드에서 상단 메뉴 확인
   - "Volumes" 탭이 있는지 확인
   - 없으면 서비스 레벨에서 확인

2. **방법 B: 서비스(Service) 레벨에서 찾기**
   - 프로젝트 내의 서비스(예: GitHub Deploy) 클릭
   - 서비스 상세 페이지에서 "Volumes" 탭 확인
   - 또는 "Settings" → "Volumes" 섹션 확인

3. **방법 C: Settings에서 찾기**
   - "Settings" 탭 클릭
   - 왼쪽 사이드바나 설정 메뉴에서 "Volumes" 또는 "Storage" 찾기

**Volume 생성 방법** (탭을 찾은 경우):

1. **"New Volume"** 또는 **"Create Volume"** 버튼 클릭
2. 설정:
   - **Name**: `data-volume`
   - **Mount Path**: `/data`
3. **"Create"** 클릭
4. 서비스에 Volume 연결 확인

**Volume이 없는 경우 대안**:

- Volume 없이도 앱은 작동하지만, CSV 파일은 컨테이너 재시작 시 사라질 수 있습니다
- 분석 결과는 Streamlit의 `session_state`에 저장되므로 세션 동안은 유지됩니다
- 영구 저장이 필요하면 외부 스토리지(예: AWS S3) 사용 고려

### 5단계: 공개 도메인 생성

#### A. Railway 기본 도메인 사용 (무료)

1. **"Settings"** 탭 클릭
2. **"Public Networking"** 섹션 찾기
3. **"Generate Service Domain"** 클릭
4. **포트 번호 입력**: `8501` (Streamlit 기본 포트)
   - ⚠️ 기본값이 8080으로 표시될 수 있지만, **8501로 변경**해야 합니다
5. **"Generate Domain"** 버튼 클릭
6. 생성된 도메인 URL 확인 (예: `https://your-app-name.up.railway.app`)

#### B. 전용 도메인 연결 (선택사항)

⚠️ **참고**: 전용 도메인을 연결해도 **출발(Outbound) IP는 여전히 동적**입니다. 업비트 API IP 등록은 여전히 필요합니다.

1. **"Settings"** 탭 → **"Domains"** 섹션
2. **"Custom Domain"** 클릭
3. 도메인 이름 입력 (예: `app.yourdomain.com`)
4. Railway가 제공하는 DNS 레코드를 도메인 등록업체에 추가
5. DNS 전파 대기

**전용 도메인의 장점**:
- ✅ 안정적인 접근 (IP 변경에 영향받지 않음)
- ✅ 자동 SSL 인증서
- ✅ 전문적인 URL

### 6단계: 배포 확인

1. **"Deployments"** 탭에서 배포 상태 확인
2. 생성된 도메인 URL 클릭하여 앱 접속 테스트
3. Streamlit 앱이 정상적으로 로드되는지 확인

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

### ⚠️ IP 주소 등록 필수!

업비트 API는 보안을 위해 **IP 주소 등록**이 필요합니다.

1. **Railway IP 확인**:
   - Streamlit 앱 사이드바에서 **"🔍 Railway IP 확인"** 버튼 클릭
   - 또는 Railway 앱이 배포된 후 https://api.ipify.org 접속

2. **업비트에 IP 등록**:
   - https://upbit.com → 마이페이지 → Open API 관리
   - 확인한 IP 주소를 등록

📖 **자세한 방법**: `RAILWAY_IP_SETUP.md` 파일 참고

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
