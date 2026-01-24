# 업비트 펌핑코인 알리미V2

업비트 코인을 필터링하고 자동 매매하는 Streamlit 웹 애플리케이션입니다.

## 주요 기능

- 📊 실시간 코인 필터링 (가격 변동률, 거래량 변동률 기반)
- 🔍 슬리피지 분석
- 📈 일봉 필터링 (양봉 비율 기반)
- 🤖 자동 매매 (시장가 매수, 지정가 매도)
- ⏰ 자동 종료 (설정된 시간 후 전량 매도)
- 📉 손절 기능

## 설치 방법

1. 저장소 클론
```bash
git clone <repository-url>
cd streamlit_app
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

3. 패키지 설치
```bash
pip install -r requirements.txt
```

4. API 키 설정
```bash
# api.json.example을 복사하여 api.json 생성
copy api.json.example api.json
# 또는
cp api.json.example api.json

# api.json 파일을 열어서 실제 API 키 입력
{
  "apiKey": "YOUR_API_KEY_HERE",
  "secretKey": "YOUR_SECRET_KEY_HERE"
}
```

## 실행 방법

```bash
streamlit run app.py
```

브라우저에서 자동으로 열리며, 기본 주소는 `http://localhost:8501`입니다.

## 파일 구조

```
streamlit_app/
├── app.py                      # 메인 Streamlit 애플리케이션
├── utils.py                    # 유틸리티 함수 (auto_trading_system_gui.py 래퍼)
├── auto_trading_system_gui.py  # 핵심 로직 (필터링, 매매 등)
├── requirements.txt            # Python 패키지 의존성
├── api.json.example           # API 키 템플릿
├── .gitignore                 # Git 제외 파일 목록
└── README.md                  # 이 파일
```

## 사용 방법

1. 사이드바에서 필터링 조건 설정
2. "분석 시작" 버튼 클릭
3. 결과 확인 및 CSV 다운로드
4. 자동매매 활성화 시 자동으로 매수 실행

## 주의사항

- ⚠️ `api.json` 파일은 절대 공개 저장소에 커밋하지 마세요!
- ⚠️ 실제 거래 전에 충분히 테스트하세요.
- ⚠️ 투자 손실에 대한 책임은 사용자에게 있습니다.

## 라이선스

이 프로젝트는 개인 사용 목적으로 제작되었습니다.
