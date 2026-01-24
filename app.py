"""
업비트 펌핑코인 알리미V2 - Streamlit 버전
"""
import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import json
import os
import sys
import warnings
import threading
import queue
import glob
import csv
import tempfile
import webbrowser
import pytz

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def get_kst_now():
    """한국 시간(KST)으로 현재 시간을 반환합니다."""
    return datetime.now(KST)

# Streamlit의 ScriptRunContext 경고 무시 (모듈 import 시 발생하는 경고)
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

# 현재 디렉토리의 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# utils 모듈 import (lazy import로 처리됨)
from utils import (
    get_all_upbit_coins,
    print_coins_under_price_and_volume,
    print_3minute_candles,
    print_filtered_coins_by_price_volume,
    print_all_coins_market_buy_analysis,
    print_filtered_by_slippage,
    filter_by_day_candle,
    load_api_keys_from_json,
    buy_coins_from_list
)

# 설정 파일 경로 (현재 디렉토리)
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading_config.json")

# 데이터 저장 디렉토리 (Railway Volume 지원)
# 환경 변수 DATA_DIR이 설정되어 있으면 사용, 없으면 현재 디렉토리 사용
DATA_DIR = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
# DATA_DIR이 존재하지 않으면 생성
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

def load_settings():
    """설정 파일에서 설정값을 로드합니다."""
    default_settings = {
        "interval": "1",
        "hour": "09",
        "minute": "00",
        "end_hour": "23",
        "end_minute": "00",
        "price_change_min": "0.2",
        "price_change_max": "5.0",
        "volume_change_min": "100",
        "slippage": "0.3",
        "max_spread": "0.2",
        "day_candle_filter": False,
        "auto_trade": False,
        "sell_percentage": "3",
        "sell_ratio": "절반",
        "investment_ratio": "100",
        "max_coins": "10",
        "stop_loss": "5",
        "end_hours": "2",
        "exclude_coins": ""
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_settings = json.load(f)
                # 기본값과 병합 (누락된 키가 있으면 기본값 사용)
                default_settings.update(saved_settings)
        except Exception as e:
            st.warning(f"설정 파일 로드 오류: {e}")
    
    return default_settings

def save_settings(settings):
    """설정값을 파일에 저장합니다."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"설정 파일 저장 오류: {e}")

# 페이지 설정
st.set_page_config(
    page_title="업비트 펌핑코인 알리미V2",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 제목
st.title("📈 업비트 펌핑코인 알리미V2")

# Railway IP 확인 버튼 (개발/배포 시 사용)
if st.sidebar.button("🔍 Railway IP 확인", help="Railway의 현재 IP 주소를 확인합니다. 업비트 API에 등록할 IP입니다."):
    try:
        import requests
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        railway_ip = response.json()['ip']
        st.sidebar.success(f"✅ Railway IP: {railway_ip}")
        st.sidebar.info("📝 이 IP를 업비트 API에 등록하세요!")
        st.sidebar.code(railway_ip)
    except Exception as e:
        st.sidebar.error(f"❌ IP 확인 실패: {e}")

# 결과 보기 버튼 (제목 아래)
col_result1, col_result2 = st.columns(2)
with col_result1:
    if st.button("📊 코인 필터링 결과", use_container_width=True):
        st.session_state.show_slippage_results = True
        st.rerun()
with col_result2:
    if st.button("💰 수익률 보기", use_container_width=True):
        st.session_state.show_profit_results = True
        st.rerun()

st.markdown("---")

# 설정값 로드 (초기화 시 한 번만)
if 'settings_loaded' not in st.session_state:
    st.session_state.settings = load_settings()
    st.session_state.settings_loaded = True

# session_state 초기화 (사이드바에서 사용하기 전에 초기화)
if 'run_analysis' not in st.session_state:
    st.session_state.run_analysis = False
if 'scheduler_running' not in st.session_state:
    st.session_state.scheduler_running = False
if 'show_slippage_results' not in st.session_state:
    st.session_state.show_slippage_results = False
if 'show_profit_results' not in st.session_state:
    st.session_state.show_profit_results = False
if 'purchased_coins' not in st.session_state:
    st.session_state.purchased_coins = {}
if 'sold_coins' not in st.session_state:
    st.session_state.sold_coins = {}
if 'scheduler_thread' not in st.session_state:
    st.session_state.scheduler_thread = None
if 'stop_scheduler' not in st.session_state:
    st.session_state.stop_scheduler = threading.Event()
if 'analysis_queue' not in st.session_state:
    st.session_state.analysis_queue = queue.Queue()
if 'logs' not in st.session_state:
    st.session_state.logs = []

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 펌핑코인 필터링 설정")
    
    # 기본 설정
    st.subheader("기본 설정")
    
    # 분봉 선택
    interval_options = ["1", "2", "3", "5", "15", "30", "60"]
    interval_default = interval_options.index(st.session_state.settings.get("interval", "1")) if st.session_state.settings.get("interval", "1") in interval_options else 0
    interval_minutes = st.selectbox("분봉 선택", interval_options, index=interval_default, key="interval_select")
    if interval_minutes != st.session_state.settings.get("interval", "1"):
        st.session_state.settings["interval"] = interval_minutes
        save_settings(st.session_state.settings)
    
    # 필터링 조건
    st.subheader("필터링 조건")
    col3, col4 = st.columns(2)
    with col3:
        price_change_min = st.number_input("가격 변동률 최소 (%)", min_value=0.0, max_value=100.0, 
                                          value=float(st.session_state.settings.get("price_change_min", "0.2")), 
                                          step=0.1, key="price_min_input")
        if price_change_min != float(st.session_state.settings.get("price_change_min", "0.2")):
            st.session_state.settings["price_change_min"] = str(price_change_min)
            save_settings(st.session_state.settings)
    with col4:
        price_change_max = st.number_input("가격 변동률 최대 (%)", min_value=0.0, max_value=100.0, 
                                          value=float(st.session_state.settings.get("price_change_max", "5.0")), 
                                          step=0.1, key="price_max_input")
        if price_change_max != float(st.session_state.settings.get("price_change_max", "5.0")):
            st.session_state.settings["price_change_max"] = str(price_change_max)
            save_settings(st.session_state.settings)
    
    volume_change_min = st.number_input("거래량 변동 최소 (%)", min_value=0.0, max_value=1000.0, 
                                        value=float(st.session_state.settings.get("volume_change_min", "100")), 
                                        step=1.0, key="volume_input")
    if volume_change_min != float(st.session_state.settings.get("volume_change_min", "100")):
        st.session_state.settings["volume_change_min"] = str(volume_change_min)
        save_settings(st.session_state.settings)
    
    max_slippage = st.number_input("슬리피지 최대 (%)", min_value=0.0, max_value=10.0, 
                                  value=float(st.session_state.settings.get("slippage", "0.3")), 
                                  step=0.1, key="slippage_input")
    if max_slippage != float(st.session_state.settings.get("slippage", "0.3")):
        st.session_state.settings["slippage"] = str(max_slippage)
        save_settings(st.session_state.settings)
    
    max_spread = st.number_input("호가스프레드 최대 (%)", min_value=0.0, max_value=10.0, 
                                 value=float(st.session_state.settings.get("max_spread", "0.2")), 
                                 step=0.1, key="spread_input",
                                 help="호가 스프레드가 이 값보다 큰 코인은 필터링에서 제외됩니다")
    if max_spread != float(st.session_state.settings.get("max_spread", "0.2")):
        st.session_state.settings["max_spread"] = str(max_spread)
        save_settings(st.session_state.settings)
    
    # 일봉 필터링
    enable_day_candle_filter = st.checkbox("일봉 필터링", 
                                           value=st.session_state.settings.get("day_candle_filter", False), 
                                           help="최근 일봉 10개 중 양봉 40% 이상인 코인만 선별",
                                           key="day_candle_check")
    if enable_day_candle_filter != st.session_state.settings.get("day_candle_filter", False):
        st.session_state.settings["day_candle_filter"] = enable_day_candle_filter
        save_settings(st.session_state.settings)
    
    # 제외 코인
    exclude_coins = st.text_input("제외 코인", 
                                  value=st.session_state.settings.get("exclude_coins", ""), 
                                  help="콤마로 구분 (예: BTC,ETH,ONDO)",
                                  key="exclude_input")
    if exclude_coins != st.session_state.settings.get("exclude_coins", ""):
        st.session_state.settings["exclude_coins"] = exclude_coins
        save_settings(st.session_state.settings)
    
    st.markdown("---")
    
    # 자동매매 설정
    st.subheader("💎 자동매매 (프리미엄)")
    enable_auto_trade = st.checkbox("자동매매 활성화", 
                                    value=st.session_state.settings.get("auto_trade", False),
                                    key="auto_trade_check")
    if enable_auto_trade != st.session_state.settings.get("auto_trade", False):
        st.session_state.settings["auto_trade"] = enable_auto_trade
        save_settings(st.session_state.settings)
    
    if enable_auto_trade:
        sell_percentage = st.number_input("지정가 매도 (%)", min_value=0.0, max_value=100.0, 
                                         value=float(st.session_state.settings.get("sell_percentage", "3")), 
                                         step=0.1, key="sell_pct_input")
        if sell_percentage != float(st.session_state.settings.get("sell_percentage", "3")):
            st.session_state.settings["sell_percentage"] = str(sell_percentage)
            save_settings(st.session_state.settings)
        
        sell_ratio_options = ["전부", "절반", "3분의 1"]
        sell_ratio_default = sell_ratio_options.index(st.session_state.settings.get("sell_ratio", "절반")) if st.session_state.settings.get("sell_ratio", "절반") in sell_ratio_options else 1
        sell_ratio = st.selectbox("매도 비중", sell_ratio_options, index=sell_ratio_default, key="sell_ratio_select")
        if sell_ratio != st.session_state.settings.get("sell_ratio", "절반"):
            st.session_state.settings["sell_ratio"] = sell_ratio
            save_settings(st.session_state.settings)
        
        investment_ratio = st.number_input("투자 비중 (%)", min_value=0.0, max_value=100.0, 
                                          value=float(st.session_state.settings.get("investment_ratio", "100")), 
                                          step=1.0, key="investment_input")
        if investment_ratio != float(st.session_state.settings.get("investment_ratio", "100")):
            st.session_state.settings["investment_ratio"] = str(investment_ratio)
            save_settings(st.session_state.settings)
        
        max_coins = st.number_input("최대 허용 코인개수", min_value=1, max_value=50, 
                                    value=int(st.session_state.settings.get("max_coins", "10")), 
                                    step=1, key="max_coins_input")
        if max_coins != int(st.session_state.settings.get("max_coins", "10")):
            st.session_state.settings["max_coins"] = str(max_coins)
            save_settings(st.session_state.settings)
        
        stop_loss = st.number_input("손절 (%)", min_value=0.0, max_value=50.0, 
                                   value=float(st.session_state.settings.get("stop_loss", "5")), 
                                   step=0.1, key="stop_loss_input")
        if stop_loss != float(st.session_state.settings.get("stop_loss", "5")):
            st.session_state.settings["stop_loss"] = str(stop_loss)
            save_settings(st.session_state.settings)
        
        # 종료 시간 (상대 시간)
        end_hours_options = [1, 2, 3, 4, 5, 6, 8, 12, 24]
        end_hours_default = int(st.session_state.settings.get("end_hours", "2"))
        if end_hours_default not in end_hours_options:
            end_hours_default = 2
        end_hours_index = end_hours_options.index(end_hours_default)
        end_hours = st.selectbox("자동 종료 시간", 
                                options=end_hours_options, 
                                format_func=lambda x: f"{x}시간 후",
                                index=end_hours_index,
                                key="end_hours_select",
                                help="매수 후 지정된 시간이 지나면 자동으로 전량 매도합니다")
        if end_hours != int(st.session_state.settings.get("end_hours", "2")):
            st.session_state.settings["end_hours"] = str(end_hours)
            save_settings(st.session_state.settings)
    
    st.markdown("---")
    
    # 실행 버튼
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    with col_btn1:
        if st.button("🚀 분석 시작", type="primary", use_container_width=True):
            if not st.session_state.run_analysis:
                # 현재 시간을 기준으로 target_hour, target_minute 설정
                now = get_kst_now()
                target_hour = now.hour
                target_minute = now.minute
                
                # 분석 파라미터 설정
                analysis_params = {
                    'interval_minutes': int(interval_minutes),
                    'target_hour': target_hour,
                    'target_minute': target_minute,
                    'max_slippage': float(max_slippage),
                    'price_change_min': float(price_change_min),
                    'price_change_max': float(price_change_max),
                    'volume_change_min': float(volume_change_min),
                    'enable_day_candle_filter': enable_day_candle_filter,
                    'exclude_coins': exclude_coins,
                    'enable_auto_trade': enable_auto_trade,
                    'sell_percentage': float(sell_percentage) if enable_auto_trade else 3.0,
                    'sell_ratio': sell_ratio if enable_auto_trade else "절반",
                    'investment_ratio': float(investment_ratio) if enable_auto_trade else 100.0,
                    'max_coins': int(max_coins) if enable_auto_trade else 10,
                    'max_spread': float(max_spread),
                    'end_hours': int(end_hours) if enable_auto_trade else 2,
                    'stop_loss': float(stop_loss) if enable_auto_trade else 5.0
                }
                
                # 설정값 로그 출력 (StreamlitLogger는 분석 실행 부분에서 정의되므로 여기서는 직접 로그 추가)
                if 'logs' not in st.session_state:
                    st.session_state.logs = []
                
                timestamp = get_kst_now().strftime("%H:%M:%S")
                st.session_state.logs.append("=" * 60)
                st.session_state.logs.append(f"[{timestamp}] [INFO] 📋 분석 설정값 확인")
                st.session_state.logs.append("=" * 60)
                st.session_state.logs.append(f"[{timestamp}] [INFO] 분봉: {interval_minutes}분봉")
                st.session_state.logs.append(f"[{timestamp}] [INFO] 가격 변동률: {price_change_min}% ~ {price_change_max}%")
                st.session_state.logs.append(f"[{timestamp}] [INFO] 거래량 변동 최소: {volume_change_min}%")
                st.session_state.logs.append(f"[{timestamp}] [INFO] 슬리피지 최대: {max_slippage}%")
                st.session_state.logs.append(f"[{timestamp}] [INFO] 호가스프레드 최대: {max_spread}%")
                st.session_state.logs.append(f"[{timestamp}] [INFO] 일봉 필터링: {'활성화' if enable_day_candle_filter else '비활성화'}")
                if exclude_coins:
                    st.session_state.logs.append(f"[{timestamp}] [INFO] 제외 코인: {exclude_coins}")
                if enable_auto_trade:
                    st.session_state.logs.append(f"[{timestamp}] [INFO] 자동매매: 활성화")
                    st.session_state.logs.append(f"[{timestamp}] [INFO]   - 지정가 매도: {sell_percentage}%")
                    st.session_state.logs.append(f"[{timestamp}] [INFO]   - 매도 비중: {sell_ratio}")
                    st.session_state.logs.append(f"[{timestamp}] [INFO]   - 투자 비중: {investment_ratio}%")
                    st.session_state.logs.append(f"[{timestamp}] [INFO]   - 최대 코인 개수: {max_coins}개")
                    st.session_state.logs.append(f"[{timestamp}] [INFO]   - 손절: {stop_loss}%")
                    st.session_state.logs.append(f"[{timestamp}] [INFO]   - 자동 종료: {end_hours}시간 후")
                else:
                    st.session_state.logs.append(f"[{timestamp}] [INFO] 자동매매: 비활성화")
                st.session_state.logs.append("=" * 60)
                
                st.session_state.run_analysis = True
                st.session_state.analysis_params = analysis_params
                st.rerun()
            else:
                st.warning("⚠️ 이미 분석이 실행 중입니다.")
    with col_btn2:
        if st.button("🗑️ 로그 초기화", use_container_width=True):
            if 'logs' in st.session_state:
                st.session_state.logs = []
            st.success("✅ 로그가 초기화되었습니다.")
            st.rerun()
    with col_btn3:
        if st.button("🔄 상태 초기화", use_container_width=True):
            st.session_state.run_analysis = False
            if 'analysis_params' in st.session_state:
                del st.session_state.analysis_params
            if 'purchased_coins' in st.session_state:
                st.session_state.purchased_coins = {}
            st.success("✅ 상태가 초기화되었습니다.")
            st.rerun()

# 메인 영역
# 큐에서 분석 실행 메시지 확인 (메인 영역에서도 확인 - 우선순위 높음)
# 이 부분은 매 렌더링마다 실행되므로 큐 메시지를 놓치지 않음
if st.session_state.scheduler_running:
    try:
        while True:
            msg_type, data = st.session_state.analysis_queue.get_nowait()
            if msg_type == 'start_analysis':
                st.session_state.run_analysis = True
                st.session_state.analysis_params = data
                # 로그에 기록
                if 'logs' in st.session_state:
                    log_msg = f"[{get_kst_now().strftime('%H:%M:%S')}] [SUCCESS] 큐에서 분석 실행 메시지 수신! 분석을 시작합니다."
                    st.session_state.logs.append(log_msg)
                # st.rerun()을 호출하여 즉시 분석 시작
                st.rerun()
    except queue.Empty:
        pass

# 분석 실행 확인
if st.session_state.run_analysis and 'analysis_params' in st.session_state:
    # 분석 파라미터 가져오기
    params = st.session_state.analysis_params
    interval_minutes = params['interval_minutes']
    target_hour = params['target_hour']
    target_minute = params['target_minute']
    max_slippage = params['max_slippage']
    price_change_min = params['price_change_min']
    price_change_max = params['price_change_max']
    volume_change_min = params['volume_change_min']
    enable_day_candle_filter = params['enable_day_candle_filter']
    exclude_coins = params['exclude_coins']
    enable_auto_trade = params['enable_auto_trade']
    sell_percentage = params['sell_percentage']
    sell_ratio = params['sell_ratio']
    investment_ratio = params['investment_ratio']
    max_coins = params['max_coins']
    max_spread = params['max_spread']
    
    # 진행 상황 표시
    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.container()
    
    # 로그를 저장할 리스트
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    
    # 간단한 로거 클래스 (기존 logger 인터페이스와 호환)
    class StreamlitLogger:
        def __init__(self):
            if 'logs' not in st.session_state:
                st.session_state.logs = []
        
        def log(self, message, level="INFO"):
            timestamp = get_kst_now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] [{level}] {message}"
            st.session_state.logs.append(log_entry)
    
    logger = StreamlitLogger()
    
    try:
        # 설정값 변환
        sell_ratio_map = {"전부": 1.0, "절반": 0.5, "3분의 1": 1.0/3.0}
        sell_ratio_value = sell_ratio_map.get(sell_ratio, 0.5) if enable_auto_trade else 0.5
        
        # 제외 코인 리스트 변환
        exclude_list = []
        if exclude_coins:
            exclude_list = [s.strip() for s in exclude_coins.split(',') if s.strip()]
        
        # 1단계: 원화마켓 코인 수집
        status_text.text("1단계: 원화마켓 코인 수집 중...")
        progress_bar.progress(10)
        coins = get_all_upbit_coins(logger=logger, exclude_coins=exclude_list)
        
        # 로그 표시
        with log_container:
            st.text_area("로그", "\n".join(st.session_state.logs[-50:]), height=300, key="log_area")
        
        # 2단계: 거래대금 필터링
        status_text.text("2단계: 거래대금 필터링 중...")
        progress_bar.progress(30)
        final_filtered_coins = print_coins_under_price_and_volume(
            coins,
            max_price=None,
            min_volume=1000000000,
            interval_minutes=interval_minutes,
            target_hour=target_hour,
            target_minute=target_minute,
            logger=logger,
            stop_event=None  # Streamlit에서는 threading.Event 불필요
        )
        
        with log_container:
            st.text_area("로그", "\n".join(st.session_state.logs[-50:]), height=300, key="log_area2")
        
        if final_filtered_coins:
            # 3단계: 분봉 데이터 분석
            status_text.text("3단계: 분봉 데이터 분석 중...")
            progress_bar.progress(50)
            rising_coins = print_3minute_candles(
                final_filtered_coins,
                interval_minutes=interval_minutes,
                target_hour=target_hour,
                logger=logger
            )
            
            with log_container:
                st.text_area("로그", "\n".join(st.session_state.logs[-50:]), height=300, key="log_area3")
            
            if rising_coins:
                # 4단계: 가격/거래량 변동률 필터링
                status_text.text("4단계: 가격/거래량 변동률 필터링 중...")
                progress_bar.progress(60)
                filtered_coins = print_filtered_coins_by_price_volume(
                    rising_coins,
                    price_change_min=price_change_min,
                    price_change_max=price_change_max,
                    volume_change_min=volume_change_min,
                    logger=logger
                )
                
                with log_container:
                    st.text_area("로그", "\n".join(st.session_state.logs[-50:]), height=300, key="log_area4")
                
                if filtered_coins:
                    # 5단계: 시장가 매수 분석
                    status_text.text("5단계: 시장가 매수 분석 중...")
                    progress_bar.progress(70)
                    analysis_results = print_all_coins_market_buy_analysis(
                        filtered_coins,
                        buy_amount=10000000,
                        max_spread=max_spread,
                        logger=logger
                    )
                    
                    with log_container:
                        st.text_area("로그", "\n".join(st.session_state.logs[-50:]), height=300, key="log_area5")
                    
                    if analysis_results:
                        # 6단계: 슬리피지 필터링
                        status_text.text("6단계: 슬리피지 필터링 중...")
                        progress_bar.progress(80)
                        filtered_results = print_filtered_by_slippage(
                            analysis_results,
                            max_slippage=max_slippage,
                            logger=logger,
                            root=None,
                            skip_csv_and_popup=True
                        )
                        
                        with log_container:
                            st.text_area("로그", "\n".join(st.session_state.logs[-50:]), height=300, key="log_area6")
                        
                        # 7단계: 일봉 필터링 (선택사항)
                        if filtered_results and enable_day_candle_filter:
                            status_text.text("7단계: 일봉 필터링 중...")
                            progress_bar.progress(90)
                            filtered_results = filter_by_day_candle(
                                filtered_results,
                                min_bullish_ratio=0.4,
                                logger=logger,
                                stop_event=None  # Streamlit에서는 threading.Event 불필요
                            )
                        
                        if filtered_results:
                            progress_bar.progress(100)
                            status_text.text("✅ 분석 완료!")
                            
                            # 결과를 DataFrame으로 변환
                            results_data = []
                            for idx, result in enumerate(filtered_results, 1):
                                coin = result.get('coin', '').replace("KRW-", "")
                                day_candle_pass = result.get('day_candle_pass', False)
                                day_filter = "O" if day_candle_pass else "X"
                                
                                results_data.append({
                                    '순위': idx,
                                    '코인': coin,
                                    '일봉필터링': day_filter,
                                    '가격변동률': f"+{result.get('price_change', 0):.2f}%",
                                    '거래량변동률': f"+{result.get('volume_change', 0):.2f}%",
                                    '최저매도가': f"{result.get('lowest_ask', 0):,.0f}원",
                                    '평균매수가': f"{result.get('avg_price', 0):,.0f}원",
                                    '슬리피지': f"{result.get('price_diff_pct', 0):.4f}%",
                                    '호가스프레드': f"{result.get('spread_pct', 0):.4f}%",
                                    '소진호가수': f"{result.get('filled_asks_count', 0)}개"
                                })
                            
                            df_results = pd.DataFrame(results_data)
                            
                            # 결과 표시
                            st.markdown("---")
                            st.subheader("📊 필터링 결과")
                            st.dataframe(df_results, use_container_width=True)
                            
                            # CSV 다운로드
                            csv = df_results.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                label="📥 CSV 다운로드",
                                data=csv,
                                file_name=f"slippage_results_{get_kst_now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv"
                            )
                            
                            # 자동매매가 비활성화된 경우 분석 완료 후 자동 중지
                            if not enable_auto_trade:
                                st.success("✅ 분석이 완료되었습니다!")
                                st.info("💡 다시 분석하려면 '분석 시작' 버튼을 클릭하세요.")
                                # 분석 완료 후 자동으로 프로그램 중지 (로그는 유지)
                                st.session_state.run_analysis = False
                                if 'analysis_params' in st.session_state:
                                    del st.session_state.analysis_params
                            
                            # 자동매매 실행
                            if enable_auto_trade and filtered_results:
                                st.markdown("---")
                                st.subheader("💎 자동매매")
                                
                                # 일봉 필터링이 활성화된 경우 통과한 코인만 매수
                                if enable_day_candle_filter:
                                    coins_to_buy = [r for r in filtered_results if r.get('day_candle_pass', False)]
                                else:
                                    coins_to_buy = filtered_results
                                
                                if coins_to_buy:
                                    st.info(f"매수 대상 코인: {len(coins_to_buy)}개")
                                    
                                    # 자동매매가 활성화된 경우 자동으로 실행
                                    try:
                                        api_key, secret_key = load_api_keys_from_json()
                                        if api_key and secret_key:
                                            import pyupbit
                                            upbit = pyupbit.Upbit(api_key, secret_key)
                                            
                                            # purchased_coins_dict 초기화
                                            if 'purchased_coins' not in st.session_state:
                                                st.session_state.purchased_coins = {}
                                            
                                            with st.spinner("매수 주문 실행 중..."):
                                                buy_coins_from_list(
                                                    upbit,
                                                    coins_to_buy,
                                                    sell_percentage=sell_percentage,
                                                    sell_ratio=sell_ratio_value,
                                                    investment_ratio=investment_ratio,
                                                    max_coins=max_coins,
                                                    logger=logger,
                                                    purchased_coins_dict=st.session_state.purchased_coins
                                                )
                                            
                                            st.success("✅ 매수 주문이 완료되었습니다!")
                                            
                                            # 자동 종료 스레드 시작
                                            if st.session_state.purchased_coins and enable_auto_trade:
                                                end_hours = params.get('end_hours', 2)
                                                
                                                # 스레드에서 사용할 변수들 (스레드 안전)
                                                purchased_coins_copy = dict(st.session_state.purchased_coins)
                                                
                                                def auto_sell_thread(coins_dict, end_hours_value, upbit_obj, logger_obj):
                                                    """지정된 시간 후 자동 매도 (스레드 안전 버전)"""
                                                    import time
                                                    from datetime import datetime, timedelta
                                                    
                                                    # 종료 시간 계산
                                                    end_time = get_kst_now() + timedelta(hours=end_hours_value)
                                                    
                                                    # 로그에 기록 (logger 사용)
                                                    if logger_obj:
                                                        log_msg = f"[{get_kst_now().strftime('%H:%M:%S')}] [INFO] 자동 종료 예정 시간: {end_time.strftime('%H:%M:%S')} ({end_hours_value}시간 후)"
                                                        logger_obj.log(log_msg, "INFO")
                                                    
                                                    # 종료 시간까지 대기
                                                    while get_kst_now() < end_time:
                                                        remaining = end_time - get_kst_now()
                                                        hours = int(remaining.total_seconds() // 3600)
                                                        minutes = int((remaining.total_seconds() % 3600) // 60)
                                                        seconds = int(remaining.total_seconds() % 60)
                                                        
                                                        # 매 10초마다 카운트다운 로그
                                                        if seconds % 10 == 0:
                                                            if logger_obj:
                                                                countdown_msg = f"[{get_kst_now().strftime('%H:%M:%S')}] [INFO] 자동 종료까지 남은 시간: {hours:02d}시간 {minutes:02d}분 {seconds:02d}초"
                                                                logger_obj.log(countdown_msg, "INFO")
                                                        
                                                        time.sleep(1)
                                                        
                                                        # purchased_coins가 비어있으면 종료
                                                        if not coins_dict:
                                                            break
                                                    
                                                    # 종료 시간 도달 - 자동 매도
                                                    if coins_dict:
                                                        try:
                                                            if logger_obj:
                                                                log_msg = f"[{get_kst_now().strftime('%H:%M:%S')}] [INFO] 자동 종료 시간 도달! 전량 매도 시작..."
                                                                logger_obj.log(log_msg, "INFO")
                                                            
                                                            # utils에서 cancel_all_orders_and_sell_all 함수 import
                                                            from utils import cancel_all_orders_and_sell_all
                                                            
                                                            # 매도할 코인 목록 복사 (스레드 안전)
                                                            coins_to_sell = list(coins_dict.keys())
                                                            
                                                            for coin in coins_to_sell:
                                                                cancel_all_orders_and_sell_all(
                                                                    upbit_obj,
                                                                    coin,
                                                                    logger=logger_obj,
                                                                    return_sell_price=True
                                                                )
                                                            
                                                            if logger_obj:
                                                                log_msg = f"[{get_kst_now().strftime('%H:%M:%S')}] [SUCCESS] 자동 종료 매도 완료!"
                                                                logger_obj.log(log_msg, "SUCCESS")
                                                            
                                                            # purchased_coins 초기화 (메인 스레드에서 처리하도록 큐 사용)
                                                            # 스레드 내에서는 직접 수정하지 않음
                                                        except Exception as e:
                                                            if logger_obj:
                                                                error_msg = f"[{get_kst_now().strftime('%H:%M:%S')}] [ERROR] 자동 종료 매도 중 오류: {e}"
                                                                logger_obj.log(error_msg, "ERROR")
                                                
                                                # 자동 종료 스레드 시작
                                                auto_sell_thread_obj = threading.Thread(
                                                    target=auto_sell_thread,
                                                    args=(purchased_coins_copy, end_hours, upbit, logger),
                                                    daemon=True
                                                )
                                                auto_sell_thread_obj.start()
                                                st.info(f"⏰ {end_hours}시간 후 자동으로 전량 매도됩니다.")
                                            
                                            # 최종 로그 표시
                                            with log_container:
                                                st.text_area("전체 로그", "\n".join(st.session_state.logs), height=400, key="log_area_final_success")
                                            
                                            # 매수 주문 완료 후 자동으로 프로그램 중지 (로그는 유지)
                                            st.success("✅ 분석 및 매수 주문이 완료되었습니다!")
                                            st.info("💡 다시 분석하려면 '분석 시작' 버튼을 클릭하세요.")
                                            st.session_state.run_analysis = False
                                            if 'analysis_params' in st.session_state:
                                                del st.session_state.analysis_params
                                        else:
                                            st.error("❌ API 키를 불러올 수 없습니다. 현재 디렉토리에 api.json 파일을 확인하세요.")
                                            # API 키 오류 후에도 분석 완료로 처리 (로그는 유지)
                                            st.session_state.run_analysis = False
                                            if 'analysis_params' in st.session_state:
                                                del st.session_state.analysis_params
                                    except Exception as e:
                                        st.error(f"❌ 매수 주문 실행 중 오류 발생: {e}")
                                        import traceback
                                        st.code(traceback.format_exc())
                                        # 오류 발생 후에도 분석 완료로 처리 (로그는 유지)
                                        st.session_state.run_analysis = False
                                        if 'analysis_params' in st.session_state:
                                            del st.session_state.analysis_params
                                else:
                                    if enable_day_candle_filter:
                                        st.warning("⚠️ 매수할 코인이 없습니다. (일봉 필터링 미통과)")
                                    else:
                                        st.warning("⚠️ 매수할 코인이 없습니다.")
                                    # 매수할 코인이 없어도 분석 완료로 처리 (로그는 유지)
                                    st.session_state.run_analysis = False
                                    if 'analysis_params' in st.session_state:
                                        del st.session_state.analysis_params
                            else:
                                # 자동매매가 활성화되었지만 필터링 결과가 없는 경우
                                st.warning("⚠️ 자동매매할 코인이 없습니다.")
                                st.session_state.run_analysis = False
                                if 'analysis_params' in st.session_state:
                                    del st.session_state.analysis_params
                        else:
                            st.warning("슬리피지 필터링 결과가 없습니다.")
                            # 분석 완료 후 자동으로 프로그램 중지 (로그는 유지)
                            st.session_state.run_analysis = False
                            if 'analysis_params' in st.session_state:
                                del st.session_state.analysis_params
                    else:
                        st.warning("시장가 매수 분석 결과가 없습니다.")
                        # 분석 완료 후 자동으로 프로그램 중지 (로그는 유지)
                        st.session_state.run_analysis = False
                        if 'analysis_params' in st.session_state:
                            del st.session_state.analysis_params
                else:
                    st.warning("가격/거래량 변동률 필터링 결과가 없습니다.")
                    # 분석 완료 후 자동으로 프로그램 중지 (로그는 유지)
                    st.session_state.run_analysis = False
                    if 'analysis_params' in st.session_state:
                        del st.session_state.analysis_params
            else:
                st.warning("분봉 데이터 분석 결과가 없습니다.")
                # 분석 완료 후 자동으로 프로그램 중지 (로그는 유지)
                st.session_state.run_analysis = False
                if 'analysis_params' in st.session_state:
                    del st.session_state.analysis_params
        else:
            st.warning("거래대금 필터링 결과가 없습니다.")
            # 분석 완료 후 자동으로 프로그램 중지 (로그는 유지)
            st.session_state.run_analysis = False
            if 'analysis_params' in st.session_state:
                del st.session_state.analysis_params
    except Exception as e:
        st.error(f"❌ 오류 발생: {e}")
        import traceback
        st.code(traceback.format_exc())
        
        # 에러 발생 시에도 로그 표시
        if 'logs' in st.session_state:
            with log_container:
                st.text_area("전체 로그", "\n".join(st.session_state.logs), height=400, key="log_area_error")
        
        # 오류 발생 후에도 분석 완료로 처리 (로그는 유지)
        st.session_state.run_analysis = False
        if 'analysis_params' in st.session_state:
            del st.session_state.analysis_params
    
    # 로그 최종 표시
    with log_container:
        st.text_area("전체 로그", "\n".join(st.session_state.logs), height=400, key="log_area_final")

# 코인 필터링 결과 보기
if st.session_state.show_slippage_results:
    st.session_state.show_slippage_results = False
    
    # 데이터 저장 디렉토리 (Railway Volume 지원)
    data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
    csv_files = glob.glob(os.path.join(data_dir, "slippage_results_*.csv"))
    
    if not csv_files:
        st.warning("저장된 코인 필터링 결과가 없습니다.")
    else:
        # 파일명에서 날짜 추출하여 정렬 (최신순)
        def extract_date(filename):
            try:
                parts = filename.replace("slippage_results_", "").replace(".csv", "").split("_")
                if len(parts) >= 2:
                    date_str = parts[0]
                    time_str = parts[1]
                    return (date_str, time_str)
                return ("", "")
            except:
                return ("", "")
        
        csv_files.sort(key=lambda x: extract_date(x), reverse=True)
        
        def format_filename(filename):
            try:
                # 전체 경로에서 파일명만 추출
                basename = os.path.basename(filename)
                base = basename.replace("slippage_results_", "").replace(".csv", "")
                if "_" in base:
                    parts = base.split("_")
                    date_str = parts[0]
                    time_str = parts[1] if len(parts) > 1 else "000000"
                else:
                    date_str = base
                    time_str = "000000"
                
                if len(date_str) == 8:
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    if len(time_str) == 6:
                        hour = time_str[:2]
                        minute = time_str[2:4]
                        return f"{year}-{month}-{day} {hour}:{minute}"
                    return f"{year}-{month}-{day}"
                return filename
            except:
                return filename
        
        file_options = [format_filename(f) for f in csv_files]
        selected_index = st.selectbox("표시할 코인 필터링 결과를 선택하세요:", range(len(file_options)), 
                                      format_func=lambda x: file_options[x], key="slippage_file_select")
        
        if selected_index is not None:
            selected_file = csv_files[selected_index]
            max_slippage = float(st.session_state.settings.get("slippage", "0.3"))
            
            try:
                from utils import _get_auto_trading_module
                module = _get_auto_trading_module()
                get_slippage_result_html = module.get_slippage_result_html
                
                filtered_results = []
                with open(selected_file, 'r', encoding='utf-8-sig') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        filtered_results.append({
                            'coin': f"KRW-{row['코인']}",
                            'coin_symbol': row['코인'],
                            'price_change': float(row['가격변동률'].replace('%', '').replace('+', '')),
                            'volume_change': float(row['거래량변동률'].replace('%', '').replace('+', '')),
                            'lowest_ask': float(row['최저매도가'].replace('원', '').replace(',', '')),
                            'avg_price': float(row['평균매수가'].replace('원', '').replace(',', '')),
                            'price_diff_pct': float(row['슬리피지'].replace('%', '').replace('+', '').replace('-', '')),
                            'spread_pct': float(row.get('호가스프레드', '0').replace('%', '').replace('+', '').replace('-', '')) if '호가스프레드' in row else 0,
                            'filled_count': int(row['소진호가수'].replace('개', ''))
                        })
                
                if filtered_results:
                    html_content = get_slippage_result_html(filtered_results, max_slippage, selected_file)
                    if html_content:
                        temp_file = os.path.join(tempfile.gettempdir(), f'slippage_results_{get_kst_now().strftime("%Y%m%d_%H%M%S")}.html')
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        
                        if os.name == 'nt':
                            file_url = f'file:///{temp_file.replace(os.sep, "/")}'
                        else:
                            file_url = f'file://{temp_file}'
                        
                        webbrowser.open(file_url)
                        st.success(f"코인 필터링 결과를 브라우저에서 열었습니다. (슬리피지: {max_slippage}%)")
            except Exception as e:
                st.error(f"코인 필터링 결과 표시 오류: {e}")
                import traceback
                st.code(traceback.format_exc())

# 수익률 보기
if st.session_state.show_profit_results:
    st.session_state.show_profit_results = False
    
    profit_results = []
    
    if 'sold_coins' in st.session_state and st.session_state.sold_coins:
        for coin, info in st.session_state.sold_coins.items():
            profit_results.append({
                'coin': coin,
                'buy_price': info.get('buy_price', 0),
                'sell_price': info.get('sell_price', 0),
                'buy_amount': info.get('buy_amount', 0),
                'sell_amount': info.get('sell_amount', 0),
                'profit_pct': info.get('profit_pct', 0),
                'profit_amount': info.get('profit_amount', 0)
            })
    
    if not profit_results:
        # 데이터 저장 디렉토리 (Railway Volume 지원)
        data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
        csv_files = glob.glob(os.path.join(data_dir, "profit_results_*.csv"))
        
        if not csv_files:
            st.warning("당일 매매 수익률 데이터가 없습니다.")
        else:
            def extract_date(filename):
                try:
                    # 전체 경로에서 파일명만 추출
                    basename = os.path.basename(filename)
                    base = basename.replace("profit_results_", "").replace(".csv", "")
                    if "_" in base:
                        parts = base.split("_")
                        date_str = parts[0]
                        time_str = parts[1] if len(parts) > 1 else "000000"
                        return (date_str, time_str)
                    else:
                        return (base, "000000")
                except:
                    return ("", "")
            
            csv_files.sort(key=lambda x: extract_date(x), reverse=True)
            
            def format_filename(filename):
                try:
                    # 전체 경로에서 파일명만 추출
                    basename = os.path.basename(filename)
                    base = basename.replace("profit_results_", "").replace(".csv", "")
                    if "_" in base:
                        parts = base.split("_")
                        date_str = parts[0]
                        time_str = parts[1] if len(parts) > 1 else "000000"
                    else:
                        date_str = base
                        time_str = "000000"
                    
                    if len(date_str) == 8:
                        year = date_str[:4]
                        month = date_str[4:6]
                        day = date_str[6:8]
                        if len(time_str) == 6:
                            hour = time_str[:2]
                            minute = time_str[2:4]
                            return f"{year}-{month}-{day} {hour}:{minute}"
                        return f"{year}-{month}-{day}"
                    return filename
                except:
                    return filename
            
            file_options = [format_filename(f) for f in csv_files]
            selected_index = st.selectbox("표시할 당일 매매 수익률을 선택하세요:", range(len(file_options)),
                                          format_func=lambda x: file_options[x], key="profit_file_select")
            
            if selected_index is not None:
                selected_file = csv_files[selected_index]
                
                with open(selected_file, 'r', encoding='utf-8-sig') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        coin = row['코인']
                        profit_results.append({
                            'coin': f"KRW-{coin}",
                            'buy_price': float(row['매수가'].replace(',', '')),
                            'sell_price': float(row['매도가'].replace(',', '')),
                            'buy_amount': float(row['매수금액'].replace(',', '')),
                            'sell_amount': float(row['매도금액'].replace(',', '')),
                            'profit_pct': float(row['수익률'].replace('%', '')),
                            'profit_amount': float(row['수익금액'].replace(',', ''))
                        })
    
    if profit_results:
        try:
            from utils import _get_auto_trading_module
            module = _get_auto_trading_module()
            get_profit_result_html = module.get_profit_result_html
            
            html_content = get_profit_result_html(profit_results)
            if html_content:
                temp_file = os.path.join(tempfile.gettempdir(), f'profit_results_{get_kst_now().strftime("%Y%m%d_%H%M%S")}.html')
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                if os.name == 'nt':
                    file_url = f'file:///{temp_file.replace(os.sep, "/")}'
                else:
                    file_url = f'file://{temp_file}'
                
                webbrowser.open(file_url)
                st.success(f"당일 매매 수익률을 브라우저에서 열었습니다. (총 {len(profit_results)}개 코인)")
        except Exception as e:
            st.error(f"수익률 표시 오류: {e}")
            import traceback
            st.code(traceback.format_exc())

else:
    st.info("👈 사이드바에서 설정을 입력하고 '분석 시작' 버튼을 클릭하세요.")
    st.markdown("""
    ### 사용 방법
    1. 사이드바에서 필터링 조건을 설정합니다.
    2. '분석 시작' 버튼을 클릭합니다.
    3. 결과가 표시되면 CSV로 다운로드할 수 있습니다.
    4. 자동매매가 활성화된 경우 매수 실행 버튼이 나타납니다.
    """)
