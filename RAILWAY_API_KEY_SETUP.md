# Railway에서 API 키 설정 방법

## 방법 1: Railway Volume에 api.json 파일 업로드 (권장)

### 1단계: Volume 생성 및 마운트

1. Railway 대시보드 → 프로젝트 선택
2. **"Volumes"** 탭 → **"New Volume"** 클릭
3. 설정:
   - **Name**: `data-volume`
   - **Mount Path**: `/data`
4. **"Create"** 클릭
5. 서비스에 Volume 연결 확인

### 2단계: api.json 파일 업로드

#### 방법 A: Railway CLI 사용

```bash
# Railway CLI 설치 (없다면)
npm i -g @railway/cli

# 로그인
railway login

# 프로젝트 연결
railway link

# api.json 파일을 Volume에 복사
railway run sh -c "echo '{\"apiKey\":\"YOUR_API_KEY\",\"secretKey\":\"YOUR_SECRET_KEY\"}' > /data/api.json"
```

#### 방법 B: Railway 대시보드에서 직접

1. Railway 대시보드 → 프로젝트 → **"Volumes"** 탭
2. 생성한 Volume 선택
3. **"Files"** 또는 **"Upload"** 옵션 확인
4. `api.json` 파일 업로드

⚠️ **참고**: Railway Volume의 파일 업로드는 CLI를 통하거나, 배포 시점에 파일을 포함시키는 방법을 사용해야 합니다.

### 3단계: 코드 수정 (Volume 경로 사용)

`load_api_keys_from_json` 함수가 Volume 경로를 확인하도록 수정 필요:

```python
# 현재 디렉토리 또는 DATA_DIR에서 api.json 찾기
api_json_path = os.path.join(os.getenv("DATA_DIR", "."), "api.json")
if not os.path.exists(api_json_path):
    api_json_path = "api.json"  # 기본 경로
```

## 방법 2: 환경 변수 사용 (가장 안전, 권장)

### 1단계: Railway 환경 변수 설정

Railway 대시보드 → 프로젝트 → **"Variables"** 탭:

1. **"New Variable"** 클릭
2. **"Secret"** 선택 (중요!)
3. 변수 추가:
   ```
   UPBIT_API_KEY = your_api_key_here
   UPBIT_SECRET_KEY = your_secret_key_here
   ```

### 2단계: 코드 수정 (환경 변수 우선 사용)

`load_api_keys_from_json` 함수를 수정하여 환경 변수를 먼저 확인:

```python
def load_api_keys_from_json():
    """환경 변수 또는 api.json 파일에서 API 키를 읽어옵니다."""
    # 1. 환경 변수에서 먼저 확인 (Railway Secrets)
    api_key = os.getenv("UPBIT_API_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")
    
    if api_key and secret_key:
        return api_key, secret_key
    
    # 2. api.json 파일에서 읽기
    try:
        # DATA_DIR 또는 현재 디렉토리에서 api.json 찾기
        data_dir = os.getenv("DATA_DIR", ".")
        api_json_path = os.path.join(data_dir, "api.json")
        
        if not os.path.exists(api_json_path):
            api_json_path = "api.json"
        
        with open(api_json_path, "r", encoding="utf-8") as f:
            content = f.read()
            # ... 기존 코드 ...
    except Exception as e:
        return None, None
```

## 방법 3: 배포 시점에 파일 포함 (비권장)

⚠️ **보안 위험**: API 키가 코드에 포함되면 안 됩니다!

GitHub에 커밋하지 않고 Railway에만 배포하는 방법:

1. 로컬에서 `api.json` 파일 준비
2. Railway CLI로 직접 배포 (GitHub 거치지 않음)
3. 또는 Railway의 파일 시스템에 직접 업로드

## 권장 방법

**환경 변수 사용 (방법 2)**을 가장 권장합니다:
- ✅ 보안: Secrets로 안전하게 저장
- ✅ 관리: Railway 대시보드에서 쉽게 수정
- ✅ 버전 관리: 코드와 분리되어 안전

## 빠른 설정 (환경 변수 사용)

1. Railway 대시보드 → **"Variables"** 탭
2. **"New Variable"** → **"Secret"** 선택
3. 추가:
   - `UPBIT_API_KEY` = 실제 API 키
   - `UPBIT_SECRET_KEY` = 실제 Secret 키
4. 코드 수정하여 환경 변수 우선 사용
