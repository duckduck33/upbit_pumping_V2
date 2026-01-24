# GitHub 저장소 업로드 가이드

## 1단계: GitHub에서 저장소 생성

1. GitHub 웹사이트 (https://github.com)에 로그인
2. 우측 상단의 **"+"** 버튼 클릭 → **"New repository"** 선택
3. 저장소 정보 입력:
   - **Repository name**: `업비트-펌핑코인-알리미V2` (또는 원하는 이름)
   - **Description**: "업비트 코인 필터링 및 자동 매매 시스템"
   - **Public** 또는 **Private** 선택
   - ⚠️ **"Initialize this repository with a README"** 체크 해제 (이미 README.md가 있음)
4. **"Create repository"** 버튼 클릭

## 2단계: 로컬에서 Git 초기화 및 커밋

### 2-1. Git 초기화 (처음 한 번만)

```bash
# streamlit_app 폴더로 이동
cd streamlit_app

# Git 저장소 초기화
git init
```

### 2-2. 파일 추가 및 커밋

```bash
# 모든 파일 추가 (api.json, trading_config.json은 .gitignore에 의해 제외됨)
git add .

# 커밋 메시지와 함께 커밋
git commit -m "Initial commit: 업비트 펌핑코인 알리미V2"
```

## 3단계: GitHub 원격 저장소 연결

```bash
# 원격 저장소 추가 (YOUR_USERNAME과 YOUR_REPO_NAME을 실제 값으로 변경)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 예시:
# git remote add origin https://github.com/username/업비트-펌핑코인-알리미V2.git
```

## 4단계: GitHub에 푸시

```bash
# 메인 브랜치로 푸시
git branch -M main
git push -u origin main
```

## 전체 명령어 순서 (한 번에 실행)

```bash
# 1. streamlit_app 폴더로 이동
cd streamlit_app

# 2. Git 초기화
git init

# 3. 파일 추가
git add .

# 4. 커밋
git commit -m "Initial commit: 업비트 펌핑코인 알리미V2"

# 5. 원격 저장소 연결 (YOUR_USERNAME과 YOUR_REPO_NAME 변경 필요)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 6. 푸시
git branch -M main
git push -u origin main
```

## 주의사항

⚠️ **중요**: 다음 파일들은 `.gitignore`에 의해 자동으로 제외됩니다:
- `api.json` (API 키 포함)
- `trading_config.json` (개인 설정)
- `*.csv` (결과 파일)
- `*.html` (결과 파일)
- `__pycache__/` (Python 캐시)

✅ **업로드되는 파일들**:
- `app.py`
- `utils.py`
- `auto_trading_system_gui.py`
- `requirements.txt`
- `README.md`
- `README_GITHUB.md`
- `RAILWAY_DEPLOY.md`
- `api.json.example`
- `.gitignore`
- 기타 문서 파일들

## 문제 해결

### 인증 오류 발생 시

GitHub에서 Personal Access Token을 사용해야 할 수 있습니다:

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token" 클릭
3. 권한 선택: `repo` 체크
4. 토큰 생성 후 복사
5. 푸시 시 비밀번호 대신 토큰 사용

### 이미 Git 저장소가 있는 경우

```bash
# 원격 저장소 확인
git remote -v

# 기존 원격 저장소 제거 (필요시)
git remote remove origin

# 새로운 원격 저장소 추가
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
```
