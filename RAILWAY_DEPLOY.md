# Railway 배포 가이드

## Railway 배포 시 CSV 파일 저장 문제 해결

Railway는 컨테이너 기반 플랫폼이므로 기본 파일 시스템은 임시적입니다. CSV 파일을 영구적으로 저장하려면 **Railway Volume**을 사용해야 합니다.

## 설정 방법

### 1. Railway Volume 생성

1. Railway 대시보드에서 프로젝트 선택
2. **Volumes** 탭으로 이동
3. **New Volume** 클릭
4. Volume 이름 설정 (예: `data-volume`)
5. 마운트 경로 설정 (예: `/data`)

### 2. 환경 변수 설정

Railway 대시보드에서 **Variables** 탭으로 이동하여 다음 환경 변수를 추가:

```
DATA_DIR=/data
```

이렇게 설정하면 모든 CSV 파일이 `/data` 디렉토리에 저장되어 컨테이너 재시작 후에도 유지됩니다.

### 3. Volume 없이 사용하는 경우

Volume을 사용하지 않으면:
- CSV 파일은 컨테이너 재시작 시 사라질 수 있습니다
- 하지만 분석 결과는 Streamlit의 `session_state`에 저장되므로 세션 동안은 유지됩니다
- "코인 필터링 결과"와 "수익률 보기" 버튼은 CSV 파일이 없으면 작동하지 않습니다

## 대안: 외부 스토리지 사용

Volume 대신 외부 스토리지를 사용할 수도 있습니다:

### 옵션 1: AWS S3
### 옵션 2: Google Cloud Storage
### 옵션 3: 데이터베이스 (PostgreSQL, SQLite)

필요시 추가 구현 가능합니다.

## 확인 사항

배포 후 다음을 확인하세요:

1. `DATA_DIR` 환경 변수가 올바르게 설정되었는지
2. Volume이 올바른 경로에 마운트되었는지
3. CSV 파일이 생성되는지 (로그 확인)

## 문제 해결

### CSV 파일이 저장되지 않는 경우

1. Railway 로그에서 `DATA_DIR` 경로 확인
2. Volume 마운트 상태 확인
3. 파일 권한 확인 (필요시 `chmod` 사용)

### CSV 파일을 찾을 수 없는 경우

1. `glob.glob()` 경로가 올바른지 확인
2. `DATA_DIR` 환경 변수가 설정되었는지 확인
3. 파일이 실제로 생성되었는지 확인
