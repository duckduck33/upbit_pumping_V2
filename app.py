"""
업비트 리플 간단 매매: 시작 → 리플 1만원 매수 → 4분 후 자동 매도
"""
import streamlit as st
import pyupbit
import time
import os
import re
import json
import threading
import requests

COIN = "KRW-XRP"
BUY_AMOUNT_KRW = 10000  # 1만원
HOLD_SECONDS = 4 * 60   # 4분


def load_api_keys():
    """환경 변수 또는 api.json에서 API 키 로드"""
    api_key = os.getenv("UPBIT_API_KEY", "").strip()
    secret_key = os.getenv("UPBIT_SECRET_KEY", "").strip()
    if api_key and secret_key:
        return api_key, secret_key

    data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
    api_path = os.path.join(data_dir, "api.json")
    if not os.path.exists(api_path):
        api_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api.json")
    if not os.path.exists(api_path):
        return None, None

    try:
        with open(api_path, "r", encoding="utf-8") as f:
            content = f.read()
        api_key_match = re.search(r'apiKey\s*=\s*"([^"]+)"', content)
        secret_key_match = re.search(r'secretKey\s*=\s*"([^"]+)"', content)
        if api_key_match and secret_key_match:
            return api_key_match.group(1).strip(), secret_key_match.group(1).strip()
        data = json.loads(content)
        return (data.get("apiKey") or data.get("access_key") or "").strip(), (data.get("secretKey") or data.get("secret_key") or "").strip()
    except Exception:
        return None, None


def run_auto_sell(upbit):
    """4분 대기 후 전량 시장가 매도"""
    try:
        time.sleep(HOLD_SECONDS)
        balance = upbit.get_balance(COIN)
        if balance and float(balance) > 0:
            sell_result = upbit.sell_market_order(COIN, float(balance))
            if sell_result and (not isinstance(sell_result, dict) or not sell_result.get("error")):
                if "auto_sell_done" not in st.session_state:
                    st.session_state.auto_sell_done = True
                    st.session_state.auto_sell_message = "매도 완료"
            else:
                err = sell_result.get("error", {}) if isinstance(sell_result, dict) else {}
                st.session_state.auto_sell_done = True
                st.session_state.auto_sell_message = f"매도 실패: {err.get('message', sell_result)}"
        else:
            st.session_state.auto_sell_done = True
            st.session_state.auto_sell_message = "매도할 수량 없음"
    except Exception as e:
        st.session_state.auto_sell_done = True
        st.session_state.auto_sell_message = f"매도 오류: {e}"


st.set_page_config(page_title="리플 1만원 매수·4분 후 매도", page_icon="🪙", layout="centered")
st.title("🪙 리플 1만원 매수 → 4분 후 자동 매도")

# 서버 IP 확인 (업비트 API에 등록할 IP)
with st.sidebar:
    st.header("🔧 도구")
    if st.button("🔍 서버 IP 확인", help="현재 서버의 공인 IP를 확인합니다. 이 IP를 업비트 API 설정에 등록하세요."):
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=5)
            ip = r.json().get("ip", "확인 실패")
            st.success(f"✅ 현재 서버 IP")
            st.code(ip, language=None)
            st.caption("이 IP를 업비트 [마이페이지 → API 관리]에서 등록해야 매수/매도가 가능합니다.")
        except Exception as e:
            st.error(f"❌ IP 확인 실패: {e}")

if "auto_sell_done" not in st.session_state:
    st.session_state.auto_sell_done = False
if "auto_sell_message" not in st.session_state:
    st.session_state.auto_sell_message = ""
if "buy_done" not in st.session_state:
    st.session_state.buy_done = False
if "buy_message" not in st.session_state:
    st.session_state.buy_message = ""

if st.button("시작", type="primary"):
    api_key, secret_key = load_api_keys()
    if not api_key or not secret_key:
        st.error("API 키를 찾을 수 없습니다. api.json 또는 환경 변수 UPBIT_API_KEY, UPBIT_SECRET_KEY를 설정하세요.")
    else:
        try:
            upbit = pyupbit.Upbit(api_key, secret_key)
            result = upbit.buy_market_order(COIN, BUY_AMOUNT_KRW)
            if result and (not isinstance(result, dict) or not result.get("error")):
                st.session_state.buy_done = True
                st.session_state.buy_message = f"리플(XRP) {BUY_AMOUNT_KRW:,}원 매수 완료. 4분 후 자동 매도됩니다."
                thread = threading.Thread(target=run_auto_sell, args=(upbit,))
                thread.daemon = True
                thread.start()
            else:
                err = result.get("error", {}) if isinstance(result, dict) else {}
                st.error(f"매수 실패: {err.get('message', result)}")
        except Exception as e:
            st.error(f"오류: {e}")

if st.session_state.buy_done:
    st.success(st.session_state.buy_message)
    if not st.session_state.auto_sell_done:
        st.info("4분 후 자동 매도됩니다. 잠시 후 새로고침하면 결과를 확인할 수 있습니다.")
if st.session_state.auto_sell_done:
    st.success(st.session_state.auto_sell_message)
