# Git Line Ending 경고 해결 방법

## 경고 메시지 의미

```
warning: in the working copy of 'app.py', LF will be replaced by CRLF the next time Git touches it
```

이 경고는 **줄바꿈 문자(Line Ending)** 차이 때문에 발생합니다.

- **Windows**: CRLF (`\r\n`) 사용
- **Linux/Mac**: LF (`\n`) 사용
- **Git**: 저장소에는 LF로 저장하고, Windows에서는 자동으로 CRLF로 변환

## 해결 방법

### 방법 1: 경고 무시 (권장)

이 경고는 **무해**하며, Git이 자동으로 처리합니다. 그대로 진행해도 됩니다.

### 방법 2: Git 설정 변경

#### Windows에서 자동 변환 활성화 (기본값)

```bash
git config core.autocrlf true
```

#### 저장소에 LF로 저장, 체크아웃 시 자동 변환

```bash
git config core.autocrlf input
```

#### 자동 변환 비활성화 (경고 제거)

```bash
git config core.autocrlf false
```

### 방법 3: .gitattributes 파일 생성 (권장)

프로젝트 루트에 `.gitattributes` 파일을 생성하여 일관된 줄바꿈 처리:

```
# 모든 텍스트 파일을 LF로 정규화
* text=auto eol=lf

# Python 파일은 LF 사용
*.py text eol=lf

# Windows 배치 파일은 CRLF 사용
*.bat text eol=crlf
*.cmd text eol=crlf
```

## 권장 설정

Windows에서 작업하는 경우:

```bash
# 전역 설정 (모든 저장소에 적용)
git config --global core.autocrlf true

# 또는 현재 저장소만
git config core.autocrlf true
```

이렇게 설정하면:
- 커밋 시: CRLF → LF로 변환
- 체크아웃 시: LF → CRLF로 변환
- 경고 메시지가 나타나지만 정상 동작

## 결론

**이 경고는 무시해도 됩니다.** Git이 자동으로 처리하므로 기능에는 문제가 없습니다.
