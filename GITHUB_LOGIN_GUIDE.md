# GitHub CLI 로그인 가이드

## 방법 1: GitHub CLI 사용 (권장)

### 로그인

```bash
gh auth login
```

실행하면 다음 옵션이 나타납니다:

1. **GitHub.com** 선택
2. **HTTPS** 또는 **SSH** 선택 (HTTPS 권장)
3. **Login with a web browser** 선택 (가장 간단)
4. 브라우저에서 인증 코드 입력
5. GitHub 계정으로 로그인 및 권한 승인

### 로그인 상태 확인

```bash
gh auth status
```

### 로그아웃

```bash
gh auth logout
```

## 방법 2: Personal Access Token 사용

### 1. GitHub에서 토큰 생성

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. "Generate new token (classic)" 클릭
3. Note: "Git CLI" 입력
4. Expiration: 원하는 기간 선택
5. 권한 선택:
   - ✅ `repo` (전체 체크)
   - ✅ `workflow` (필요시)
6. "Generate token" 클릭
7. **토큰 복사** (한 번만 표시됨!)

### 2. Git에 토큰 설정

```bash
# 전역 설정 (모든 저장소에 적용)
git config --global credential.helper store

# 또는 Windows Credential Manager 사용
git config --global credential.helper wincred
```

### 3. 푸시 시 토큰 사용

```bash
# 푸시 시 사용자 이름과 비밀번호 입력 요청
git push -u origin main

# Username: GitHub 사용자 이름
# Password: Personal Access Token (비밀번호가 아님!)
```

## 방법 3: SSH 키 사용

### 1. SSH 키 생성

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

### 2. SSH 키를 GitHub에 추가

```bash
# 공개 키 복사
cat ~/.ssh/id_ed25519.pub
# 또는 Windows의 경우
type %USERPROFILE%\.ssh\id_ed25519.pub
```

1. GitHub → Settings → SSH and GPG keys
2. "New SSH key" 클릭
3. 복사한 공개 키 붙여넣기
4. "Add SSH key" 클릭

### 3. SSH로 원격 저장소 연결

```bash
# HTTPS 대신 SSH 사용
git remote set-url origin git@github.com:YOUR_USERNAME/YOUR_REPO_NAME.git
```

## 빠른 시작 (GitHub CLI 사용)

```bash
# 1. 로그인
gh auth login

# 2. 로그인 확인
gh auth status

# 3. 저장소 생성 및 푸시 (선택사항)
gh repo create 업비트-펌핑코인-알리미V2 --public --source=. --remote=origin --push
```

## 문제 해결

### 인증 실패 시

```bash
# 캐시된 자격 증명 제거
git credential-cache exit
# 또는 Windows
git credential-manager-core erase
```

### GitHub CLI 재인증

```bash
gh auth refresh
```
