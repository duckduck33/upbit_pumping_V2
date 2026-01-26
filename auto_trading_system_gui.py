# -*- coding: utf-8 -*-
"""
업비트 자동 매매 시스템 (GUI 버전)

GUI를 통해 옵션을 설정하고 자동 매매를 실행하는 시스템입니다.
"""
import pyupbit
import time
import requests
import json
import re
import threading
import queue
import sys
import csv
import os
import tempfile
import webbrowser
from datetime import datetime, timedelta, timezone
import pytz
from rich.console import Console

# 한국 시간대 설정
KST = pytz.timezone('Asia/Seoul')

def get_kst_now():
    """한국 시간(KST)으로 현재 시간을 반환합니다."""
    return datetime.now(KST)
from rich.table import Table
from rich.panel import Panel
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox


# ============================================================================
# 설정 저장/로드 함수
# ============================================================================

CONFIG_FILE = "trading_config.json"

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
        "exclude_coins": ""
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_settings = json.load(f)
                # 기본값과 병합 (누락된 키가 있으면 기본값 사용)
                default_settings.update(saved_settings)
        except Exception as e:
            print(f"설정 파일 로드 오류: {e}")
    
    return default_settings

def save_settings(settings):
    """설정값을 파일에 저장합니다."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"설정 파일 저장 오류: {e}")


# ============================================================================
# 툴팁 클래스
# ============================================================================

class ToolTip:
    """위젯에 마우스를 올리면 툴팁을 표시하는 클래스"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<Button-1>", self.on_click)
        self.is_clicked = False
    
    def on_enter(self, event=None):
        """마우스가 위젯 위로 올라왔을 때"""
        if not self.is_clicked:
            self.show_tooltip()
    
    def on_leave(self, event=None):
        """마우스가 위젯에서 벗어났을 때"""
        if not self.is_clicked:
            self.hide_tooltip()
    
    def on_click(self, event=None):
        """위젯을 클릭했을 때"""
        if self.is_clicked:
            self.hide_tooltip()
            self.is_clicked = False
        else:
            self.show_tooltip()
            self.is_clicked = True
    
    def show_tooltip(self):
        """툴팁 표시"""
        # 위젯의 위치를 가져옴
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 20
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip_window, text=self.text, 
                        background="#ffffe0", relief="solid", borderwidth=1,
                        font=('맑은 고딕', 8), foreground='#333333',
                        padx=5, pady=3, justify=tk.LEFT)
        label.pack()
    
    def hide_tooltip(self):
        """툴팁 숨김"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None


# ============================================================================
# API 키 관리
# ============================================================================

def load_api_keys_from_json():
    """환경 변수 또는 api.json 파일에서 API 키를 읽어옵니다."""
    # 1. 환경 변수에서 먼저 확인 (Railway Secrets 우선)
    api_key = os.getenv("UPBIT_API_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")
    
    if api_key and secret_key:
        return api_key.strip(), secret_key.strip()
    
    # 2. api.json 파일에서 읽기
    try:
        # DATA_DIR 또는 현재 디렉토리에서 api.json 찾기
        data_dir = os.getenv("DATA_DIR", ".")
        api_json_path = os.path.join(data_dir, "api.json")
        
        # DATA_DIR에 없으면 현재 디렉토리에서 찾기
        if not os.path.exists(api_json_path):
            api_json_path = "api.json"
        
        with open(api_json_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # JSON 형식이 아닌 경우를 대비하여 정규식으로 추출
        api_key_match = re.search(r'apiKey\s*=\s*"([^"]+)"', content)
        secret_key_match = re.search(r'secretKey\s*=\s*"([^"]+)"', content)
        
        if api_key_match and secret_key_match:
            api_key = api_key_match.group(1).strip()
            secret_key = secret_key_match.group(1).strip()
            return api_key, secret_key
        else:
            # JSON 형식으로 시도
            data = json.loads(content)
            api_key = data.get("apiKey", "").strip()
            secret_key = data.get("secretKey", "").strip()
            return api_key, secret_key
    except Exception as e:
        return None, None


# ============================================================================
# 로그 출력 클래스 (GUI용)
# ============================================================================

class GUILogger:
    """GUI 텍스트 위젯에 로그를 출력하는 클래스"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.console = Console()
        
        # 기본 텍스트 색상을 초록색으로 설정
        self.text_widget.config(foreground="#00FF00", background="#000000", 
                               selectbackground="#FFFF00", selectforeground="#000000",
                               insertbackground="#00FF00")
        
        # 선택 영역 스타일 설정 (드래그 시 더 잘 보이도록)
        self.text_widget.tag_config("sel", background="#FFFF00", foreground="#000000")
    
    def log(self, message, level="INFO"):
        """로그 메시지를 GUI에 출력"""
        timestamp = get_kst_now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] [{level}] {message}\n"
        
        # GUI 스레드에서 실행되도록 보장
        if threading.current_thread() == threading.main_thread():
            self._append_log(log_message, level)
        else:
            self.text_widget.after(0, lambda: self._append_log(log_message, level))
    
    def _append_log(self, message, level):
        """로그를 텍스트 위젯에 추가"""
        start_pos = self.text_widget.index(tk.END)
        self.text_widget.insert(tk.END, message)
        end_pos = self.text_widget.index(tk.END)
        
        # 모든 텍스트를 초록색으로 설정
        self.text_widget.tag_add("default", start_pos, end_pos)
        self.text_widget.tag_config("default", foreground="#00FF00")
        
        self.text_widget.see(tk.END)
    
    def clear(self):
        """로그 창 지우기"""
        self.text_widget.delete(1.0, tk.END)


# ============================================================================
# 시간 대기 기능
# ============================================================================

def wait_until_target_time(target_hour, target_minute, interval_minutes, logger=None, stop_event=None):
    """
    지정된 시간 + 분봉 간격까지 대기합니다.
    예: 3분봉, 3시 00분 → 3시 3분에 분석 시작
    예: 1분봉, 3시 00분 → 3시 1분에 분석 시작
    """
    # 분석 시작 시간 = 기준 시간 + 분봉 간격
    analysis_hour = target_hour
    analysis_minute = target_minute + interval_minutes
    
    # 분이 60을 넘으면 시간 조정
    if analysis_minute >= 60:
        analysis_hour += analysis_minute // 60
        analysis_minute = analysis_minute % 60
        if analysis_hour >= 24:
            analysis_hour = analysis_hour % 24
    
    if logger:
        logger.log(f"기준 시간: {target_hour:02d}:{target_minute:02d}", "INFO")
        logger.log(f"분봉 간격: {interval_minutes}분", "INFO")
        logger.log(f"분석 시작 시간: {analysis_hour:02d}:{analysis_minute:02d} (기준 시간 + {interval_minutes}분)", "INFO")
        logger.log(f"현재 시간: {get_kst_now().strftime('%Y-%m-%d %H:%M:%S')} (KST)", "INFO")
    
    last_second = -1
    
    while True:
        # 중지 이벤트 확인
        if stop_event and stop_event.is_set():
            if logger:
                logger.log("대기가 중지되었습니다.", "WARNING")
            return False
        
        now = get_kst_now()
        current_hour = now.hour
        current_minute = now.minute
        current_second = now.second
        
        # 목표 시간 확인 (분석 시작 시간)
        if current_hour == analysis_hour and current_minute == analysis_minute:
            if logger:
                logger.log(f"분석 시작 시간 도달: {now.strftime('%Y-%m-%d %H:%M:%S')}", "SUCCESS")
                logger.log("프로세스를 시작합니다...", "INFO")
            return True
        
        # 목표 시간까지 남은 시간 계산
        target_time = now.replace(hour=analysis_hour, minute=analysis_minute, second=0, microsecond=0)
        
        # 현재 시간이 목표 시간 이후라면 다음 날로 설정
        if now > target_time:
            target_time += timedelta(days=1)
        
        remaining = target_time - now
        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        # 매 초마다 출력
        if current_second != last_second and logger:
            logger.log(f"대기 중... (남은 시간: {hours:02d}:{minutes:02d}:{seconds:02d})", "INFO")
            last_second = current_second
        
        time.sleep(0.1)


# ============================================================================
# 코인 데이터 수집 함수
# ============================================================================

def get_all_upbit_coins(logger=None, exclude_coins=None):
    """업비트 원화마켓에서 거래 가능한 모든 코인 목록을 가져옵니다.
    
    exclude_coins: 사용자가 제외하고 싶은 코인 심볼 리스트 (예: ["BTC", "ETH", "ONDO"])"""
    if logger:
        logger.log("원화마켓 코인 목록 수집 중...", "INFO")
    
    all_coins = pyupbit.get_tickers(fiat="KRW")
    filtered_coins = all_coins.copy()
    
    # 제외 코인 처리
    if exclude_coins:
        exclude_set = set()
        for symbol in exclude_coins:
            s = symbol.strip().upper()
            if not s:
                continue
            if not s.startswith("KRW-"):
                s = "KRW-" + s
            exclude_set.add(s)
        before_count = len(filtered_coins)
        filtered_coins = [coin for coin in filtered_coins if coin not in exclude_set]
        if logger:
            logger.log(f"제외 코인: {', '.join(sorted(exclude_set))}", "INFO")
            logger.log(f"제외 후 코인 개수: {len(filtered_coins)}개 (원래 {before_count}개)", "INFO")
    
    if logger:
        logger.log(f"총 {len(filtered_coins)}개 코인 발견", "SUCCESS")
    
    return filtered_coins


def print_all_coin_list(coins, logger=None):
    """원화마켓 코인 개수만 출력합니다."""
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log("1. 전체 원화마켓 코인 개수", "INFO")
        logger.log("=" * 60, "INFO")
        logger.log(f"총 코인 개수: {len(coins)}개", "SUCCESS")


def print_coins_under_price_and_volume(coins, max_price=None, min_volume=1000000000, 
                                       max_volume=None, interval_minutes=1, target_hour=9, target_minute=0, logger=None, stop_event=None):
    """거래대금 조건을 만족하는 코인 리스트를 출력하고, 1분봉 데이터도 함께 수집합니다.
    
    항상 1분봉만 사용하며, 정시 기준으로 비교합니다.
    예) 오후 7시면 6시59분봉과 7시00분봉 비교
    """
    if logger:
        logger.log("=" * 60, "INFO")
        if max_price:
            logger.log(f"2. 현재가 {max_price:,}원 이하 & 거래대금 {min_volume/100000000:,.0f}억원 이상", "INFO")
        else:
            logger.log(f"2. 거래대금 {min_volume/100000000:,.0f}억원 이상", "INFO")
        logger.log("=" * 60, "INFO")
        logger.log(f"1분봉 비교: {target_hour:02d}:{target_minute:02d} 기준 (정시)", "INFO")
    
    final_filtered_coins = []
    # ------------------------------------------------------------------------
    # 정시 기준 1분봉 비교
    # 예) 오후 7시면 6시59분봉과 7시00분봉 비교
    # ------------------------------------------------------------------------
    now_kst = get_kst_now()
    now = now_kst.replace(tzinfo=None)
    target_date = now.date()
    
    # 정시 기준: target_hour:00분봉과 (target_hour-1):59분봉 비교
    candle2_time = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    candle1_time = candle2_time - timedelta(minutes=1)  # 직전 1분봉
    
    if logger:
        logger.log(f"분석 구간:", "INFO")
        logger.log(f"  이전 1분봉: {candle1_time.strftime('%H:%M')}", "INFO")
        logger.log(f"  이후 1분봉: {candle2_time.strftime('%H:%M')}", "INFO")
        logger.log(f"가격, 거래대금 및 1분봉 정보 확인 중...", "INFO")
    
    # 배치로 현재가 조회 (100개씩)
    if logger:
        logger.log(f"현재가 배치 조회 중... (총 {len(coins)}개 코인)", "INFO")
    
    all_prices = {}
    batch_size = 100
    for i in range(0, len(coins), batch_size):
        if stop_event and stop_event.is_set():
            if logger:
                logger.log("프로세스가 중지되었습니다.", "WARNING")
            return []
        
        batch_coins = coins[i:i+batch_size]
        try:
            batch_prices = pyupbit.get_current_price(batch_coins)
            if isinstance(batch_prices, dict):
                all_prices.update(batch_prices)
            time.sleep(0.1)  # API 제한 고려
        except Exception:
            continue
    
    # 배치로 거래대금 조회
    if logger:
        logger.log(f"거래대금 배치 조회 중...", "INFO")
    
    all_tickers = {}
    batch_size = 100
    for i in range(0, len(coins), batch_size):
        if stop_event and stop_event.is_set():
            if logger:
                logger.log("프로세스가 중지되었습니다.", "WARNING")
            return []
        
        batch_coins = coins[i:i+batch_size]
        markets = ",".join(batch_coins)
        url = "https://api.upbit.com/v1/ticker"
        params = {"markets": markets}
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                ticker_list = response.json()
                for ticker in ticker_list:
                    market = ticker.get('market', '')
                    if market:
                        all_tickers[market] = ticker
            time.sleep(0.1)  # API 제한 고려
        except Exception:
            continue
    
    # 필터링 및 분봉 데이터 수집
    for idx, coin in enumerate(coins, 1):
        if stop_event and stop_event.is_set():
            if logger:
                logger.log("프로세스가 중지되었습니다.", "WARNING")
            return []
        
        try:
            # 현재가 확인 (이미 조회한 데이터 사용)
            current_price = all_prices.get(coin)
            if not current_price:
                continue
            
            # 현재가 필터링 (max_price가 설정된 경우에만)
            if max_price and current_price > max_price:
                continue
            
            # 거래대금 확인 (이미 조회한 데이터 사용)
            ticker = all_tickers.get(coin)
            if not ticker:
                continue
            
            acc_trade_price_24h = ticker.get('acc_trade_price_24h', 0)
            
            if acc_trade_price_24h and acc_trade_price_24h >= min_volume and (max_volume is None or acc_trade_price_24h <= max_volume):
                # 1분봉 데이터 가져오기 (정시 기준 비교)
                df_candle = None
                candle1 = None
                candle2 = None
                coin_info = {}
                
                try:
                    # 항상 1분봉만 사용 (충분히 넉넉하게 가져오기)
                    df_candle = pyupbit.get_ohlcv(coin, interval="minute1", count=200)
                    if df_candle is not None and not df_candle.empty:
                        target_date_df = df_candle[df_candle.index.date == target_date]
                        if not target_date_df.empty:
                            # 정시 기준: candle1_time(예: 18:59)과 candle2_time(예: 19:00)의 1분봉 직접 찾기
                            for idx_time in target_date_df.index:
                                if idx_time.hour == candle1_time.hour and idx_time.minute == candle1_time.minute:
                                    candle1 = target_date_df.loc[idx_time]
                                    break
                            
                            for idx_time in target_date_df.index:
                                if idx_time.hour == candle2_time.hour and idx_time.minute == candle2_time.minute:
                                    candle2 = target_date_df.loc[idx_time]
                                    break
                            
                            # 캔들 존재 여부 로그 출력
                            coin_symbol = coin.replace("KRW-", "")
                            if candle1 is None:
                                if logger:
                                    logger.log(f"  {coin_symbol}: candle1 ({candle1_time.strftime('%H:%M')}) 존재하지 않음", "WARNING")
                            if candle2 is None:
                                if logger:
                                    logger.log(f"  {coin_symbol}: candle2 ({candle2_time.strftime('%H:%M')}) 존재하지 않음", "WARNING")
                            
                            coin_info['df_candle'] = target_date_df
                except Exception as e:
                    if logger:
                        coin_symbol = coin.replace("KRW-", "")
                        logger.log(f"  {coin_symbol}: 캔들 데이터 조회 중 오류 - {e}", "ERROR")
                    pass
                
                final_filtered_coins.append({
                    'coin': coin,
                    'current_price': current_price,
                    'volume_24h': acc_trade_price_24h,
                    'candle1': candle1,
                    'candle2': candle2,
                    'df_candle': coin_info.get('df_candle') if 'df_candle' in coin_info else None
                })
                
                if logger and idx % 50 == 0:
                    logger.log(f"처리 중... ({idx}/{len(coins)})", "INFO")
        except Exception:
            continue
    
    if logger:
        logger.log(f"총 코인 개수: {len(final_filtered_coins)}개", "SUCCESS")
        logger.log(f"{'번호':<6} {'코인':<15} {'현재가':<20} {'거래대금(24h)':<20}", "INFO")
        logger.log("-" * 65, "INFO")
        
        for idx, coin_info in enumerate(final_filtered_coins[:10], 1):  # 상위 10개만 출력
            coin = coin_info['coin']
            price_str = f"{coin_info['current_price']:,.2f}원"
            volume_str = f"{coin_info['volume_24h']/100000000:,.2f}억원"
            logger.log(f"{idx:4d}. {coin:<15} {price_str:<20} {volume_str:<20}", "INFO")
        
        if len(final_filtered_coins) > 10:
            logger.log(f"... 외 {len(final_filtered_coins)-10}개 코인", "INFO")
    
    return final_filtered_coins


def print_3minute_candles(filtered_coins, interval_minutes=3, target_hour=9, logger=None, return_details=False):
    """분봉 데이터를 분석하여 가격/거래량이 상승한 코인을 선별합니다.

    Args:
        filtered_coins: 2단계 통과 코인 리스트
        interval_minutes: 분봉
        target_hour: 타겟 시각(표시용)
        logger: 로거
        return_details: True면 (통과리스트, 전체상세리스트) 반환
    """
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log(f"3. {target_hour:02d}시 전후 {interval_minutes}분봉 분석 (가격/거래량 상승 코인)", "INFO")
        logger.log("=" * 60, "INFO")
        logger.log(f"{interval_minutes}분봉 데이터 분석 중...", "INFO")
    
    rising_coins = []
    details = []
    
    for coin_info in filtered_coins:
        detail = {
            'stage': 3,
            'coin': coin_info.get('coin'),
            'coin_symbol': (coin_info.get('coin') or '').replace("KRW-", ""),
            'current_price': coin_info.get('current_price'),
            'volume_24h': coin_info.get('volume_24h'),
            'interval_minutes': interval_minutes,
            'pass': False,
            'fail_reason': None,
        }
        try:
            candle1 = coin_info.get('candle1')
            candle2 = coin_info.get('candle2')
            detail['candle1_exists'] = candle1 is not None
            detail['candle2_exists'] = candle2 is not None

            if candle1 is None or candle2 is None:
                missing_candles = []
                if candle1 is None:
                    missing_candles.append("candle1")
                if candle2 is None:
                    missing_candles.append("candle2")
                detail['fail_reason'] = 'candle_missing'
                detail['missing_candles'] = ', '.join(missing_candles)
                if logger:
                    coin_symbol = detail.get('coin_symbol', '')
                    logger.log(f"  {coin_symbol}: 캔들 존재하지 않음 ({', '.join(missing_candles)})", "WARNING")
                details.append(detail)
                continue

            price1 = candle1['close']
            price2 = candle2['close']
            volume1 = candle1['volume']
            volume2 = candle2['volume']
            value1 = candle1.get('value', 0) if 'value' in candle1 else 0
            value2 = candle2.get('value', 0) if 'value' in candle2 else 0

            detail.update({
                'price1': price1,
                'price2': price2,
                'volume1': volume1,
                'volume2': volume2,
                'value1': value1,
                'value2': value2,
            })

            price_change = ((price2 - price1) / price1) * 100 if price1 else 0
            volume_change = ((volume2 - volume1) / volume1) * 100 if volume1 else 0
            value_change = ((value2 - value1) / value1) * 100 if value1 else 0

            detail.update({
                'price_change': price_change,
                'volume_change': volume_change,
                'value_change': value_change,
            })

            if not (price2 > price1):
                detail['fail_reason'] = 'price_not_up'
                details.append(detail)
                continue

            if not (volume2 > volume1):
                detail['fail_reason'] = 'volume_not_up'
                details.append(detail)
                continue

            # 통과
            detail['pass'] = True
            details.append(detail)
            rising_coins.append({
                'coin': coin_info['coin'],
                'current_price': coin_info['current_price'],
                'volume_24h': coin_info['volume_24h'],
                'price1': price1,
                'price2': price2,
                'price_change': price_change,
                'volume1': volume1,
                'volume2': volume2,
                'volume_change': volume_change,
                'value1': value1,
                'value2': value2,
                'value_change': value_change,
                'df_candle': coin_info.get('df_candle')
            })
        except Exception as e:
            detail['fail_reason'] = 'exception'
            detail['error'] = str(e)
            details.append(detail)
            continue
    
    rising_coins.sort(key=lambda x: x['volume_change'], reverse=True)
    
    if logger:
        logger.log(f"총 코인 개수: {len(rising_coins)}개", "SUCCESS")
        if rising_coins:
            logger.log(f"{'번호':<6} {'코인':<15} {'가격변동':<12} {'거래량변동':<25}", "INFO")
            logger.log("-" * 60, "INFO")
            for idx, coin_info in enumerate(rising_coins[:10], 1):
                coin = coin_info['coin']
                price_change = f"+{coin_info['price_change']:.2f}%"
                volume_change = f"+{coin_info['volume_change']:.2f}%"
                logger.log(f"{idx:4d}. {coin:<15} {price_change:<12} {volume_change:<25}", "INFO")
            if len(rising_coins) > 10:
                logger.log(f"... 외 {len(rising_coins)-10}개 코인", "INFO")
    
    if return_details:
        return rising_coins, details
    return rising_coins


def print_filtered_coins_by_price_volume(rising_coins, price_change_min=0.5, price_change_max=5.0, volume_change_min=100.0, logger=None, return_details=False):
    """가격/거래량 변동률 기준으로 필터링합니다.

    return_details=True면 (통과리스트, 전체상세리스트) 반환
    """
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log(f"4. 가격 변동률 {price_change_min}~{price_change_max}%, 거래량변동 {volume_change_min}% 이상인 코인 리스트", "INFO")
        logger.log("=" * 60, "INFO")
    
    details = []
    filtered_coins = []
    for coin_info in rising_coins:
        price_change = coin_info.get('price_change', 0)
        volume_change = coin_info.get('volume_change', 0)
        passed = True
        reasons = []
        if price_change < price_change_min:
            passed = False
            reasons.append('price_change_below_min')
        if price_change > price_change_max:
            passed = False
            reasons.append('price_change_above_max')
        if volume_change < volume_change_min:
            passed = False
            reasons.append('volume_change_below_min')

        detail = {
            'stage': 4,
            'coin': coin_info.get('coin'),
            'coin_symbol': (coin_info.get('coin') or '').replace("KRW-", ""),
            'price_change': price_change,
            'volume_change': volume_change,
            'price_change_min': price_change_min,
            'price_change_max': price_change_max,
            'volume_change_min': volume_change_min,
            'pass': passed,
            'fail_reason': ",".join(reasons) if reasons else None,
        }
        details.append(detail)
        if passed:
            filtered_coins.append(coin_info)
    
    filtered_coins.sort(key=lambda x: x['volume_change'], reverse=True)
    
    if logger:
        logger.log(f"총 코인 개수: {len(filtered_coins)}개", "SUCCESS")
        if filtered_coins:
            coin_names = [coin_info['coin'].replace("KRW-", "") for coin_info in filtered_coins]
            logger.log(f"필터링 통과 코인: {', '.join(coin_names)}", "INFO")
    
    if return_details:
        return filtered_coins, details
    return filtered_coins


# ============================================================================
# 시장가 매수 분석 함수
# ============================================================================

def get_market_buy_percentage(coin, buy_amount=10000000, max_spread=0.2, return_detail=False):
    """시장가 매수 시 몇% 이내로 매수가 가능한지 계산합니다.

    return_detail=True면 성공/실패 사유를 포함한 dict를 반환합니다.
    - 성공: {'ok': True, 'data': {...}}
    - 실패: {'ok': False, 'reason': '<reason>', ...}
    """
    try:
        url = "https://api.upbit.com/v1/orderbook"
        params = {"markets": coin}
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            orderbook_list = response.json()
            
            if orderbook_list and len(orderbook_list) > 0:
                orderbook = orderbook_list[0]
                
                asks = []
                bids = []
                lowest_ask = None
                highest_bid = None
                
                if 'orderbook_units' in orderbook:
                    for unit in orderbook['orderbook_units']:
                        ask_price = unit.get('ask_price', 0)
                        ask_size = unit.get('ask_size', 0)
                        bid_price = unit.get('bid_price', 0)
                        bid_size = unit.get('bid_size', 0)
                        
                        if ask_price > 0 and ask_size > 0:
                            asks.append((ask_price, ask_size))
                            if lowest_ask is None or ask_price < lowest_ask:
                                lowest_ask = ask_price
                        
                        if bid_price > 0 and bid_size > 0:
                            bids.append((bid_price, bid_size))
                            if highest_bid is None or bid_price > highest_bid:
                                highest_bid = bid_price
                
                if not asks or lowest_ask is None:
                    if return_detail:
                        return {'ok': False, 'reason': 'orderbook_empty'}
                    return None
                
                # 호가 스프레드 계산 (최우선 매도호가와 최우선 매수호가의 차이)
                if highest_bid and highest_bid > 0:
                    spread_pct = ((lowest_ask - highest_bid) / highest_bid) * 100
                    # 호가 스프레드가 설정값을 넘으면 제외
                    if spread_pct > max_spread:
                        if return_detail:
                            return {
                                'ok': False,
                                'reason': 'spread_exceeded',
                                'spread_pct': spread_pct,
                                'lowest_ask': lowest_ask,
                                'highest_bid': highest_bid,
                                'max_spread': max_spread,
                            }
                        return None
                
                asks.sort(key=lambda x: x[0])
                
                remaining_amount = buy_amount
                total_quantity = 0
                total_cost = 0
                filled_asks = []
                
                for ask_price, ask_size in asks:
                    if remaining_amount <= 0:
                        break
                    
                    available_cost = ask_price * ask_size
                    
                    if available_cost <= remaining_amount:
                        quantity = ask_size
                        cost = available_cost
                        remaining_amount -= cost
                    else:
                        quantity = remaining_amount / ask_price
                        cost = remaining_amount
                        remaining_amount = 0
                    
                    total_quantity += quantity
                    total_cost += cost
                    filled_asks.append({
                        'price': ask_price,
                        'quantity': quantity,
                        'cost': cost
                    })
                    
                    if remaining_amount <= 0:
                        break
                
                if total_quantity > 0:
                    avg_price = total_cost / total_quantity
                    price_diff_pct = ((avg_price - lowest_ask) / lowest_ask) * 100
                else:
                    avg_price = 0
                    price_diff_pct = 0
                
                # 호가 스프레드 계산 (이미 위에서 계산됨)
                spread_pct = ((lowest_ask - highest_bid) / highest_bid) * 100 if highest_bid and highest_bid > 0 else 0
                
                data = {
                    'lowest_ask': lowest_ask,
                    'avg_price': avg_price,
                    'price_diff_pct': price_diff_pct,
                    'total_quantity': total_quantity,
                    'total_cost': total_cost,
                    'filled_asks_count': len(filled_asks),
                    'spread_pct': spread_pct  # 호가스프레드 추가
                }
                if return_detail:
                    return {'ok': True, 'data': data}
                return data
        if return_detail:
            return {'ok': False, 'reason': 'http_error', 'status_code': response.status_code}
        return None
    except Exception as e:
        if return_detail:
            return {'ok': False, 'reason': 'exception', 'error': str(e)}
        return None


def print_all_coins_market_buy_analysis(rising_coins, buy_amount=10000000, max_spread=0.2, logger=None, return_details=False):
    """모든 코인에 대해 시장가 매수 분석을 수행합니다.

    return_details=True면 (통과리스트, 전체상세리스트) 반환
    """
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log(f"5. 시장가 매수 분석 (1000만원)", "INFO")
        logger.log("=" * 60, "INFO")
        logger.log(f"시장가 매수 분석 중... (총 {len(rising_coins)}개 코인)", "INFO")
    
    analysis_results = []
    excluded_by_spread = []  # 호가 스프레드로 제외된 코인 리스트 (기존 로그용)
    details = []
    
    for idx, coin_info in enumerate(rising_coins, 1):
        coin = coin_info['coin']
        coin_symbol = coin.replace("KRW-", "")
        detail_result = get_market_buy_percentage(coin, buy_amount, max_spread, return_detail=True)
        
        if detail_result and detail_result.get('ok'):
            result = detail_result['data']
            analysis_results.append({
                'coin': coin,
                'price_change': coin_info['price_change'],
                'volume_change': coin_info['volume_change'],
                'lowest_ask': result['lowest_ask'],
                'avg_price': result['avg_price'],
                'price_diff_pct': result['price_diff_pct'],
                'filled_asks_count': result['filled_asks_count'],
                'spread_pct': result.get('spread_pct', 0)  # 호가스프레드 추가
            })
            details.append({
                'stage': 5,
                'coin': coin,
                'coin_symbol': coin_symbol,
                'price_change': coin_info.get('price_change', 0),
                'volume_change': coin_info.get('volume_change', 0),
                'lowest_ask': result.get('lowest_ask'),
                'avg_price': result.get('avg_price'),
                'price_diff_pct': result.get('price_diff_pct'),
                'filled_asks_count': result.get('filled_asks_count'),
                'spread_pct': result.get('spread_pct', 0),
                'pass': True,
                'fail_reason': None,
            })
        else:
            reason = detail_result.get('reason') if isinstance(detail_result, dict) else 'unknown'
            if reason == 'spread_exceeded':
                excluded_by_spread.append(coin_symbol)
            details.append({
                'stage': 5,
                'coin': coin,
                'coin_symbol': coin_symbol,
                'price_change': coin_info.get('price_change', 0),
                'volume_change': coin_info.get('volume_change', 0),
                'pass': False,
                'fail_reason': reason,
                'status_code': detail_result.get('status_code') if isinstance(detail_result, dict) else None,
                'spread_pct': detail_result.get('spread_pct') if isinstance(detail_result, dict) else None,
                'max_spread': max_spread,
                'error': detail_result.get('error') if isinstance(detail_result, dict) else None,
            })
        
        if logger and idx % 5 == 0:
            logger.log(f"  [{idx}/{len(rising_coins)}] 분석 완료", "INFO")
    
    if logger:
        logger.log(f"총 코인 개수: {len(analysis_results)}개", "SUCCESS")
        if analysis_results:
            coin_names = [r['coin'].replace("KRW-", "") for r in analysis_results]
            logger.log(f"분석 통과 코인: {', '.join(coin_names)}", "INFO")
        if excluded_by_spread:
            logger.log(f"호가 스프레드 {max_spread}% 초과로 제외된 코인: {len(excluded_by_spread)}개 ({', '.join(excluded_by_spread)})", "INFO")
    
    if return_details:
        return analysis_results, details
    return analysis_results


# ============================================================================
# 결과 팝업창
# ============================================================================

def get_profit_result_html(profit_results):
    """당일 매매 수익률 결과를 HTML로 변환"""
    if not profit_results:
        return None
    
    # 테이블 행 생성
    rows_html = ""
    total_buy_amount = 0
    total_sell_amount = 0
    
    for idx, result in enumerate(profit_results, 1):
        coin = result.get('coin', '').replace("KRW-", "")
        buy_price = result.get('buy_price', 0)
        sell_price = result.get('sell_price', 0)
        buy_amount = result.get('buy_amount', 0)
        sell_amount = result.get('sell_amount', 0)
        profit_pct = result.get('profit_pct', 0)
        profit_amount = result.get('profit_amount', 0)
        
        total_buy_amount += buy_amount
        total_sell_amount += sell_amount
        
        profit_class = 'positive' if profit_pct >= 0 else 'negative'
        profit_pct_text = f"+{profit_pct:.2f}%" if profit_pct >= 0 else f"{profit_pct:.2f}%"
        profit_amount_text = f"+{profit_amount:,.0f}원" if profit_amount >= 0 else f"{profit_amount:,.0f}원"
        
        rows_html += f"""
            <tr>
                <td>{idx}</td>
                <td><strong>{coin}</strong></td>
                <td style="text-align: right;">{buy_price:,.2f}원</td>
                <td style="text-align: right;">{sell_price:,.2f}원</td>
                <td class="{profit_class}" style="text-align: right; font-weight: bold;">{profit_pct_text}</td>
                <td class="{profit_class}" style="text-align: right; font-weight: bold;">{profit_amount_text}</td>
            </tr>
            """
    
    # 합산 수익률 계산
    total_profit_amount = total_sell_amount - total_buy_amount
    total_profit_pct = ((total_sell_amount / total_buy_amount) - 1) * 100 if total_buy_amount > 0 else 0
    total_profit_class = 'positive' if total_profit_pct >= 0 else 'negative'
    total_profit_pct_text = f"+{total_profit_pct:.2f}%" if total_profit_pct >= 0 else f"{total_profit_pct:.2f}%"
    total_profit_amount_text = f"+{total_profit_amount:,.0f}원" if total_profit_amount >= 0 else f"{total_profit_amount:,.0f}원"
    
    summary_html = f"""
            <tr style="background: #f8f9ff; font-weight: bold; border-top: 3px solid #6B46C1;">
                <td colspan="4" style="text-align: center;"><strong>합산</strong></td>
                <td class="{total_profit_class}" style="text-align: right; font-size: 16px;">{total_profit_pct_text}</td>
                <td class="{total_profit_class}" style="text-align: right; font-size: 16px;">{total_profit_amount_text}</td>
            </tr>
    """
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>당일 매매 수익률</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: '맑은 고딕', 'Malgun Gothic', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #6B46C1 0%, #764ba2 100%);
                color: white;
                padding: 30px 40px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 28px;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            .header p {{
                font-size: 14px;
                opacity: 0.9;
            }}
            .table-container {{
                padding: 30px;
                overflow-x: auto;
            }}
            .result-table {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }}
            .result-table thead {{
                background: linear-gradient(135deg, #6B46C1 0%, #764ba2 100%);
                color: white;
            }}
            .result-table th {{
                padding: 18px 20px;
                text-align: left;
                font-weight: 600;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-right: 1px solid rgba(255,255,255,0.2);
            }}
            .result-table th:last-child {{
                border-right: none;
            }}
            .result-table tbody tr {{
                transition: all 0.3s ease;
                border-bottom: 1px solid #f0f0f0;
            }}
            .result-table tbody tr:hover {{
                background: linear-gradient(90deg, #f8f9ff 0%, #ffffff 100%);
                transform: scale(1.01);
                box-shadow: 0 4px 12px rgba(107, 70, 193, 0.15);
            }}
            .result-table tbody tr:last-child {{
                border-bottom: none;
            }}
            .result-table td {{
                padding: 20px;
                font-size: 14px;
                color: #333;
                border-right: 1px solid #f0f0f0;
            }}
            .result-table td:last-child {{
                border-right: none;
            }}
            .positive {{
                color: #10b981;
            }}
            .negative {{
                color: #ef4444;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💰 당일 매매 수익률</h1>
                <p>종료 시간 전량 매도 결과 - 총 {len(profit_results)}개 코인</p>
            </div>
            <div class="table-container">
                <table class="result-table">
                    <thead>
                        <tr>
                            <th>순위</th>
                            <th>코인</th>
                            <th>매수가</th>
                            <th>매도가</th>
                            <th>수익률</th>
                            <th>수익금액</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                        {summary_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

def get_slippage_result_html(filtered_results, max_slippage, csv_filename=None):
    """슬리피지 필터링 결과를 HTML로 변환"""
    # 테이블 행 생성
    rows_html = ""
    result_count = 0
    
    if csv_filename and os.path.exists(csv_filename):
        # CSV 파일에서 읽기
        try:
            with open(csv_filename, 'r', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    result_count += 1
                    # 일봉 필터링: O(통과) / X(미통과) only
                    day_filter_value = (row.get('일봉필터링', '') or row.get('매수추천', '') or '').strip().upper()
                    passed = day_filter_value == 'O'
                    day_filter_html = '<span style="color: #10B981; font-weight: bold; font-size: 16px;">O</span>' if passed else '<span style="color: #EF4444; font-weight: bold; font-size: 16px;">X</span>'
                    rows_html += f"""
                    <tr>
                        <td>{row.get('순위', '')}</td>
                        <td>{row.get('코인', '')}</td>
                        <td style="text-align: center;">{day_filter_html}</td>
                        <td>{row.get('가격변동률', '')}</td>
                        <td>{row.get('거래량변동률', '')}</td>
                        <td style="text-align: right;">{row.get('최저매도가', '')}</td>
                        <td style="text-align: right;">{row.get('평균매수가', '')}</td>
                        <td>{row.get('슬리피지', '')}</td>
                        <td>{row.get('호가스프레드', '')}</td>
                        <td style="text-align: center;">{row.get('소진호가수', '')}</td>
                    </tr>
                    """
        except Exception as e:
            print(f"CSV 파일 읽기 오류: {e}")
            rows_html = '<tr><td colspan="8" style="text-align: center; color: red;">CSV 파일 읽기 오류</td></tr>'
    else:
        # 직접 데이터에서 생성
        result_count = len(filtered_results) if filtered_results else 0
        for idx, result in enumerate(filtered_results, 1):
            coin = result.get('coin', '').replace("KRW-", "")
            price_change = f"+{result.get('price_change', 0):.2f}%"
            volume_change = f"+{result.get('volume_change', 0):.2f}%"
            lowest_ask = f"{result.get('lowest_ask', 0):,.0f}원"
            avg_price = f"{result.get('avg_price', 0):,.0f}원"
            price_diff_pct = f"{result.get('price_diff_pct', 0):.4f}%"
            spread_pct = f"{result.get('spread_pct', 0):.4f}%"
            filled_count = f"{result.get('filled_asks_count', 0)}개"
            
            # 일봉 필터링: day_candle_pass(양봉비율 통과) O / 미통과 X
            passed = result.get('day_candle_pass', False)
            day_filter_html = '<span style="color: #10B981; font-weight: bold; font-size: 16px;">O</span>' if passed else '<span style="color: #EF4444; font-weight: bold; font-size: 16px;">X</span>'
            
            rows_html += f"""
            <tr>
                <td>{idx}</td>
                <td>{coin}</td>
                <td style="text-align: center;">{day_filter_html}</td>
                <td>{price_change}</td>
                <td>{volume_change}</td>
                <td style="text-align: right;">{lowest_ask}</td>
                <td style="text-align: right;">{avg_price}</td>
                <td>{price_diff_pct}</td>
                <td>{spread_pct}</td>
                <td style="text-align: center;">{filled_count}</td>
            </tr>
            """
    
    if not rows_html:
        rows_html = '<tr><td colspan="10" style="text-align: center; padding: 40px; color: #999;">데이터가 없습니다.</td></tr>'
    
    csv_info = f"<p style='color: #666; font-size: 12px; margin-top: 10px;'>💾 저장됨: {csv_filename}</p>" if csv_filename else ""
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>슬리피지 필터링 결과</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            body {{
                font-family: '맑은 고딕', 'Malgun Gothic', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                min-height: 100vh;
            }}
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #6B46C1 0%, #764ba2 100%);
                color: white;
                padding: 30px 40px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 28px;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            .header p {{
                font-size: 14px;
                opacity: 0.9;
            }}
            .table-container {{
                padding: 30px;
                overflow-x: auto;
            }}
            .result-table {{
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background: white;
                border-radius: 12px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            }}
            .result-table thead {{
                background: linear-gradient(135deg, #6B46C1 0%, #764ba2 100%);
                color: white;
            }}
            .result-table th {{
                padding: 18px 20px;
                text-align: left;
                font-weight: 600;
                font-size: 14px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                border-right: 1px solid rgba(255,255,255,0.2);
            }}
            .result-table th:last-child {{
                border-right: none;
            }}
            .result-table tbody tr {{
                transition: all 0.3s ease;
                border-bottom: 1px solid #f0f0f0;
            }}
            .result-table tbody tr:hover {{
                background: linear-gradient(90deg, #f8f9ff 0%, #ffffff 100%);
                transform: scale(1.01);
                box-shadow: 0 4px 12px rgba(107, 70, 193, 0.15);
            }}
            .result-table tbody tr:last-child {{
                border-bottom: none;
            }}
            .result-table td {{
                padding: 20px;
                font-size: 14px;
                color: #333;
                border-right: 1px solid #f0f0f0;
            }}
            .result-table td:last-child {{
                border-right: none;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📊 슬리피지 {max_slippage}% 이내인 코인 리스트</h1>
                <p>총 {result_count}개 코인</p>
                {csv_info}
            </div>
            <div class="table-container">
                <table class="result-table">
                    <thead>
                        <tr>
                            <th>순위</th>
                            <th>코인</th>
                            <th>일봉필터링</th>
                            <th>가격변동률</th>
                            <th>거래량변동률</th>
                            <th>최저매도가</th>
                            <th>평균매수가</th>
                            <th>슬리피지</th>
                            <th>호가스프레드</th>
                            <th>소진호가수</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """

def show_result_popup(root, filtered_results, max_slippage, csv_filename=None):
    """6단계 슬리피지 필터링 결과를 브라우저 팝업창으로 표시합니다."""
    if not filtered_results:
        print("show_result_popup: filtered_results가 비어있습니다.")
        return
    
    try:
        print(f"show_result_popup 호출됨: 코인 {len(filtered_results)}개, CSV: {csv_filename}")
        
        # HTML 생성
        html_content = get_slippage_result_html(filtered_results, max_slippage, csv_filename)
        
        # 임시 파일로 저장하고 브라우저에서 열기
        temp_file = os.path.join(tempfile.gettempdir(), f'slippage_results_{get_kst_now().strftime("%Y%m%d_%H%M%S")}.html')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML 파일 생성 완료: {temp_file}")
        
        # 브라우저에서 열기 (Windows 경로 처리)
        if os.name == 'nt':  # Windows
            file_url = f'file:///{temp_file.replace(os.sep, "/")}'
        else:
            file_url = f'file://{temp_file}'
        
        print(f"브라우저 열기 시도: {file_url}")
        webbrowser.open(file_url)
        
        print(f"팝업창 표시 완료: {temp_file}")
    except Exception as e:
        print(f"팝업창 표시 오류: {e}")
        import traceback
        traceback.print_exc()

def show_profit_popup(profit_results):
    """당일 매매 수익률 결과를 브라우저 팝업창으로 표시합니다."""
    if not profit_results:
        print("show_profit_popup: profit_results가 비어있습니다.")
        return
    
    try:
        print(f"show_profit_popup 호출됨: 코인 {len(profit_results)}개")
        
        # HTML 생성
        html_content = get_profit_result_html(profit_results)
        if not html_content:
            print("HTML 생성 실패")
            return
        
        # 임시 파일로 저장하고 브라우저에서 열기
        temp_file = os.path.join(tempfile.gettempdir(), f'profit_results_{get_kst_now().strftime("%Y%m%d_%H%M%S")}.html')
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"HTML 파일 생성 완료: {temp_file}")
        
        # 브라우저에서 열기 (Windows 경로 처리)
        if os.name == 'nt':  # Windows
            file_url = f'file:///{temp_file.replace(os.sep, "/")}'
        else:
            file_url = f'file://{temp_file}'
        
        print(f"브라우저 열기 시도: {file_url}")
        webbrowser.open(file_url)
        
        print(f"팝업창 표시 완료: {temp_file}")
    except Exception as e:
        print(f"팝업창 표시 오류: {e}")
        import traceback
        traceback.print_exc()

def write_slippage_csv_and_popup(filtered_results, max_slippage, logger=None, root=None):
    """슬리피지 필터 결과를 CSV로 저장하고 팝업을 큐에 넣습니다. day_candle_pass 있으면 O/X 반영."""
    csv_filename = None
    if not filtered_results:
        return csv_filename
    try:
        # 데이터 저장 디렉토리 (Railway Volume 지원)
        data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
        
        timestamp = get_kst_now().strftime("%Y%m%d_%H%M%S")
        csv_filename = os.path.join(data_dir, f"slippage_results_{timestamp}.csv")
        with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['순위', '코인', '일봉필터링', '가격변동률', '거래량변동률', '최저매도가', '평균매수가', '슬리피지', '호가스프레드', '소진호가수']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for idx, result in enumerate(filtered_results, 1):
                coin = result.get('coin', '').replace("KRW-", "")
                price_change = f"+{result.get('price_change', 0):.2f}%"
                volume_change = f"+{result.get('volume_change', 0):.2f}%"
                lowest_ask = f"{result.get('lowest_ask', 0):,.0f}원"
                avg_price = f"{result.get('avg_price', 0):,.0f}원"
                price_diff_pct = f"{result.get('price_diff_pct', 0):.4f}%"
                spread_pct = f"{result.get('spread_pct', 0):.4f}%"
                filled_count = f"{result.get('filled_asks_count', 0)}개"
                passed = result.get('day_candle_pass', False)
                day_filter = "O" if passed else "X"
                writer.writerow({
                    '순위': idx, '코인': coin, '일봉필터링': day_filter,
                    '가격변동률': price_change, '거래량변동률': volume_change,
                    '최저매도가': lowest_ask, '평균매수가': avg_price,
                    '슬리피지': price_diff_pct, '호가스프레드': spread_pct, '소진호가수': filled_count
                })
        if logger:
            logger.log(f"CSV 파일 저장 완료: {csv_filename}", "SUCCESS")
    except Exception as e:
        if logger:
            logger.log(f"CSV 파일 저장 오류: {e}", "ERROR")
        csv_filename = None
    if root and hasattr(root, 'popup_queue'):
        try:
            results_copy = [r.copy() for r in filtered_results]
            root.popup_queue.put(('show_popup', results_copy, max_slippage, csv_filename))
        except Exception as e:
            if logger:
                logger.log(f"팝업창 표시 오류: {e}", "ERROR")
    elif logger and filtered_results:
        logger.log("팝업창 표시 실패: root 또는 popup_queue가 없습니다.", "WARNING")
    return csv_filename


def print_filtered_by_slippage(analysis_results, max_slippage=0.3, logger=None, root=None, skip_csv_and_popup=False, return_details=False):
    """시장가 매수 분석 결과 중 슬리피지 이내인 코인만 선별합니다.

    return_details=True면 (통과리스트, 전체상세리스트) 반환
    """
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log(f"6. 펌핑가능 코인중 슬리피지 {max_slippage}% 이내인 코인 리스트", "INFO")
        logger.log("=" * 60, "INFO")
    
    if not analysis_results:
        if logger:
            logger.log("분석 결과가 없습니다.", "WARNING")
        return []
    
    details = []
    filtered_results = []
    for result in analysis_results:
        price_diff_pct = result.get('price_diff_pct', float('inf'))
        passed = price_diff_pct <= max_slippage
        details.append({
            'stage': 6,
            'coin': result.get('coin'),
            'coin_symbol': (result.get('coin') or '').replace("KRW-", ""),
            'price_change': result.get('price_change', 0),
            'volume_change': result.get('volume_change', 0),
            'lowest_ask': result.get('lowest_ask'),
            'avg_price': result.get('avg_price'),
            'price_diff_pct': price_diff_pct,
            'spread_pct': result.get('spread_pct', 0),
            'filled_asks_count': result.get('filled_asks_count'),
            'max_slippage': max_slippage,
            'pass': passed,
            'fail_reason': None if passed else 'slippage_exceeded',
        })
        if passed:
            filtered_results.append(result)
    
    filtered_results.sort(key=lambda x: x['price_diff_pct'])
    
    if not skip_csv_and_popup and filtered_results:
        write_slippage_csv_and_popup(filtered_results, max_slippage, logger=logger, root=root)
    
    if logger:
        logger.log(f"총 코인 개수: {len(filtered_results)}개", "SUCCESS")
        if filtered_results:
            logger.log(f"{'번호':<6} {'코인':<15} {'가격변동률':<15} {'거래량변동률':<15} {'슬리피지':<15} {'호가스프레드':<15}", "INFO")
            logger.log("-" * 90, "INFO")
            for idx, result in enumerate(filtered_results[:10], 1):
                coin = result['coin'].replace("KRW-", "")
                price_change = f"+{result['price_change']:.2f}%"
                volume_change = f"+{result['volume_change']:.2f}%"
                price_diff_pct = f"{result['price_diff_pct']:.4f}%"
                spread_pct = f"{result.get('spread_pct', 0):.4f}%"
                logger.log(f"{idx:4d}. {coin:<15} {price_change:<15} {volume_change:<15} {price_diff_pct:<15} {spread_pct:<15}", "INFO")
            if len(filtered_results) > 10:
                logger.log(f"... 외 {len(filtered_results)-10}개 코인", "INFO")
    
    if return_details:
        return filtered_results, details
    return filtered_results


def filter_by_day_candle(filtered_results, min_bullish_ratio=0.4, logger=None, stop_event=None):
    """일봉 필터링: 최근 일봉 10개 중 양봉 비율이 min_bullish_ratio 이상인 코인만 선별"""
    if not filtered_results:
        return []
    
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log(f"7. 일봉 필터링: 최근 일봉 10개 중 양봉 {min_bullish_ratio*100:.0f}% 이상인 코인 선별", "INFO")
        logger.log("=" * 60, "INFO")
        logger.log(f"📊 필터링 전 코인 개수: {len(filtered_results)}개", "INFO")
        logger.log("필터링 전 코인 리스트:", "INFO")
        logger.log(f"{'번호':<6} {'코인':<15} {'가격변동률':<15} {'거래량변동률':<15} {'슬리피지':<15}", "INFO")
        logger.log("-" * 75, "INFO")
        for idx, result in enumerate(filtered_results[:10], 1):
            coin = result['coin'].replace("KRW-", "")
            price_change = f"+{result.get('price_change', 0):.2f}%"
            volume_change = f"+{result.get('volume_change', 0):.2f}%"
            price_diff_pct = f"{result.get('price_diff_pct', 0):.4f}%"
            logger.log(f"{idx:4d}. {coin:<15} {price_change:<15} {volume_change:<15} {price_diff_pct:<15}", "INFO")
        if len(filtered_results) > 10:
            logger.log(f"... 외 {len(filtered_results)-10}개 코인", "INFO")
        logger.log("", "INFO")
    
    filtered_by_candle = []
    
    for idx, result in enumerate(filtered_results, 1):
        if stop_event and stop_event.is_set():
            if logger:
                logger.log("일봉 필터링 중단됨", "WARNING")
            break
        
        coin = result.get('coin', '')
        coin_symbol = coin.replace("KRW-", "")
        
        try:
            # 최근 일봉 10개 가져오기
            df_day = pyupbit.get_ohlcv(coin, interval="day", count=10)
            
            if df_day is None or df_day.empty:
                if logger:
                    logger.log(f"  {coin_symbol}: 일봉 데이터 없음", "WARNING")
                result = result.copy()
                result['day_candle_pass'] = False
                result['bullish_ratio'] = 0
                result['bullish_count'] = 0
                result['total_candles'] = 0
                filtered_by_candle.append(result)
                continue
            
            # 일봉 날짜 범위 확인 (로깅용)
            if logger and idx == 1:  # 첫 번째 코인에서만 전체 범위 로그 출력
                if not df_day.empty:
                    first_date = df_day.index[0].strftime('%Y-%m-%d')
                    last_date = df_day.index[-1].strftime('%Y-%m-%d')
                    logger.log(f"📅 일봉 확인 범위: {first_date} ~ {last_date} (총 {len(df_day)}개)", "INFO")
            
            # 양봉 개수 계산 (종가 > 시가)
            bullish_count = 0
            total_count = len(df_day)
            
            # 각 일봉의 날짜와 양봉 여부를 로그로 출력 (첫 번째 코인만 상세히)
            if logger and idx == 1:
                logger.log(f"  일봉 상세 (첫 번째 코인 {coin_symbol} 기준):", "INFO")
                for date_idx, (date, row) in enumerate(df_day.iterrows()):
                    open_price = row['open']
                    close_price = row['close']
                    is_bullish = close_price > open_price
                    date_str = date.strftime('%Y-%m-%d')
                    bullish_mark = "✅ 양봉" if is_bullish else "❌ 음봉"
                    logger.log(f"    {date_str}: {bullish_mark} (시가: {open_price:,.0f}, 종가: {close_price:,.0f})", "INFO")
            
            for _, row in df_day.iterrows():
                open_price = row['open']
                close_price = row['close']
                if close_price > open_price:  # 양봉
                    bullish_count += 1
            
            # 양봉 비율 계산
            bullish_ratio = bullish_count / total_count if total_count > 0 else 0
            
            if logger:
                logger.log(f"  {coin_symbol}: 양봉 {bullish_count}/{total_count} ({bullish_ratio*100:.1f}%)", "INFO")
            
            # 양봉 비율 기준 통과 여부 (일봉필터링 O/X 표시용)
            result['bullish_ratio'] = bullish_ratio
            result['bullish_count'] = bullish_count
            result['total_candles'] = total_count
            result['day_candle_pass'] = bullish_ratio >= min_bullish_ratio
            
            if result['day_candle_pass']:
                filtered_by_candle.append(result)
            else:
                if logger:
                    logger.log(f"  {coin_symbol}: 양봉 비율 부족 ({bullish_ratio*100:.1f}% < {min_bullish_ratio*100:.0f}%)", "WARNING")
                filtered_by_candle.append(result)  # 미통과도 리스트에 포함 (테이블 O/X 표시용)
        
        except Exception as e:
            if logger:
                logger.log(f"  {coin_symbol}: 일봉 필터링 오류 - {e}", "ERROR")
            result = result.copy()
            result['day_candle_pass'] = False
            result['bullish_ratio'] = 0
            result['bullish_count'] = 0
            result['total_candles'] = 0
            filtered_by_candle.append(result)
    
    passing_count = sum(1 for r in filtered_by_candle if r.get('day_candle_pass'))
    if logger:
        logger.log(f"📊 일봉 필터링 통과: {passing_count}개 (전체 {len(filtered_results)}개 중)", "SUCCESS")
        logger.log(f"📉 일봉 필터링 미통과: {len(filtered_results) - passing_count}개", "INFO")
        logger.log("", "INFO")
        if filtered_by_candle:
            logger.log("일봉 필터링 결과 (O: 통과, X: 미통과):", "SUCCESS")
            logger.log(f"{'번호':<6} {'코인':<15} {'일봉필터링':<12} {'양봉비율':<15} {'양봉/전체':<15} {'가격변동률':<15} {'거래량변동률':<15}", "INFO")
            logger.log("-" * 105, "INFO")
            for idx, result in enumerate(filtered_by_candle[:10], 1):
                coin = result['coin'].replace("KRW-", "")
                day_candle_pass = result.get('day_candle_pass', False)
                pass_status = "O" if day_candle_pass else "X"
                bullish_ratio = result.get('bullish_ratio', 0) * 100
                bullish_count = result.get('bullish_count', 0)
                total_candles = result.get('total_candles', 0)
                price_change = f"+{result.get('price_change', 0):.2f}%"
                volume_change = f"+{result.get('volume_change', 0):.2f}%"
                logger.log(f"{idx:4d}. {coin:<15} {pass_status:<12} {bullish_ratio:.1f}%{'':<8} {bullish_count}/{total_candles} {'':<5} {price_change:<15} {volume_change:<15}", "INFO")
            if len(filtered_by_candle) > 10:
                logger.log(f"... 외 {len(filtered_by_candle)-10}개 코인", "INFO")
        else:
            logger.log("⚠️ 일봉 필터링 결과가 없습니다.", "WARNING")
    
    return filtered_by_candle


# ============================================================================
# 자동 매수/매도 함수
# ============================================================================

def get_krw_balance(upbit):
    """원화 잔고를 확인합니다."""
    try:
        balance = upbit.get_balance("KRW")
        return balance if balance else 0
    except Exception as e:
        return 0


def buy_coins_from_list(upbit, coin_list, sell_percentage=3, sell_ratio=0.5, investment_ratio=100, max_coins=None, logger=None, purchased_coins_dict=None):
    """
    6번 리스트의 코인들을 자동으로 매수하고 지정가 매도 주문을 겁니다.
    
    Args:
        upbit: pyupbit.Upbit 객체
        coin_list: 코인 리스트
        sell_percentage: 지정가 매도 가격 상승률 (%)
        sell_ratio: 지정가 매도 비중 (1.0=전부, 0.5=절반, 0.333=3분의1)
        investment_ratio: 투자비중 (원화잔고의 몇%를 투자할지, %)
        max_coins: 최대 허용 코인개수 (None이면 모든 코인 매수)
        logger: 로거 객체
    """
    if not coin_list:
        if logger:
            logger.log("매수할 코인이 없습니다.", "WARNING")
        return []
    
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log("7. 자동 매수/매도 시작", "INFO")
        logger.log("=" * 60, "INFO")
    
    # 코인 리스트 정렬: 슬리피지 작은 순 -> 호가스프레드 작은 순 -> 거래량변동률 큰 순 -> 가격변동률 큰 순
    sorted_coin_list = sorted(coin_list, key=lambda x: (
        x.get('price_diff_pct', float('inf')),  # 슬리피지 작은 순 (1순위)
        x.get('spread_pct', float('inf')),  # 호가스프레드 작은 순 (2순위)
        -x.get('volume_change', 0),  # 거래량변동률 큰 순 (3순위, 음수로 내림차순)
        -x.get('price_change', 0)  # 가격변동률 큰 순 (4순위, 음수로 내림차순)
    ))
    
    # 최대 허용 코인개수 적용
    if max_coins is not None and max_coins > 0:
        original_count = len(sorted_coin_list)
        sorted_coin_list = sorted_coin_list[:max_coins]
        if logger:
            logger.log(f"필터링 결과: {original_count}개 → 최대 허용 코인개수: {max_coins}개 적용 → {len(sorted_coin_list)}개 매수", "INFO")
            # 매수 순서 출력
            logger.log("=" * 60, "INFO")
            logger.log("📋 매수 순서 (정렬 기준: 슬리피지 작은 순 → 호가스프레드 작은 순 → 거래량변동률 큰 순 → 가격변동률 큰 순)", "INFO")
            logger.log("=" * 60, "INFO")
            for idx, coin_info in enumerate(sorted_coin_list, 1):
                coin_symbol = coin_info.get('coin', '').replace("KRW-", "")
                slippage = coin_info.get('price_diff_pct', 0)
                spread_pct = coin_info.get('spread_pct', 0)
                volume_change = coin_info.get('volume_change', 0)
                price_change = coin_info.get('price_change', 0)
                logger.log(f"{idx}. {coin_symbol} - 슬리피지: {slippage:.4f}%, 호가스프레드: {spread_pct:.4f}%, 거래량변동: +{volume_change:.2f}%, 가격변동: +{price_change:.2f}%", "INFO")
            logger.log("=" * 60, "INFO")
    
    krw_balance = get_krw_balance(upbit)
    if logger:
        logger.log(f"원화 잔고: {krw_balance:,.0f}원", "INFO")
    
    if krw_balance <= 0:
        if logger:
            logger.log("원화 잔고가 없습니다. 매수를 진행할 수 없습니다.", "ERROR")
        return []
    
    coin_count = len(sorted_coin_list)
    
    # 투자비중 적용: (원화잔고 × 투자비중%) ÷ 코인개수
    total_investment = krw_balance * (investment_ratio / 100)
    buy_amount_per_coin = total_investment / coin_count
    
    # 매도 비중 텍스트
    if sell_ratio == 1.0:
        sell_ratio_text = "전부"
    elif sell_ratio == 0.5:
        sell_ratio_text = "절반"
    elif abs(sell_ratio - 0.333) < 0.01:
        sell_ratio_text = "3분의 1"
    else:
        sell_ratio_text = f"{sell_ratio*100:.1f}%"
    
    if logger:
        logger.log(f"투자비중: {investment_ratio}%", "INFO")
        logger.log(f"총 투자 금액: {total_investment:,.0f}원 (원화잔고의 {investment_ratio}%)", "INFO")
        logger.log(f"매수할 코인 개수: {coin_count}개", "INFO")
        logger.log(f"코인당 매수 금액: {buy_amount_per_coin:,.0f}원", "INFO")
        logger.log(f"매도 주문: 매수 수량의 {sell_ratio_text}을 현재가의 {sell_percentage}% 상승 가격에 지정가 매도", "INFO")
        logger.log("⚠️  실제 주문을 진행합니다!", "WARNING")
    
    results = []
    
    for idx, coin_info in enumerate(sorted_coin_list, 1):
        coin = coin_info['coin']
        coin_symbol = coin.replace("KRW-", "")
        
        if logger:
            logger.log(f"[{idx}/{coin_count}] {coin_symbol} 처리 중...", "INFO")
        
        try:
            current_price = pyupbit.get_current_price(coin)
            if not current_price:
                if logger:
                    logger.log(f"  {coin_symbol}: 현재가를 가져올 수 없습니다.", "ERROR")
                results.append({
                    'coin': coin,
                    'coin_symbol': coin_symbol,
                    'status': 'failed',
                    'reason': '현재가 조회 실패',
                    'buy_order': None,
                    'sell_order': None
                })
                continue
            
            if logger:
                logger.log(f"  현재가: {current_price:,.2f}원", "INFO")
                logger.log(f"  시장가 매수 중... ({buy_amount_per_coin:,.0f}원)", "INFO")
            
            try:
                if buy_amount_per_coin < 5000:
                    if logger:
                        logger.log(f"  최소 주문 금액(5,000원) 미달: {buy_amount_per_coin:,.0f}원", "ERROR")
                    results.append({
                        'coin': coin,
                        'coin_symbol': coin_symbol,
                        'status': 'failed',
                        'reason': f'최소 주문 금액 미달 ({buy_amount_per_coin:,.0f}원)',
                        'buy_order': None,
                        'sell_order': None
                    })
                    continue
                
                buy_order_result = upbit.buy_market_order(coin, buy_amount_per_coin)
                
                if buy_order_result:
                    if isinstance(buy_order_result, (tuple, list)):
                        buy_order = buy_order_result[0] if len(buy_order_result) > 0 else None
                    else:
                        buy_order = buy_order_result
                    
                    if buy_order and isinstance(buy_order, dict):
                        error_name = buy_order.get('error', {}).get('name', '') if isinstance(buy_order.get('error'), dict) else None
                        error_msg = buy_order.get('error', {}).get('message', '') if isinstance(buy_order.get('error'), dict) else None
                        
                        if error_name or error_msg:
                            if logger:
                                logger.log(f"  매수 주문 실패: {error_name or error_msg}", "ERROR")
                            results.append({
                                'coin': coin,
                                'coin_symbol': coin_symbol,
                                'status': 'failed',
                                'reason': f'API 오류: {error_name or error_msg}',
                                'buy_order': None,
                                'sell_order': None
                            })
                            continue
                        
                        uuid = buy_order.get('uuid', '')
                        if not uuid:
                            if logger:
                                logger.log(f"  매수 주문 실패: UUID가 없습니다.", "ERROR")
                            results.append({
                                'coin': coin,
                                'coin_symbol': coin_symbol,
                                'status': 'failed',
                                'reason': 'UUID 없음',
                                'buy_order': None,
                                'sell_order': None
                            })
                            continue
                        
                        if logger:
                            logger.log(f"  ✅ 매수 주문 성공 (UUID: {uuid[:8]}...)", "SUCCESS")
                        
                        time.sleep(2)
                        
                        if uuid:
                            orders = upbit.get_order(uuid)
                            if orders:
                                order_status = orders[0] if isinstance(orders, list) else orders
                                final_state = order_status.get('state', '')
                                executed_volume = order_status.get('executed_volume', '0')
                                if logger:
                                    logger.log(f"  주문 상태: {final_state}, 체결 수량: {executed_volume}", "INFO")
                        
                        time.sleep(1)
                        coin_balance = upbit.get_balance(coin)
                        if coin_balance and float(coin_balance) > 0:
                            if logger:
                                logger.log(f"  매수된 수량: {coin_balance}", "SUCCESS")
                            
                            # 매수 가격 저장 (실제 체결 가격)
                            buy_price = current_price  # 기본값: 현재가
                            try:
                                if uuid:
                                    time.sleep(1)  # 체결 대기
                                    orders = upbit.get_order(uuid, state="done")
                                    if orders:
                                        order = orders[0] if isinstance(orders, list) else orders
                                        executed_volume = float(order.get('executed_volume', 0))
                                        
                                        # 체결 내역(trades)에서 실제 평균 매수가 계산
                                        if executed_volume > 0:
                                            trades = order.get('trades', [])
                                            if trades and len(trades) > 0:
                                                total_cost = 0
                                                total_volume = 0
                                                for trade in trades:
                                                    # 업비트 API의 trades 구조: price, volume, funds (체결 금액)
                                                    trade_price = float(trade.get('price', 0))
                                                    trade_volume = float(trade.get('volume', 0))
                                                    trade_funds = float(trade.get('funds', 0))  # 체결 금액 (수수료 포함 전)
                                                    
                                                    # funds가 있으면 funds 사용, 없으면 price * volume 사용
                                                    if trade_funds > 0:
                                                        total_cost += trade_funds
                                                    elif trade_price > 0 and trade_volume > 0:
                                                        total_cost += trade_price * trade_volume
                                                    
                                                    if trade_volume > 0:
                                                        total_volume += trade_volume
                                                
                                                if total_volume > 0:
                                                    buy_price = total_cost / total_volume
                                                    if logger:
                                                        logger.log(f"  실제 체결 매수가: {buy_price:.4f}원 (체결 수량: {total_volume:.8f})", "INFO")
                                            else:
                                                # trades가 없으면 executed_volume과 주문 금액으로 계산
                                                # buy_amount_per_coin은 이미 수수료 제외 전 금액
                                                if executed_volume > 0:
                                                    buy_price = buy_amount_per_coin / executed_volume
                                                    if logger:
                                                        logger.log(f"  체결 내역 없음, 계산된 매수가: {buy_price:.4f}원", "WARNING")
                            except Exception as e:
                                if logger:
                                    logger.log(f"  매수 체결 가격 조회 오류: {e}", "WARNING")
                                buy_price = current_price
                            
                            # 매수한 코인 정보 저장 (실시간 모니터링용)
                            # 지정가 매도 주문 UUID는 아래에서 추가됨
                            sell_order_uuid = None
                            
                            sell_volume = float(coin_balance) * sell_ratio
                            sell_price = current_price * (1 + sell_percentage / 100)
                            
                            if sell_price < 1000:
                                sell_price = int(sell_price)
                            elif sell_price < 10000:
                                sell_price = int(sell_price / 10) * 10
                            else:
                                sell_price = int(sell_price / 100) * 100
                            
                            if logger:
                                logger.log(f"  지정가 매도 주문 중... (수량: {sell_volume}, 가격: {sell_price:,.0f}원, +{sell_percentage}%)", "INFO")
                            
                            try:
                                sell_order_result = upbit.sell_limit_order(coin, sell_price, sell_volume)
                                
                                if sell_order_result:
                                    if isinstance(sell_order_result, (tuple, list)):
                                        sell_order = sell_order_result[0] if len(sell_order_result) > 0 else None
                                    else:
                                        sell_order = sell_order_result
                                    
                                    if sell_order and isinstance(sell_order, dict):
                                        error_name = sell_order.get('error', {}).get('name', '') if isinstance(sell_order.get('error'), dict) else None
                                        error_msg = sell_order.get('error', {}).get('message', '') if isinstance(sell_order.get('error'), dict) else None
                                        
                                        if error_name or error_msg:
                                            if logger:
                                                logger.log(f"  매도 주문 실패: {error_name or error_msg}", "ERROR")
                                            sell_order = None
                                        else:
                                            sell_uuid = sell_order.get('uuid', '')
                                            if sell_uuid:
                                                sell_order_uuid = sell_uuid  # UUID 저장
                                                if logger:
                                                    logger.log(f"  ✅ 매도 주문 성공 (UUID: {sell_uuid[:8]}...)", "SUCCESS")
                                            else:
                                                if logger:
                                                    logger.log(f"  매도 주문 실패: UUID가 없습니다.", "ERROR")
                                                sell_order = None
                                                sell_order_uuid = None
                                    else:
                                        if logger:
                                            logger.log(f"  매도 주문 실패: 주문 결과를 받을 수 없습니다.", "ERROR")
                                        sell_order = None
                                else:
                                    sell_order = None
                            except Exception as e:
                                if logger:
                                    logger.log(f"  매도 주문 오류: {e}", "ERROR")
                                sell_order = None
                            
                            # 실제 체결된 매수가격 가져오기
                            actual_buy_price = buy_price  # 위에서 계산한 실제 체결 가격
                            
                            # 매수한 코인 정보 저장 (실시간 모니터링용)
                            if purchased_coins_dict is not None:
                                purchased_coins_dict[coin] = {
                                    'buy_price': actual_buy_price,
                                    'buy_time': get_kst_now(),
                                    'buy_amount': buy_amount_per_coin,
                                    'buy_quantity': float(coin_balance),  # 원래 매수 수량 저장
                                    'coin_balance': float(coin_balance),  # 현재 남은 수량 (지정가 매도로 줄어들 수 있음)
                                    'sell_order_uuid': sell_order_uuid,  # 지정가 매도 주문 UUID 저장
                                    'sell_price_limit': sell_price,  # 지정가 매도 가격 저장
                                    'sell_volume': sell_volume,  # 지정가 매도 수량 저장
                                    'limit_sell_quantity': 0  # 지정가 매도 체결 수량 (초기값 0)
                                }
                            
                            results.append({
                                'coin': coin,
                                'coin_symbol': coin_symbol,
                                'status': 'success',
                                'current_price': actual_buy_price,  # 실제 체결된 매수가격 사용
                                'buy_price': actual_buy_price,  # 명시적으로 buy_price도 저장
                                'buy_amount': buy_amount_per_coin,
                                'buy_order': buy_order,
                                'sell_price': sell_price,
                                'sell_order': sell_order
                            })
                        else:
                            if logger:
                                logger.log(f"  매수된 수량이 없습니다.", "WARNING")
                            results.append({
                                'coin': coin,
                                'coin_symbol': coin_symbol,
                                'status': 'partial_fail',
                                'reason': '매수 후 잔고 없음',
                                'buy_order': buy_order,
                                'sell_order': None
                            })
                    else:
                        if logger:
                            logger.log(f"  매수 주문 실패: 주문 결과를 받을 수 없습니다.", "ERROR")
                        results.append({
                            'coin': coin,
                            'coin_symbol': coin_symbol,
                            'status': 'failed',
                            'reason': '매수 주문 실패 - 결과 없음',
                            'buy_order': None,
                            'sell_order': None
                        })
                else:
                    if logger:
                        logger.log(f"  매수 주문 실패: 주문 결과를 받을 수 없습니다.", "ERROR")
                    results.append({
                        'coin': coin,
                        'coin_symbol': coin_symbol,
                        'status': 'failed',
                        'reason': '매수 주문 실패',
                        'buy_order': None,
                        'sell_order': None
                    })
            except Exception as e:
                if logger:
                    logger.log(f"  매수 주문 오류: {e}", "ERROR")
                results.append({
                    'coin': coin,
                    'coin_symbol': coin_symbol,
                    'status': 'failed',
                    'reason': f'매수 주문 오류: {str(e)}',
                    'buy_order': None,
                    'sell_order': None
                })
            
            if idx < coin_count:
                time.sleep(0.5)
        except Exception as e:
            if logger:
                logger.log(f"  {coin_symbol}: 처리 중 오류 발생: {e}", "ERROR")
            results.append({
                'coin': coin,
                'coin_symbol': coin_symbol,
                'status': 'failed',
                'reason': f'처리 오류: {str(e)}',
                'buy_order': None,
                'sell_order': None
            })
    
    success_count = sum(1 for r in results if r['status'] == 'success')
    fail_count = len(results) - success_count
    
    if logger:
        logger.log("=" * 60, "INFO")
        logger.log("매수/매도 결과 요약", "INFO")
        logger.log("=" * 60, "INFO")
        logger.log(f"총 처리 코인: {len(results)}개", "INFO")
        logger.log(f"성공: {success_count}개", "SUCCESS")
        logger.log(f"실패: {fail_count}개", "ERROR" if fail_count > 0 else "INFO")
        
        if success_count > 0:
            logger.log("✅ 성공한 코인:", "SUCCESS")
            for result in results:
                if result['status'] == 'success':
                    # 실제 체결된 매수가격 사용 (buy_price가 있으면 사용, 없으면 current_price 사용)
                    buy_price_display = result.get('buy_price', result.get('current_price', 0))
                    sell_price_display = result.get('sell_price', 0)
                    # 소수점 처리: 가격이 10원 미만이면 소수점 2자리, 그 이상이면 소수점 1자리 또는 정수
                    if buy_price_display < 10:
                        buy_price_str = f"{buy_price_display:.2f}"
                    elif buy_price_display < 100:
                        buy_price_str = f"{buy_price_display:.2f}"
                    else:
                        buy_price_str = f"{buy_price_display:,.0f}"
                    
                    if sell_price_display < 10:
                        sell_price_str = f"{sell_price_display:.2f}"
                    elif sell_price_display < 100:
                        sell_price_str = f"{sell_price_display:.2f}"
                    else:
                        sell_price_str = f"{sell_price_display:,.0f}"
                    
                    logger.log(f"  - {result['coin_symbol']}: 매수가 {buy_price_str}원, 매도가(지정가) {sell_price_str}원", "SUCCESS")
        
        if fail_count > 0:
            logger.log("❌ 실패한 코인:", "ERROR")
            for result in results:
                if result['status'] != 'success':
                    logger.log(f"  - {result['coin_symbol']}: {result.get('reason', '알 수 없음')}", "ERROR")
    
    return results


# ============================================================================
# 메인 실행 함수
# ============================================================================

def run_trading_process(interval_minutes, target_hour, target_minute, max_slippage, price_change_min, price_change_max, volume_change_min, enable_day_candle_filter, exclude_coins, enable_auto_trade, sell_percentage, sell_ratio, investment_ratio, max_coins, logger, stop_event, root, purchased_coins_dict=None, stop_loss_pct=None, max_spread=0.2):
    """트레이딩 프로세스를 실행하는 함수"""
    try:
        # 중지 이벤트 확인
        if stop_event and stop_event.is_set():
            logger.log("프로세스가 중지되었습니다.", "WARNING")
            return
        
        if not wait_until_target_time(target_hour, target_minute, interval_minutes, logger=logger, stop_event=stop_event):
            return
        
        # 중지 이벤트 확인
        if stop_event and stop_event.is_set():
            logger.log("프로세스가 중지되었습니다.", "WARNING")
            return
        
        start_time = time.time()
        
        logger.log("업비트 원화마켓 코인 정보 수집 중...", "INFO")
        # 제외 코인 문자열을 리스트로 변환 (예: "BTC,ETH,ONDO")
        exclude_list = []
        if exclude_coins:
            exclude_list = [s.strip() for s in exclude_coins.split(',') if s.strip()]
        coins = get_all_upbit_coins(logger, exclude_coins=exclude_list)
        
        # 중지 이벤트 확인
        if stop_event and stop_event.is_set():
            logger.log("프로세스가 중지되었습니다.", "WARNING")
            return
        
        print_all_coin_list(coins, logger)
        
        final_filtered_coins = print_coins_under_price_and_volume(
            coins,
            max_price=None,
            min_volume=1000000000,
            interval_minutes=interval_minutes,
            target_hour=target_hour,
            target_minute=target_minute,
            logger=logger,
            stop_event=stop_event
        )
        
        # 중지 이벤트 확인
        if stop_event and stop_event.is_set():
            logger.log("프로세스가 중지되었습니다.", "WARNING")
            return
        
        if final_filtered_coins:
            rising_coins = print_3minute_candles(
                final_filtered_coins,
                interval_minutes=interval_minutes,
                target_hour=target_hour,
                logger=logger
            )
            
            if rising_coins:
                filtered_coins = print_filtered_coins_by_price_volume(rising_coins, price_change_min=price_change_min, price_change_max=price_change_max, volume_change_min=volume_change_min, logger=logger)
                
                if filtered_coins:
                    analysis_results = print_all_coins_market_buy_analysis(filtered_coins, buy_amount=10000000, max_spread=max_spread, logger=logger)
                    
                    if analysis_results:
                        filtered_results = print_filtered_by_slippage(
                            analysis_results, max_slippage=max_slippage, logger=logger, root=root,
                            skip_csv_and_popup=enable_day_candle_filter
                        )
                        
                        # 일봉 필터링 적용 (체크된 경우): 전체 리스트 반환, O/X 표시용
                        if filtered_results and enable_day_candle_filter:
                            filtered_results = filter_by_day_candle(filtered_results, min_bullish_ratio=0.4, logger=logger, stop_event=stop_event)
                            write_slippage_csv_and_popup(filtered_results, max_slippage, logger=logger, root=root)
                            filtered_results = [r for r in filtered_results if r.get('day_candle_pass')]
                        
                        # 자동매매가 활성화된 경우에만 실행
                        if filtered_results and enable_auto_trade:
                            logger.log("=" * 60, "INFO")
                            logger.log("💎 프리미엄 기능: 자동매매 실행", "SUCCESS")
                            logger.log("=" * 60, "INFO")
                            
                            api_key, secret_key = load_api_keys_from_json()
                            if api_key and secret_key:
                                try:
                                    upbit = pyupbit.Upbit(api_key, secret_key)
                                    buy_coins_from_list(upbit, filtered_results, sell_percentage=sell_percentage, sell_ratio=sell_ratio, investment_ratio=investment_ratio, max_coins=max_coins, logger=logger, purchased_coins_dict=purchased_coins_dict)
                                except Exception as e:
                                    logger.log(f"자동 매수/매도 실행 중 오류 발생: {e}", "ERROR")
                            else:
                                logger.log("API 키를 불러올 수 없습니다. 자동 매수/매도를 건너뜁니다.", "WARNING")
                        elif filtered_results and not enable_auto_trade:
                            logger.log("=" * 60, "INFO")
                            logger.log("펌핑코인 분석 완료 (자동매매 미사용)", "SUCCESS")
                            logger.log(f"총 {len(filtered_results)}개 코인이 선별되었습니다.", "INFO")
                            logger.log("자동매매를 사용하려면 '자동매매 (프리미엄)' 옵션을 체크하세요.", "INFO")
                            logger.log("=" * 60, "INFO")
        
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = elapsed_time % 60
        
        logger.log("=" * 60, "INFO")
        logger.log("처리 완료", "SUCCESS")
        logger.log("=" * 60, "INFO")
        if minutes > 0:
            logger.log(f"처리 시간: {minutes}분 {seconds:.2f}초", "INFO")
        else:
            logger.log(f"처리 시간: {seconds:.2f}초", "INFO")
        logger.log("=" * 60, "INFO")
    except Exception as e:
        logger.log(f"프로세스 실행 중 오류 발생: {e}", "ERROR")
        import traceback
        logger.log(traceback.format_exc(), "ERROR")


# ============================================================================
# GUI 애플리케이션
# ============================================================================

class TradingGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("업비트 펌핑코인 알리미V2")
        self.root.geometry("900x600")
        self.root.configure(bg='#ffffff')
        
        # 스타일 설정
        style = ttk.Style()
        style.theme_use('clam')
        
        # 보라색 테마 색상 설정
        purple_color = '#6B46C1'  # 보라색
        purple_light = '#8B5CF6'  # 밝은 보라색
        purple_dark = '#5B21B6'   # 어두운 보라색
        
        # 색상 설정
        style.configure('Header.TFrame', background=purple_color)
        style.configure('Title.TLabel', font=('맑은 고딕', 18, 'bold'), background=purple_color, foreground='white')
        style.configure('Subtitle.TLabel', font=('맑은 고딕', 11), background=purple_color, foreground='#E9D5FF')
        style.configure('Header.TLabel', font=('맑은 고딕', 10, 'bold'), background='#ffffff')
        style.configure('Option.TLabel', font=('맑은 고딕', 9), background='#ffffff', foreground='#374151')
        style.configure('Action.TButton', font=('맑은 고딕', 10, 'bold'))
        # LabelFrame은 기본 스타일 사용 (커스텀 스타일 제거)
        
        # Entry 스타일
        style.configure('Custom.TEntry', fieldbackground='#ffffff', borderwidth=1, relief='solid')
        
        # Button 스타일
        style.map('Action.TButton',
                 background=[('active', purple_light), ('!active', purple_color)],
                 foreground=[('active', 'white'), ('!active', 'white')])
        
        self.is_running = False
        self.process_thread = None
        self.stop_event = threading.Event()
        self.popup_queue = queue.Queue()
        
        # 매수한 코인 정보 저장 (실시간 모니터링용)
        # {coin: {'buy_price': float, 'buy_time': datetime, 'buy_amount': float}}
        self.purchased_coins = {}
        # 손절 또는 종료 시간에 매도된 코인 정보 저장 (수익률 계산용)
        # {coin: {'buy_price': float, 'sell_price': float, 'buy_amount': float, 'sell_amount': float, 'profit_pct': float, 'profit_amount': float, 'sell_time': datetime, 'sell_reason': str}}
        self.sold_coins = {}
        self.monitoring_thread = None
        self.monitoring_stop_event = threading.Event()
        
        # root 객체에 popup_queue 속성 추가 (다른 스레드에서 접근 가능하도록)
        self.root.popup_queue = self.popup_queue
        
        # 팝업창 큐 체크 시작
        self.check_popup_queue()
        
        # 종료 시간 스케줄러 시작 (초기값: 23:00)
        self.end_hour = 23
        self.end_minute = 0
        
        # 설정값 로드
        self.settings = load_settings()
        
        self.schedule_auto_sell()
        
        self.setup_ui()
        
        # 설정값 변경 시 자동 저장을 위한 trace 추가
        self.setup_settings_trace()
        
        # 프로그램 종료 시 설정 저장
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def setup_ui(self):
        # 헤더 프레임 (보라색 배너)
        header_frame = ttk.Frame(self.root, style='Header.TFrame')
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        
        # 헤더 내용
        header_content = ttk.Frame(header_frame, style='Header.TFrame')
        header_content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 아이콘과 제목
        title_container = ttk.Frame(header_content, style='Header.TFrame')
        title_container.pack(anchor='center')
        
        # 제목
        title_label = ttk.Label(title_container, text="📈 업비트 펌핑코인 알리미V2", style='Title.TLabel')
        title_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # 부제목
        subtitle_label = ttk.Label(title_container, text="업비트 자동매매 시스템", style='Subtitle.TLabel')
        subtitle_label.pack(side=tk.LEFT)
        
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 설정 섹션 헤더
        settings_header = ttk.Frame(main_frame)
        settings_header.pack(fill=tk.X, pady=(0, 15))
        
        settings_label = ttk.Label(settings_header, text="⚙️ 펌핑코인 필터링 설정", style='Header.TLabel', font=('맑은 고딕', 12, 'bold'))
        settings_label.pack(side=tk.LEFT)
        
        # 구분선
        separator1 = ttk.Separator(main_frame, orient='horizontal')
        separator1.pack(fill=tk.X, pady=(0, 20))
        
        # 옵션 설정 프레임 (왼쪽) - 스크롤 가능하게 만들기
        options_container = ttk.Frame(main_frame)
        options_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        # Canvas와 Scrollbar 생성 (가로 스크롤)
        canvas = tk.Canvas(options_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(options_container, orient="horizontal", command=canvas.xview)
        scrollable_frame = ttk.Frame(canvas)
        
        def configure_scroll_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar.set)
        
        # Canvas 높이를 스크롤 가능한 프레임에 맞추기
        def configure_canvas_height(event):
            canvas_height = event.height
            canvas.itemconfig(canvas_window, height=canvas_height)
        
        canvas.bind("<Configure>", configure_canvas_height)
        
        # 마우스 휠 바인딩 (가로 스크롤)
        def _on_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Shift + 마우스 휠도 가로 스크롤로 처리
        def _on_shift_mousewheel(event):
            canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        
        canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)
        
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="bottom", fill="x")
        
        # 옵션 설정 프레임 (스크롤 가능한 프레임 내부)
        options_frame = ttk.LabelFrame(scrollable_frame, text="", padding="15")
        options_frame.pack(fill=tk.BOTH, expand=True)
        
        # 버튼 프레임 (제일 상단) - 두 줄로 배치
        button_frame = ttk.Frame(options_frame)
        button_frame.grid(row=0, column=0, columnspan=2, pady=(0, 20), sticky=(tk.W, tk.E))
        
        # 첫 번째 줄 버튼 프레임
        button_row1 = ttk.Frame(button_frame)
        button_row1.pack(fill=tk.X, pady=(0, 5))
        
        self.start_button = ttk.Button(button_row1, text="▶ 시작", command=self.start_process, style='Action.TButton', width=12)
        self.start_button.pack(side=tk.LEFT, padx=3)
        
        self.stop_button = ttk.Button(button_row1, text="⏹ 중지", command=self.stop_process, state=tk.DISABLED, width=12)
        self.stop_button.pack(side=tk.LEFT, padx=3)
        
        self.clear_button = ttk.Button(button_row1, text="🗑 로그 지우기", command=self.clear_log, width=12)
        self.clear_button.pack(side=tk.LEFT, padx=3)
        
        # 두 번째 줄 버튼 프레임
        button_row2 = ttk.Frame(button_frame)
        button_row2.pack(fill=tk.X)
        
        # 슬리피지 필터링 결과 보기 버튼
        self.slippage_result_button = ttk.Button(button_row2, text="📊 코인 필터링 결과", command=self.show_slippage_results, width=15)
        self.slippage_result_button.pack(side=tk.LEFT, padx=3)
        
        # 당일 매매 수익률 보기 버튼
        self.profit_result_button = ttk.Button(button_row2, text="💰 수익률 보기", command=self.show_profit_results, width=15)
        self.profit_result_button.pack(side=tk.LEFT, padx=3)
        
        # 구분선
        separator = ttk.Separator(options_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 자동매매 체크박스 (프리미엄 기능) - 상단에 배치
        self.auto_trade_var = tk.BooleanVar(value=False)
        auto_trade_check = ttk.Checkbutton(options_frame, text="💎 자동매매 (프리미엄)", 
                                          variable=self.auto_trade_var,
                                          command=self.toggle_auto_trade_options)
        auto_trade_check.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 10))
        
        # 프리미엄 옵션 프레임 (자동매매 관련 옵션들) - 가로 배치
        self.premium_frame = ttk.Frame(options_frame)
        self.premium_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 지정가 매도
        sell_label_frame = ttk.Frame(self.premium_frame)
        sell_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(sell_label_frame, text="지정가 매도", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        sell_input_frame = ttk.Frame(sell_label_frame)
        sell_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.sell_percentage_var = tk.StringVar(value=self.settings.get("sell_percentage", "3"))
        sell_entry = ttk.Entry(sell_input_frame, textvariable=self.sell_percentage_var, width=8, style='Custom.TEntry')
        sell_entry.pack(side=tk.LEFT)
        ttk.Label(sell_input_frame, text="%", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # 매도 비중
        sell_ratio_label_frame = ttk.Frame(self.premium_frame)
        sell_ratio_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(sell_ratio_label_frame, text="매도 비중", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        sell_ratio_input_frame = ttk.Frame(sell_ratio_label_frame)
        sell_ratio_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.sell_ratio_var = tk.StringVar(value=self.settings.get("sell_ratio", "절반"))
        sell_ratio_combo = ttk.Combobox(sell_ratio_input_frame, textvariable=self.sell_ratio_var,
                                      values=["전부", "절반", "3분의 1"],
                                      state="readonly", width=8)
        sell_ratio_combo.pack(side=tk.LEFT)
        
        # 투자 비중
        investment_label_frame = ttk.Frame(self.premium_frame)
        investment_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        investment_label = ttk.Label(investment_label_frame, text="투자 비중", style='Option.TLabel', font=('맑은 고딕', 9, 'bold'))
        investment_label.pack(anchor=tk.W)
        ToolTip(investment_label, "원화잔고의 몇%를 투자할지")
        investment_input_frame = ttk.Frame(investment_label_frame)
        investment_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.investment_ratio_var = tk.StringVar(value=self.settings.get("investment_ratio", "100"))
        investment_entry = ttk.Entry(investment_input_frame, textvariable=self.investment_ratio_var, width=8, style='Custom.TEntry')
        investment_entry.pack(side=tk.LEFT)
        ttk.Label(investment_input_frame, text="%", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # 최대 허용 코인개수
        max_coins_label_frame = ttk.Frame(self.premium_frame)
        max_coins_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        max_coins_label = ttk.Label(max_coins_label_frame, text="최대 허용 코인개수", style='Option.TLabel', font=('맑은 고딕', 9, 'bold'))
        max_coins_label.pack(anchor=tk.W)
        ToolTip(max_coins_label, "필터링 결과 중 최대 매수할 코인 개수")
        max_coins_input_frame = ttk.Frame(max_coins_label_frame)
        max_coins_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.max_coins_var = tk.StringVar(value=self.settings.get("max_coins", "10"))
        max_coins_entry = ttk.Entry(max_coins_input_frame, textvariable=self.max_coins_var, width=8, style='Custom.TEntry')
        max_coins_entry.pack(side=tk.LEFT)
        ttk.Label(max_coins_input_frame, text="개", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # 손절%
        stop_loss_label_frame = ttk.Frame(self.premium_frame)
        stop_loss_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        stop_loss_label = ttk.Label(stop_loss_label_frame, text="손절%", style='Option.TLabel', font=('맑은 고딕', 9, 'bold'))
        stop_loss_label.pack(anchor=tk.W)
        ToolTip(stop_loss_label, "매수 가격 대비 하락 시 전량 매도")
        stop_loss_input_frame = ttk.Frame(stop_loss_label_frame)
        stop_loss_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.stop_loss_var = tk.StringVar(value=self.settings.get("stop_loss", "5"))
        stop_loss_entry = ttk.Entry(stop_loss_input_frame, textvariable=self.stop_loss_var, width=8, style='Custom.TEntry')
        stop_loss_entry.pack(side=tk.LEFT)
        ttk.Label(stop_loss_input_frame, text="%", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # 종료 시간 입력 (자동매매 카테고리로 이동)
        end_time_label_frame = ttk.Frame(self.premium_frame)
        end_time_label_frame.pack(side=tk.LEFT)
        end_time_label = ttk.Label(end_time_label_frame, text="종료 시간", style='Option.TLabel', font=('맑은 고딕', 9, 'bold'))
        end_time_label.pack(anchor=tk.W)
        ToolTip(end_time_label, "당일 매수 코인 전량 매도")
        end_time_frame = ttk.Frame(end_time_label_frame)
        end_time_frame.pack(fill=tk.X, pady=(3, 0))
        self.end_hour_var = tk.StringVar(value=self.settings.get("end_hour", "23"))
        end_hour_combo = ttk.Combobox(end_time_frame, textvariable=self.end_hour_var,
                                     values=[f"{i:02d}" for i in range(24)],
                                     state="readonly", width=5)
        end_hour_combo.pack(side=tk.LEFT)
        ttk.Label(end_time_frame, text="시", style='Option.TLabel').pack(side=tk.LEFT, padx=(3, 5))
        self.end_minute_var = tk.StringVar(value=self.settings.get("end_minute", "00"))
        end_minute_combo = ttk.Combobox(end_time_frame, textvariable=self.end_minute_var,
                                       values=[f"{i:02d}" for i in range(60)],
                                       state="readonly", width=5)
        end_minute_combo.pack(side=tk.LEFT)
        ttk.Label(end_time_frame, text="분", style='Option.TLabel').pack(side=tk.LEFT, padx=(3, 0))
        
        # 초기 상태: 프리미엄 옵션 숨김
        self.premium_frame.grid_remove()
        
        # 구분선 (자동매매 옵션과 일반 옵션 사이)
        separator2 = ttk.Separator(options_frame, orient='horizontal')
        separator2.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 첫 번째 줄: 분봉, 기준 시간
        row5_frame = ttk.Frame(options_frame)
        row5_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 1. 분봉 입력
        interval_label_frame = ttk.Frame(row5_frame)
        interval_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(interval_label_frame, text="분봉 선택", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        interval_input_frame = ttk.Frame(interval_label_frame)
        interval_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.interval_var = tk.StringVar(value=self.settings.get("interval", "1"))
        interval_combo = ttk.Combobox(interval_input_frame, textvariable=self.interval_var, 
                                     values=["1", "2", "3", "5", "15", "30", "60"], 
                                     state="readonly", width=8)
        interval_combo.pack(side=tk.LEFT)
        ttk.Label(interval_input_frame, text="분봉", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # 2. 기준 시간 입력
        time_label_frame = ttk.Frame(row5_frame)
        time_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(time_label_frame, text="기준 시간", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        time_frame = ttk.Frame(time_label_frame)
        time_frame.pack(fill=tk.X, pady=(3, 0))
        self.hour_var = tk.StringVar(value=self.settings.get("hour", "09"))
        hour_combo = ttk.Combobox(time_frame, textvariable=self.hour_var,
                                 values=[f"{i:02d}" for i in range(24)],
                                 state="readonly", width=5)
        hour_combo.pack(side=tk.LEFT)
        ttk.Label(time_frame, text="시", style='Option.TLabel').pack(side=tk.LEFT, padx=(3, 5))
        self.minute_var = tk.StringVar(value=self.settings.get("minute", "00"))
        minute_combo = ttk.Combobox(time_frame, textvariable=self.minute_var,
                                    values=[f"{i:02d}" for i in range(60)],
                                    state="readonly", width=5)
        minute_combo.pack(side=tk.LEFT)
        ttk.Label(time_frame, text="분", style='Option.TLabel').pack(side=tk.LEFT, padx=(3, 0))
        
        # 두 번째 줄: 가격 변동률, 거래량변동, 슬리피지
        row6_frame = ttk.Frame(options_frame)
        row6_frame.grid(row=6, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # 3. 가격 변동률 필터링
        price_label_frame = ttk.Frame(row6_frame)
        price_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(price_label_frame, text="가격 변동률", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        price_filter_frame = ttk.Frame(price_label_frame)
        price_filter_frame.pack(fill=tk.X, pady=(3, 0))
        self.price_change_min_var = tk.StringVar(value=self.settings.get("price_change_min", "0.2"))
        price_min_entry = ttk.Entry(price_filter_frame, textvariable=self.price_change_min_var, width=6, style='Custom.TEntry')
        price_min_entry.pack(side=tk.LEFT)
        ttk.Label(price_filter_frame, text=" % ~ ", style='Option.TLabel').pack(side=tk.LEFT)
        self.price_change_max_var = tk.StringVar(value=self.settings.get("price_change_max", "5.0"))
        price_max_entry = ttk.Entry(price_filter_frame, textvariable=self.price_change_max_var, width=6, style='Custom.TEntry')
        price_max_entry.pack(side=tk.LEFT)
        ttk.Label(price_filter_frame, text=" %", style='Option.TLabel').pack(side=tk.LEFT)
        
        # 4. 거래량변동 필터링
        volume_label_frame = ttk.Frame(row6_frame)
        volume_label_frame.pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(volume_label_frame, text="거래량변동", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        volume_input_frame = ttk.Frame(volume_label_frame)
        volume_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.volume_change_min_var = tk.StringVar(value=self.settings.get("volume_change_min", "100"))
        volume_entry = ttk.Entry(volume_input_frame, textvariable=self.volume_change_min_var, width=8, style='Custom.TEntry')
        volume_entry.pack(side=tk.LEFT)
        ttk.Label(volume_input_frame, text=" % 이상", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        
        # 5. 슬리피지 입력
        slippage_label_frame = ttk.Frame(row6_frame)
        slippage_label_frame.pack(side=tk.LEFT)
        ttk.Label(slippage_label_frame, text="슬리피지", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        slippage_input_frame = ttk.Frame(slippage_label_frame)
        slippage_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.slippage_var = tk.StringVar(value=self.settings.get("slippage", "0.3"))
        slippage_entry = ttk.Entry(slippage_input_frame, textvariable=self.slippage_var, width=8, style='Custom.TEntry')
        slippage_entry.pack(side=tk.LEFT)
        ttk.Label(slippage_input_frame, text="%", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(slippage_entry, "시장가 매수 시 허용할 최대 슬리피지 (%)")
        
        # 6. 호가스프레드 입력
        spread_label_frame = ttk.Frame(row6_frame)
        spread_label_frame.pack(side=tk.LEFT, padx=(15, 0))
        ttk.Label(spread_label_frame, text="호가스프레드", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        spread_input_frame = ttk.Frame(spread_label_frame)
        spread_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.max_spread_var = tk.StringVar(value=self.settings.get("max_spread", "0.2"))
        spread_entry = ttk.Entry(spread_input_frame, textvariable=self.max_spread_var, width=8, style='Custom.TEntry')
        spread_entry.pack(side=tk.LEFT)
        ttk.Label(spread_input_frame, text="%", style='Option.TLabel').pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(spread_entry, "호가 스프레드가 이 값보다 큰 코인은 필터링에서 제외됩니다 (%)")
        
        # 제외 코인 입력 (콤마로 구분, 예: BTC,ETH,ONDO)
        exclude_label_frame = ttk.Frame(row6_frame)
        exclude_label_frame.pack(side=tk.LEFT, padx=(15, 0))
        ttk.Label(exclude_label_frame, text="제외 코인", style='Option.TLabel', font=('맑은 고딕', 9, 'bold')).pack(anchor=tk.W)
        exclude_input_frame = ttk.Frame(exclude_label_frame)
        exclude_input_frame.pack(fill=tk.X, pady=(3, 0))
        self.exclude_coins_var = tk.StringVar(value=self.settings.get("exclude_coins", ""))
        exclude_entry = ttk.Entry(exclude_input_frame, textvariable=self.exclude_coins_var, width=20, style='Custom.TEntry')
        exclude_entry.pack(side=tk.LEFT)
        ToolTip(exclude_entry, "필터링에서 제외할 코인 심볼을 콤마로 구분해서 입력 (예: BTC,ETH,ONDO)")
        
        # 일봉 필터링 체크박스
        day_candle_label_frame = ttk.Frame(row6_frame)
        day_candle_label_frame.pack(side=tk.LEFT, padx=(15, 0))
        self.day_candle_filter_var = tk.BooleanVar(value=self.settings.get("day_candle_filter", False))
        day_candle_check = ttk.Checkbutton(day_candle_label_frame, text="일봉 필터링", 
                                          variable=self.day_candle_filter_var)
        day_candle_check.pack(anchor=tk.W)
        ToolTip(day_candle_check, "최근 일봉 10개 중 양봉 40% 이상인 코인만 선별")
        
        # 컬럼 가중치 설정
        options_frame.columnconfigure(0, weight=1)
        
        # 로그 프레임 (오른쪽)
        log_frame = ttk.LabelFrame(main_frame, text="📋 로그", padding="20")
        log_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 로그 텍스트 위젯
        self.log_text = scrolledtext.ScrolledText(log_frame, width=50, height=25, wrap=tk.WORD, 
                                                  font=('맑은 고딕', 9),
                                                  foreground="#00FF00", 
                                                  background="#000000",
                                                  selectbackground="#FFFF00",
                                                  selectforeground="#000000",
                                                  insertbackground="#00FF00")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 로거 초기화
        self.logger = GUILogger(self.log_text)
        
        # 그리드 가중치 설정
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # 초기 메시지
        self.logger.log("업비트 펌핑코인 알리미V2가 시작되었습니다.", "INFO")
        self.logger.log("옵션을 설정하고 '시작' 버튼을 클릭하세요.", "INFO")
    
    def toggle_auto_trade_options(self):
        """자동매매 체크박스 상태에 따라 프리미엄 옵션 표시/숨김"""
        if self.auto_trade_var.get():
            self.premium_frame.grid()
        else:
            self.premium_frame.grid_remove()
    
    def start_process(self):
        """프로세스 시작"""
        if self.is_running:
            messagebox.showwarning("경고", "이미 실행 중입니다.")
            return
        
        try:
            interval_minutes = int(self.interval_var.get())
            target_hour = int(self.hour_var.get())
            target_minute = int(self.minute_var.get())
            end_hour = int(self.end_hour_var.get())
            end_minute = int(self.end_minute_var.get())
            price_change_min = float(self.price_change_min_var.get())
            price_change_max = float(self.price_change_max_var.get())
            volume_change_min = float(self.volume_change_min_var.get())
            max_slippage = float(self.slippage_var.get())
            max_spread = float(self.max_spread_var.get())
            enable_day_candle_filter = self.day_candle_filter_var.get()
            exclude_coins = self.exclude_coins_var.get()
            enable_auto_trade = self.auto_trade_var.get()
            
            # 자동매매가 활성화된 경우에만 프리미엄 옵션 검증
            if enable_auto_trade:
                sell_percentage = float(self.sell_percentage_var.get())
                sell_ratio_text = self.sell_ratio_var.get()
                investment_ratio = float(self.investment_ratio_var.get())
                
                # 매도 비중 텍스트를 숫자로 변환
                if sell_ratio_text == "전부":
                    sell_ratio = 1.0
                elif sell_ratio_text == "절반":
                    sell_ratio = 0.5
                elif sell_ratio_text == "3분의 1":
                    sell_ratio = 1.0 / 3.0
                else:
                    messagebox.showerror("오류", "매도 비중을 올바르게 선택해주세요.")
                    return
                
                if sell_percentage < 0 or sell_percentage > 100:
                    messagebox.showerror("오류", "지정가 매도 %는 0~100 사이의 값이어야 합니다.")
                    return
                
                if investment_ratio < 0 or investment_ratio > 100:
                    messagebox.showerror("오류", "투자비중은 0~100 사이의 값이어야 합니다.")
                    return
                
                # 최대 허용 코인개수 가져오기
                try:
                    max_coins = int(self.max_coins_var.get())
                    if max_coins < 1:
                        messagebox.showerror("오류", "최대 허용 코인개수는 1 이상이어야 합니다.")
                        return
                except ValueError:
                    messagebox.showerror("오류", "최대 허용 코인개수를 올바르게 입력해주세요.")
                    return
            else:
                # 자동매매가 비활성화된 경우 기본값 설정 (사용되지 않음)
                sell_percentage = 3.0
                sell_ratio = 0.5
                investment_ratio = 100.0
                max_coins = None
        except ValueError:
            messagebox.showerror("오류", "모든 옵션 값을 올바르게 입력해주세요.")
            return
        
        if not (1 <= interval_minutes <= 60):
            messagebox.showerror("오류", "분봉은 1~60 사이의 값이어야 합니다.")
            return
        
        if not (0 <= target_hour <= 23):
            messagebox.showerror("오류", "기준 시간(시)은 0~23 사이의 값이어야 합니다.")
            return
        
        if not (0 <= target_minute <= 59):
            messagebox.showerror("오류", "기준 시간(분)은 0~59 사이의 값이어야 합니다.")
            return
        
        if not (0 <= end_hour <= 23):
            messagebox.showerror("오류", "종료 시간(시)은 0~23 사이의 값이어야 합니다.")
            return
        
        if not (0 <= end_minute <= 59):
            messagebox.showerror("오류", "종료 시간(분)은 0~59 사이의 값이어야 합니다.")
            return
        
        if max_slippage < 0 or max_slippage > 100:
            messagebox.showerror("오류", "슬리피지는 0~100 사이의 값이어야 합니다.")
            return
        
        if max_spread < 0 or max_spread > 10:
            messagebox.showerror("오류", "호가스프레드는 0~10 사이의 값이어야 합니다.")
            return
        
        self.is_running = True
        self.stop_event.clear()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.logger.log("=" * 60, "INFO")
        self.logger.log("프로세스 시작", "SUCCESS")
        self.logger.log("=" * 60, "INFO")
        self.logger.log(f"분봉: {interval_minutes}분봉", "INFO")
        self.logger.log(f"기준 시간: {target_hour:02d}:{target_minute:02d}", "INFO")
        self.logger.log(f"슬리피지: {max_slippage}%", "INFO")
        self.logger.log(f"호가스프레드: {max_spread}%", "INFO")
        if exclude_coins:
            self.logger.log(f"제외 코인: {exclude_coins}", "INFO")
        if enable_day_candle_filter:
            self.logger.log(f"일봉 필터링: 활성화 (양봉 40% 이상)", "INFO")
        if enable_auto_trade:
            self.logger.log(f"💎 자동매매: 활성화", "SUCCESS")
            self.logger.log(f"지정가 매도: {sell_percentage}%", "INFO")
            self.logger.log(f"매도 비중: {sell_ratio_text}", "INFO")
            self.logger.log(f"투자비중: {investment_ratio}%", "INFO")
            self.logger.log(f"최대 허용 코인개수: {max_coins}개", "INFO")
        else:
            self.logger.log(f"자동매매: 비활성화 (알리미만 사용)", "INFO")
        self.logger.log("=" * 60, "INFO")
        
        # 손절% 가져오기
        stop_loss_pct = None
        if enable_auto_trade:
            try:
                stop_loss_pct = float(self.stop_loss_var.get())
            except:
                stop_loss_pct = 5.0  # 기본값
        
        # 종료 시간 업데이트
        self.end_hour = end_hour
        self.end_minute = end_minute
        
        # 별도 스레드에서 실행
        self.process_thread = threading.Thread(
            target=run_trading_process,
            args=(interval_minutes, target_hour, target_minute, max_slippage, price_change_min, price_change_max, volume_change_min, enable_day_candle_filter, exclude_coins, enable_auto_trade, sell_percentage, sell_ratio, investment_ratio, max_coins, self.logger, self.stop_event, self.root, self.purchased_coins, stop_loss_pct, max_spread),
            daemon=True
        )
        self.process_thread.start()
        
        # 실시간 모니터링 스레드 시작 (자동매매 활성화 시)
        if enable_auto_trade and stop_loss_pct:
            self.start_price_monitoring(stop_loss_pct)
    
    def stop_process(self):
        """프로세스 중지"""
        if not self.is_running:
            return
        
        self.stop_event.set()
        self.monitoring_stop_event.set()  # 모니터링 스레드도 중지
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.logger.log("프로세스 중지 요청...", "WARNING")
    
    def setup_settings_trace(self):
        """설정값 변경 시 자동 저장을 위한 trace 설정"""
        def save_settings_callback(*args):
            self.save_current_settings()
        
        # 모든 설정 변수에 trace 추가
        self.interval_var.trace_add("write", save_settings_callback)
        self.hour_var.trace_add("write", save_settings_callback)
        self.minute_var.trace_add("write", save_settings_callback)
        self.end_hour_var.trace_add("write", save_settings_callback)
        self.end_minute_var.trace_add("write", save_settings_callback)
        self.price_change_min_var.trace_add("write", save_settings_callback)
        self.price_change_max_var.trace_add("write", save_settings_callback)
        self.volume_change_min_var.trace_add("write", save_settings_callback)
        self.slippage_var.trace_add("write", save_settings_callback)
        self.max_spread_var.trace_add("write", save_settings_callback)
        self.day_candle_filter_var.trace_add("write", save_settings_callback)
        self.exclude_coins_var.trace_add("write", save_settings_callback)
        self.auto_trade_var.trace_add("write", save_settings_callback)
        self.sell_percentage_var.trace_add("write", save_settings_callback)
        self.sell_ratio_var.trace_add("write", save_settings_callback)
        self.investment_ratio_var.trace_add("write", save_settings_callback)
        self.max_coins_var.trace_add("write", save_settings_callback)
        self.stop_loss_var.trace_add("write", save_settings_callback)
    
    def save_current_settings(self):
        """현재 설정값을 파일에 저장"""
        try:
            settings = {
                "interval": self.interval_var.get(),
                "hour": self.hour_var.get(),
                "minute": self.minute_var.get(),
                "end_hour": self.end_hour_var.get(),
                "end_minute": self.end_minute_var.get(),
                "price_change_min": self.price_change_min_var.get(),
                "price_change_max": self.price_change_max_var.get(),
                "volume_change_min": self.volume_change_min_var.get(),
                "slippage": self.slippage_var.get(),
                "max_spread": self.max_spread_var.get(),
                "day_candle_filter": self.day_candle_filter_var.get(),
                "exclude_coins": self.exclude_coins_var.get(),
                "auto_trade": self.auto_trade_var.get(),
                "sell_percentage": self.sell_percentage_var.get(),
                "sell_ratio": self.sell_ratio_var.get(),
                "investment_ratio": self.investment_ratio_var.get(),
                "max_coins": self.max_coins_var.get(),
                "stop_loss": self.stop_loss_var.get()
            }
            save_settings(settings)
        except Exception as e:
            print(f"설정 저장 오류: {e}")
    
    def on_closing(self):
        """프로그램 종료 시 설정 저장"""
        self.save_current_settings()
        self.root.destroy()
    
    def clear_log(self):
        """로그 지우기"""
        self.logger.clear()
        self.logger.log("로그가 지워졌습니다.", "INFO")
    
    def show_slippage_results(self):
        """슬리피지 필터링 결과 CSV 파일을 날짜별로 선택해서 표시"""
        import glob
        
        try:
            # 데이터 저장 디렉토리 (Railway Volume 지원)
            data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
            # slippage_results_*.csv 파일 찾기
            csv_files = glob.glob(os.path.join(data_dir, "slippage_results_*.csv"))
            
            if not csv_files:
                self.logger.log("저장된 슬리피지 필터링 결과가 없습니다.", "WARNING")
                return
            
            # 파일명에서 날짜 추출하여 정렬 (최신순)
            def extract_date(filename):
                try:
                    # slippage_results_YYYYMMDD_HHMMSS.csv 형식
                    parts = filename.replace("slippage_results_", "").replace(".csv", "").split("_")
                    if len(parts) >= 2:
                        date_str = parts[0]  # YYYYMMDD
                        time_str = parts[1]  # HHMMSS
                        return (date_str, time_str)
                    return ("", "")
                except:
                    return ("", "")
            
            # 날짜별로 정렬 (최신순)
            csv_files.sort(key=lambda x: extract_date(x), reverse=True)
            
            # 파일 선택 다이얼로그 표시
            selected_file = self.show_file_selection_dialog(
                csv_files, 
                "슬리피지 필터링 결과 선택",
                "표시할 슬리피지 필터링 결과를 선택하세요:"
            )
            
            if not selected_file:
                return
            
            # CSV 파일 읽기
            filtered_results = []
            # 설정창에 입력한 슬리피지 수치 사용
            try:
                max_slippage = float(self.slippage_var.get())
            except (ValueError, AttributeError):
                max_slippage = 0.3  # 기본값
            
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
                        'filled_count': int(row['소진호가수'].replace('개', ''))
                    })
            
            if filtered_results:
                self.logger.log(f"슬리피지 필터링 결과 표시 중... (파일: {selected_file}, 슬리피지: {max_slippage}%)", "INFO")
                show_result_popup(self.root, filtered_results, max_slippage, selected_file)
            else:
                self.logger.log("슬리피지 필터링 결과 데이터가 비어있습니다.", "WARNING")
                
        except Exception as e:
            self.logger.log(f"슬리피지 필터링 결과 표시 오류: {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    def show_profit_results(self):
        """당일 매매 수익률 표시 (CSV 파일 또는 sold_coins에서 불러오기)"""
        import glob
        
        try:
            profit_results = []
            
            # 1. 먼저 sold_coins에서 확인 (아직 초기화되지 않은 경우)
            if self.sold_coins:
                for coin, info in self.sold_coins.items():
                    profit_results.append({
                        'coin': coin,
                        'buy_price': info.get('buy_price', 0),
                        'sell_price': info.get('sell_price', 0),
                        'buy_amount': info.get('buy_amount', 0),
                        'sell_amount': info.get('sell_amount', 0),
                        'profit_pct': info.get('profit_pct', 0),
                        'profit_amount': info.get('profit_amount', 0)
                    })
                
                if profit_results:
                    self.logger.log(f"당일 매매 수익률 표시 중... (총 {len(profit_results)}개 코인)", "INFO")
                    show_profit_popup(profit_results)
                    return
            
            # 2. sold_coins가 비어있으면 CSV 파일에서 불러오기
            # 데이터 저장 디렉토리 (Railway Volume 지원)
            data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
            csv_files = glob.glob(os.path.join(data_dir, "profit_results_*.csv"))
            
            if not csv_files:
                self.logger.log("당일 매매 수익률 데이터가 없습니다.", "WARNING")
                return
            
            # 파일명에서 날짜 추출하여 정렬 (최신순)
            def extract_date(filename):
                try:
                    # profit_results_YYYYMMDD.csv 또는 profit_results_YYYYMMDD_HHMMSS.csv 형식
                    base = filename.replace("profit_results_", "").replace(".csv", "")
                    if "_" in base:
                        parts = base.split("_")
                        date_str = parts[0]  # YYYYMMDD
                        time_str = parts[1] if len(parts) > 1 else "000000"  # HHMMSS
                        return (date_str, time_str)
                    else:
                        # YYYYMMDD 형식만 있는 경우
                        return (base, "000000")
                except:
                    return ("", "")
            
            # 날짜별로 정렬 (최신순)
            csv_files.sort(key=lambda x: extract_date(x), reverse=True)
            
            # 파일 선택 다이얼로그 표시
            selected_file = self.show_file_selection_dialog(
                csv_files, 
                "당일 매매 수익률 선택",
                "표시할 당일 매매 수익률을 선택하세요:"
            )
            
            if not selected_file:
                return
            
            # CSV 파일 읽기
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
                self.logger.log(f"CSV 파일에서 수익률 데이터 불러옴: {selected_file}", "INFO")
                self.logger.log(f"당일 매매 수익률 표시 중... (총 {len(profit_results)}개 코인)", "INFO")
                show_profit_popup(profit_results)
            else:
                self.logger.log("당일 매매 수익률 데이터가 비어있습니다.", "WARNING")
                
        except Exception as e:
            self.logger.log(f"당일 매매 수익률 표시 오류: {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    def show_file_selection_dialog(self, file_list, title, message):
        """파일 선택 다이얼로그 표시"""
        if not file_list:
            return None
        
        # 다이얼로그 창 생성
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("600x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # 메시지 레이블
        msg_label = ttk.Label(dialog, text=message, font=('맑은 고딕', 10))
        msg_label.pack(pady=10)
        
        # 파일 목록 프레임
        list_frame = ttk.Frame(dialog)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # 스크롤바와 리스트박스
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=('맑은 고딕', 9))
        scrollbar.config(command=listbox.yview)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 파일 목록 추가 (날짜 형식으로 표시)
        selected_file = [None]  # 클로저를 위한 리스트
        
        def format_filename(filename):
            """파일명을 날짜 형식으로 변환"""
            try:
                # slippage_results_YYYYMMDD_HHMMSS.csv 또는 profit_results_YYYYMMDD.csv 또는 profit_results_YYYYMMDD_HHMMSS.csv
                base = filename.replace("slippage_results_", "").replace("profit_results_", "").replace(".csv", "")
                if "_" in base:
                    parts = base.split("_")
                    date_str = parts[0]  # YYYYMMDD
                    time_str = parts[1] if len(parts) > 1 else "000000"  # HHMMSS
                else:
                    # YYYYMMDD 형식만 있는 경우
                    date_str = base
                    time_str = "000000"
                
                if len(date_str) == 8:
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    if len(time_str) == 6:
                        hour = time_str[:2]
                        minute = time_str[2:4]
                        second = time_str[4:6]
                        return f"{year}-{month}-{day} {hour}:{minute}:{second} - {filename}"
                    else:
                        return f"{year}-{month}-{day} - {filename}"
            except:
                pass
            return filename
        
        for filename in file_list:
            listbox.insert(tk.END, format_filename(filename))
        
        # 첫 번째 항목 선택
        if file_list:
            listbox.selection_set(0)
            listbox.see(0)
        
        # 더블클릭으로 선택
        def on_double_click(event):
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected_file[0] = file_list[index]
                dialog.destroy()
        
        listbox.bind('<Double-Button-1>', on_double_click)
        
        # 버튼 프레임
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        def on_ok():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected_file[0] = file_list[index]
                dialog.destroy()
            else:
                messagebox.showwarning("경고", "파일을 선택해주세요.")
        
        def on_cancel():
            dialog.destroy()
        
        ok_button = ttk.Button(button_frame, text="확인", command=on_ok, width=15)
        ok_button.pack(side=tk.LEFT, padx=5)
        
        cancel_button = ttk.Button(button_frame, text="취소", command=on_cancel, width=15)
        cancel_button.pack(side=tk.LEFT, padx=5)
        
        # Enter 키로 확인
        dialog.bind('<Return>', lambda e: on_ok())
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # 다이얼로그가 닫힐 때까지 대기
        dialog.wait_window()
        
        return selected_file[0] if selected_file[0] else None
    
    def save_profit_results_to_csv(self, profit_results=None):
        """수익률 결과를 CSV 파일로 저장 (당일 데이터 업데이트 또는 새로 저장)"""
        try:
            # profit_results가 없으면 sold_coins에서 생성
            if profit_results is None:
                profit_results = []
                for coin, info in self.sold_coins.items():
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
                return
            
            # 데이터 저장 디렉토리 (Railway Volume 지원)
            data_dir = os.getenv("DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
            
            # 당일 날짜로 파일명 생성 (같은 날짜면 덮어쓰기)
            today = get_kst_now().strftime("%Y%m%d")
            csv_filename = os.path.join(data_dir, f"profit_results_{today}.csv")
            
            # 기존 파일이 있으면 읽어서 병합 (같은 코인은 최신 데이터로 업데이트)
            existing_data = {}
            if os.path.exists(csv_filename):
                try:
                    with open(csv_filename, 'r', encoding='utf-8-sig') as csvfile:
                        reader = csv.DictReader(csvfile)
                        for row in reader:
                            coin = row['코인']
                            existing_data[coin] = row
                except:
                    pass
            
            # 새 데이터로 업데이트
            for result in profit_results:
                coin = result.get('coin', '').replace("KRW-", "")
                existing_data[coin] = {
                    '코인': coin,
                    '매수가': f"{result.get('buy_price', 0):,.2f}",
                    '매도가': f"{result.get('sell_price', 0):,.2f}",
                    '매수금액': f"{result.get('buy_amount', 0):,.0f}",
                    '매도금액': f"{result.get('sell_amount', 0):,.0f}",
                    '수익률': f"{result.get('profit_pct', 0):.2f}%",
                    '수익금액': f"{result.get('profit_amount', 0):,.0f}"
                }
            
            # CSV 파일로 저장
            with open(csv_filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['코인', '매수가', '매도가', '매수금액', '매도금액', '수익률', '수익금액']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for coin_data in existing_data.values():
                    writer.writerow(coin_data)
            
            self.logger.log(f"수익률 데이터 CSV 저장 완료: {csv_filename}", "SUCCESS")
        except Exception as e:
            self.logger.log(f"수익률 데이터 CSV 저장 오류: {e}", "ERROR")
            import traceback
            traceback.print_exc()
    
    def check_popup_queue(self):
        """팝업창 큐를 주기적으로 확인하여 팝업창 표시"""
        try:
            while not self.popup_queue.empty():
                message = self.popup_queue.get_nowait()
                print(f"팝업창 큐에서 메시지 수신: {message[0] if message else 'None'}")
                if message and len(message) >= 2 and message[0] == 'show_popup':
                    _, filtered_results, max_slippage, csv_filename = message
                    print(f"팝업창 표시 호출: 코인 {len(filtered_results)}개, 슬리피지 {max_slippage}%, CSV: {csv_filename}")
                    show_result_popup(self.root, filtered_results, max_slippage, csv_filename)
        except queue.Empty:
            pass
        except Exception as e:
            print(f"팝업창 큐 확인 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # 100ms 후 다시 확인
        self.root.after(100, self.check_popup_queue)
    
    def cancel_all_orders_and_sell_all(self, coin, logger=None, return_sell_price=False):
        """특정 코인의 모든 미체결 주문 취소 후 전량 매도
        
        Args:
            coin: 코인 티커 (예: "KRW-BTC")
            logger: 로거 객체
            return_sell_price: True이면 매도 가격과 매도 금액을 반환 (수익률 계산용)
        
        Returns:
            return_sell_price가 False: 성공 여부 (bool)
            return_sell_price가 True: (성공 여부, 매도 가격, 매도 금액) 튜플
        """
        try:
            coin_symbol = coin.replace("KRW-", "")
            api_key, secret_key = load_api_keys_from_json()
            if not api_key or not secret_key:
                if logger:
                    logger.log(f"  {coin_symbol}: API 키를 불러올 수 없습니다.", "ERROR")
                return (False, None) if return_sell_price else False
            
            upbit = pyupbit.Upbit(api_key, secret_key)
            
            # 모든 미체결 주문 조회 및 취소
            orders = upbit.get_order(coin)
            if orders:
                if isinstance(orders, list):
                    for order in orders:
                        uuid = order.get('uuid', '')
                        if uuid:
                            try:
                                upbit.cancel_order(uuid)
                                if logger:
                                    logger.log(f"  {coin_symbol}: 미체결 주문 취소 (UUID: {uuid[:8]}...)", "INFO")
                            except Exception as e:
                                if logger:
                                    logger.log(f"  {coin_symbol}: 주문 취소 실패: {e}", "ERROR")
                else:
                    uuid = orders.get('uuid', '')
                    if uuid:
                        try:
                            upbit.cancel_order(uuid)
                            if logger:
                                logger.log(f"  {coin_symbol}: 미체결 주문 취소 (UUID: {uuid[:8]}...)", "INFO")
                        except Exception as e:
                            if logger:
                                logger.log(f"  {coin_symbol}: 주문 취소 실패: {e}", "ERROR")
            
            time.sleep(1)
            
            # 전량 매도
            coin_balance = upbit.get_balance(coin)
            if coin_balance and float(coin_balance) > 0:
                try:
                    # 매도 전 현재가 확인 (매도 가격 추정용)
                    current_price = pyupbit.get_current_price(coin)
                    
                    sell_result = upbit.sell_market_order(coin, float(coin_balance))
                    if sell_result:
                        if logger:
                            logger.log(f"  {coin_symbol}: 전량 매도 주문 성공 (수량: {coin_balance})", "SUCCESS")
                        
                        # 매도 가격 및 매도 금액 확인 (실제 체결 내역에서 가져오기)
                        sell_price = current_price if current_price else None
                        sell_amount = 0
                        sell_quantity = float(coin_balance)
                        
                        if sell_result and isinstance(sell_result, dict):
                            uuid = sell_result.get('uuid', '')
                            if uuid:
                                time.sleep(2)  # 체결 대기
                                try:
                                    done_orders = upbit.get_order(uuid, state="done")
                                    if done_orders:
                                        order = done_orders[0] if isinstance(done_orders, list) else done_orders
                                        executed_volume = float(order.get('executed_volume', 0))
                                        
                                        # 체결 내역(trades)에서 실제 평균 매도가 계산
                                        if executed_volume > 0:
                                            trades = order.get('trades', [])
                                            if trades and len(trades) > 0:
                                                total_revenue = 0
                                                total_volume = 0
                                                for trade in trades:
                                                    # 업비트 API의 trades 구조: price, volume, funds (체결 금액)
                                                    trade_price = float(trade.get('price', 0))
                                                    trade_volume = float(trade.get('volume', 0))
                                                    trade_funds = float(trade.get('funds', 0))  # 체결 금액 (수수료 포함 전)
                                                    
                                                    # funds가 있으면 funds 사용, 없으면 price * volume 사용
                                                    if trade_funds > 0:
                                                        total_revenue += trade_funds
                                                    elif trade_price > 0 and trade_volume > 0:
                                                        total_revenue += trade_price * trade_volume
                                                    
                                                    if trade_volume > 0:
                                                        total_volume += trade_volume
                                                
                                                if total_volume > 0:
                                                    sell_price = total_revenue / total_volume
                                                    sell_amount = total_revenue
                                                    if logger:
                                                        logger.log(f"  실제 체결 매도가: {sell_price:.4f}원 (체결 수량: {total_volume:.8f})", "INFO")
                                                else:
                                                    sell_price = current_price if current_price else None
                                                    sell_amount = executed_volume * sell_price if sell_price else 0
                                            else:
                                                # trades가 없으면 executed_volume과 현재가로 계산
                                                sell_price = current_price if current_price else None
                                                sell_amount = executed_volume * sell_price if sell_price else 0
                                                if logger:
                                                    logger.log(f"  체결 내역 없음, 현재가 사용: {sell_price:.4f}원", "WARNING")
                                        else:
                                            sell_price = current_price if current_price else None
                                            sell_amount = sell_quantity * sell_price if sell_price else 0
                                except Exception as e:
                                    if logger:
                                        logger.log(f"  매도 체결 가격 조회 오류: {e}", "WARNING")
                                    sell_price = current_price if current_price else None
                                    sell_amount = sell_quantity * sell_price if sell_price else 0
                            else:
                                sell_price = current_price if current_price else None
                                sell_amount = sell_quantity * sell_price if sell_price else 0
                        else:
                            sell_price = current_price if current_price else None
                            sell_amount = sell_quantity * sell_price if sell_price else 0
                        
                        if return_sell_price:
                            return (True, sell_price, sell_amount)
                        return True
                    else:
                        if logger:
                            logger.log(f"  {coin_symbol}: 전량 매도 주문 실패", "ERROR")
                        return (False, None, 0) if return_sell_price else False
                except Exception as e:
                    if logger:
                        logger.log(f"  {coin_symbol}: 전량 매도 주문 오류: {e}", "ERROR")
                    return (False, None) if return_sell_price else False
            else:
                if logger:
                    logger.log(f"  {coin_symbol}: 매도할 수량이 없습니다.", "WARNING")
                return (False, None) if return_sell_price else False
        except Exception as e:
            coin_symbol = coin.replace("KRW-", "") if coin else "알 수 없음"
            if logger:
                logger.log(f"  {coin_symbol}: 처리 중 오류: {e}", "ERROR")
            return (False, None) if return_sell_price else False
    
    def start_price_monitoring(self, stop_loss_pct):
        """실시간 가격 모니터링 스레드 시작"""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
        
        self.monitoring_stop_event.clear()
        
        def monitor_prices():
            """실시간 가격 모니터링"""
            while not self.monitoring_stop_event.is_set():
                try:
                    if not self.purchased_coins:
                        time.sleep(5)
                        continue
                    
                    api_key, secret_key = load_api_keys_from_json()
                    if not api_key or not secret_key:
                        time.sleep(10)
                        continue
                    
                    upbit = pyupbit.Upbit(api_key, secret_key)
                    
                    # 매수한 코인들 가격 확인 및 지정가 매도 체결 확인
                    coins_to_remove = []
                    for coin, info in list(self.purchased_coins.items()):
                        if self.monitoring_stop_event.is_set():
                            break
                        
                        try:
                            coin_symbol = coin.replace("KRW-", "")
                            
                            # 1. 지정가 매도 주문 체결 확인
                            sell_order_uuid = info.get('sell_order_uuid')
                            if sell_order_uuid:
                                try:
                                    order_info = upbit.get_order(sell_order_uuid)
                                    if order_info:
                                        if isinstance(order_info, list):
                                            order_info = order_info[0] if len(order_info) > 0 else None
                                        
                                        if order_info:
                                            order_state = order_info.get('state', '')
                                            executed_volume = float(order_info.get('executed_volume', 0))
                                            
                                            # 지정가 매도가 완전히 체결된 경우 (done 상태이고 executed_volume > 0)
                                            if order_state == 'done' and executed_volume > 0:
                                                self.logger.log(f"✅ {coin_symbol}: 지정가 매도 익절 완료 (체결 수량: {executed_volume})", "SUCCESS")
                                                
                                                # 체결 내역에서 실제 매도 가격 가져오기
                                                sell_price = info.get('sell_price_limit', 0)  # 기본값: 지정가
                                                sell_amount = 0
                                                
                                                trades = order_info.get('trades', [])
                                                if trades and len(trades) > 0:
                                                    total_revenue = 0
                                                    total_volume = 0
                                                    for trade in trades:
                                                        trade_funds = float(trade.get('funds', 0))
                                                        trade_volume = float(trade.get('volume', 0))
                                                        
                                                        if trade_funds > 0:
                                                            total_revenue += trade_funds
                                                        elif float(trade.get('price', 0)) > 0 and trade_volume > 0:
                                                            total_revenue += float(trade.get('price', 0)) * trade_volume
                                                        
                                                        if trade_volume > 0:
                                                            total_volume += trade_volume
                                                    
                                                    if total_volume > 0:
                                                        sell_price = total_revenue / total_volume
                                                        sell_amount = total_revenue
                                                
                                                # 매도 금액이 없으면 계산
                                                if sell_amount == 0:
                                                    sell_volume = info.get('sell_volume', executed_volume)
                                                    sell_amount = sell_volume * sell_price if sell_price > 0 else 0
                                                
                                                # 수익률 계산
                                                buy_price = info.get('buy_price', 0)
                                                coin_balance = info.get('coin_balance', 0)
                                                
                                                # 지정가 매도 체결 수량 (정확한 계산)
                                                limit_sell_quantity = executed_volume
                                                
                                                # 매수 정보 가져오기
                                                buy_quantity = info.get('buy_quantity', coin_balance)  # 원래 매수 수량
                                                
                                                # 지정가 매도: 지정가 체결가격 * 체결수량
                                                # buy_amount_for_sold: 지정가 매도된 부분의 매수금액
                                                if limit_sell_quantity > 0 and buy_quantity > 0:
                                                    # 지정가 매도된 부분의 매수금액 = (지정가 매도 수량 / 원래 매수 수량) * 원래 매수금액
                                                    buy_amount_for_sold = (limit_sell_quantity / buy_quantity) * (buy_quantity * buy_price)
                                                    profit_pct = ((sell_price / buy_price) - 1) * 100 if buy_price > 0 else 0
                                                    profit_amount = sell_amount - buy_amount_for_sold
                                                    
                                                    # 지정가 익절 정보를 sold_coins에 저장 (부분 매도 기록용)
                                                    # 같은 코인이 이미 sold_coins에 있으면 수익률 정보를 업데이트
                                                    if coin in self.sold_coins:
                                                        # 기존 정보에 추가 (여러 번 부분 매도 가능)
                                                        existing = self.sold_coins[coin]
                                                        existing['buy_amount'] = existing.get('buy_amount', 0) + buy_amount_for_sold
                                                        existing['sell_amount'] = existing.get('sell_amount', 0) + sell_amount
                                                        existing['limit_sell_quantity'] = existing.get('limit_sell_quantity', 0) + limit_sell_quantity
                                                        # 전체 수익률 재계산
                                                        if existing['buy_amount'] > 0:
                                                            existing['profit_pct'] = ((existing['sell_amount'] / existing['buy_amount']) - 1) * 100
                                                            existing['profit_amount'] = existing['sell_amount'] - existing['buy_amount']
                                                    else:
                                                        self.sold_coins[coin] = {
                                                            'buy_price': buy_price,
                                                            'buy_quantity': buy_quantity,
                                                            'limit_sell_price': sell_price,  # 지정가 매도 체결가격
                                                            'limit_sell_quantity': limit_sell_quantity,  # 지정가 매도 체결수량
                                                            'buy_amount': buy_amount_for_sold,  # 지정가 매도된 부분의 매수금액
                                                            'sell_amount': sell_amount,  # 지정가 매도 금액 (체결가격 * 체결수량)
                                                            'profit_pct': profit_pct,
                                                            'profit_amount': profit_amount,
                                                            'sell_time': get_kst_now(),
                                                            'sell_reason': '지정가 익절'
                                                        }
                                                    
                                                    # purchased_coins에 지정가 매도 체결 수량 저장
                                                    info['limit_sell_quantity'] = limit_sell_quantity
                                                    
                                                    # 남은 수량 계산 및 업데이트
                                                    remaining_balance = buy_quantity - limit_sell_quantity
                                                    
                                                    if remaining_balance > 0:
                                                        # 남은 수량이 있으면 purchased_coins에서 coin_balance만 업데이트하고 제거하지 않음
                                                        # 지정가 매도 주문 UUID를 제거하여 더 이상 모니터링하지 않도록 함
                                                        info['coin_balance'] = remaining_balance
                                                        info['sell_order_uuid'] = None  # 지정가 매도 완료 표시
                                                        self.logger.log(f"  {coin_symbol}: 지정가 매도 완료 ({limit_sell_quantity}개), 남은 수량 {remaining_balance}개 (종료시간에 매도 예정)", "INFO")
                                                    else:
                                                        # 남은 수량이 없으면 purchased_coins에서 제거
                                                        coins_to_remove.append(coin)
                                                    
                                                    # 지정가 익절 시에도 CSV 저장
                                                    self.save_profit_results_to_csv()
                                                    
                                                    continue  # 다음 코인으로
                                except Exception as e:
                                    # 주문 조회 실패는 무시하고 계속 진행
                                    pass
                            
                            # 2. 손절 조건 확인
                            current_price = pyupbit.get_current_price(coin)
                            if not current_price:
                                continue
                            
                            buy_price = info['buy_price']
                            price_drop_pct = ((buy_price - current_price) / buy_price) * 100
                            
                            # 손절 조건 확인
                            if price_drop_pct >= stop_loss_pct:
                                coin_symbol = coin.replace("KRW-", "")
                                self.logger.log(f"⚠️ 손절 조건 발생: {coin_symbol} (매수가: {buy_price:,.2f}원, 현재가: {current_price:,.2f}원, 하락률: {price_drop_pct:.2f}%)", "WARNING")
                                self.logger.log(f"  {coin_symbol}: 미체결 주문 취소 및 전량 매도 실행 중...", "INFO")
                                
                                # 미체결 주문 취소 및 전량 매도 (매도 가격, 매도 금액 반환)
                                result = self.cancel_all_orders_and_sell_all(coin, logger=self.logger, return_sell_price=True)
                                
                                if result and len(result) >= 2:
                                    success = result[0]
                                    sell_price = result[1] if len(result) > 1 else None
                                    sell_amount = result[2] if len(result) > 2 else 0
                                    
                                    if success:
                                        self.logger.log(f"  ✅ {coin_symbol}: 손절 매도 완료", "SUCCESS")
                                        
                                        # 매도 가격이 없으면 현재가 사용
                                        if not sell_price:
                                            sell_price = current_price
                                        
                                        # 손절된 코인 정보를 sold_coins에 저장 (수익률 계산용)
                                        buy_price = info.get('buy_price', 0)
                                        coin_balance = info.get('coin_balance', 0)  # 프로그램이 매수한 실제 수량
                                        
                                        # 프로그램이 매수한 수량만으로 계산
                                        buy_amount = coin_balance * buy_price if coin_balance > 0 and buy_price > 0 else 0
                                        
                                        # 매도 금액이 없으면 계산
                                        if sell_amount == 0:
                                            sell_amount = coin_balance * sell_price if coin_balance > 0 and sell_price else 0
                                        
                                        # 수익률 계산: 매수가격과 매도가격 기준
                                        profit_pct = ((sell_price / buy_price) - 1) * 100 if buy_price > 0 else 0
                                        profit_amount = sell_amount - buy_amount
                                        
                                        self.sold_coins[coin] = {
                                            'buy_price': buy_price,
                                            'sell_price': sell_price,
                                            'buy_amount': buy_amount,
                                            'sell_amount': sell_amount,
                                            'coin_balance': coin_balance,  # 프로그램이 매수한 실제 수량 저장
                                            'profit_pct': profit_pct,
                                            'profit_amount': profit_amount,
                                            'sell_time': get_kst_now(),
                                            'sell_reason': '손절'
                                        }
                                        
                                        # 손절 시에도 CSV 저장 (당일 데이터 업데이트)
                                        self.save_profit_results_to_csv()
                                    
                                    coins_to_remove.append(coin)
                                else:
                                    self.logger.log(f"  ❌ {coin_symbol}: 손절 매도 실패", "ERROR")
                        except Exception as e:
                            self.logger.log(f"  {coin}: 가격 확인 중 오류: {e}", "ERROR")
                    
                    # 처리 완료된 코인 제거
                    for coin in coins_to_remove:
                        self.purchased_coins.pop(coin, None)
                    
                    time.sleep(5)  # 5초마다 확인
                except Exception as e:
                    self.logger.log(f"모니터링 중 오류: {e}", "ERROR")
                    time.sleep(10)
        
        self.monitoring_thread = threading.Thread(target=monitor_prices, daemon=True)
        self.monitoring_thread.start()
        self.logger.log("실시간 가격 모니터링 시작 (손절%: {}%)".format(stop_loss_pct), "INFO")
    
    def schedule_auto_sell(self):
        """설정된 종료 시간에 당일 매수 코인 전량 매도 스케줄러"""
        def check_and_sell():
            last_logged_second = -1  # 마지막으로 로그를 출력한 초
            while True:
                try:
                    now = get_kst_now()
                    
                    # 종료 시간까지 남은 시간 계산
                    end_time = now.replace(hour=self.end_hour, minute=self.end_minute, second=0, microsecond=0)
                    if end_time <= now:
                        # 종료 시간이 오늘 지났으면 내일로 설정
                        end_time += timedelta(days=1)
                    
                    time_until_end = end_time - now
                    hours_left = time_until_end.seconds // 3600
                    minutes_left = (time_until_end.seconds % 3600) // 60
                    seconds_left = time_until_end.seconds % 60
                    
                    # 매 분마다 또는 1분 이하일 때는 매 10초마다 로그 출력
                    if now.second != last_logged_second and (now.second % 10 == 0 or (hours_left == 0 and minutes_left == 0)):
                        if self.purchased_coins or self.sold_coins:
                            if hours_left > 0:
                                self.logger.log(f"⏰ 종료 시간까지 남은 시간: {hours_left}시간 {minutes_left}분 ({self.end_hour:02d}:{self.end_minute:02d})", "INFO")
                            elif minutes_left > 0:
                                self.logger.log(f"⏰ 종료 시간까지 남은 시간: {minutes_left}분 {seconds_left}초 ({self.end_hour:02d}:{self.end_minute:02d})", "INFO")
                            else:
                                self.logger.log(f"⏰ 종료 시간까지 남은 시간: {seconds_left}초 ({self.end_hour:02d}:{self.end_minute:02d})", "WARNING")
                        last_logged_second = now.second
                    
                    # 설정된 종료 시간 확인
                    if now.hour == self.end_hour and now.minute == self.end_minute:
                        # purchased_coins 또는 sold_coins가 있으면 처리
                        if self.purchased_coins or self.sold_coins:
                            self.logger.log("=" * 60, "INFO")
                            self.logger.log(f"종료 시간 ({self.end_hour:02d}:{self.end_minute:02d}): 당일 매수 코인 전량 매도 실행", "WARNING")
                            self.logger.log("=" * 60, "INFO")
                            
                            api_key, secret_key = load_api_keys_from_json()
                            if api_key and secret_key:
                                upbit = pyupbit.Upbit(api_key, secret_key)
                                
                                # 수익률 계산을 위한 결과 리스트 (손절된 코인 포함)
                                profit_results = []
                                coins_to_remove = []
                                
                                # 1. 아직 매도되지 않은 코인들 전량 매도
                                for coin, info in list(self.purchased_coins.items()):
                                    coin_symbol = coin.replace("KRW-", "")
                                    self.logger.log(f"  {coin_symbol}: 미체결 주문 취소 및 전량 매도 실행 중...", "INFO")
                                    
                                    buy_price = info.get('buy_price', 0)
                                    buy_amount = info.get('buy_amount', 0)
                                    
                                    # 전량 매도 (매도 가격, 매도 금액 반환)
                                    result = self.cancel_all_orders_and_sell_all(coin, logger=self.logger, return_sell_price=True)
                                    
                                    if result and len(result) >= 2:
                                        success = result[0]
                                        sell_price = result[1] if len(result) > 1 else None
                                        sell_amount = result[2] if len(result) > 2 else 0
                                        
                                        if success:
                                            self.logger.log(f"  ✅ {coin_symbol}: 전량 매도 완료", "SUCCESS")
                                            
                                            # 매도 가격이 없으면 현재가 사용
                                            if not sell_price:
                                                sell_price = pyupbit.get_current_price(coin) or buy_price
                                            
                                            # 프로그램이 매수한 수량만으로 계산
                                            coin_balance = info.get('coin_balance', 0)  # 프로그램이 매수한 실제 수량
                                            buy_price = info.get('buy_price', 0)
                                            
                                            # 프로그램이 매수한 수량만으로 매수금액 계산
                                            buy_amount = coin_balance * buy_price if coin_balance > 0 and buy_price > 0 else 0
                                            
                                            # 매도 금액이 없으면 계산
                                            if sell_amount == 0:
                                                sell_amount = coin_balance * sell_price if coin_balance > 0 and sell_price else 0
                                            
                                            # 수익률 계산: 매수가격과 매도가격 기준
                                            profit_pct = ((sell_price / buy_price) - 1) * 100 if buy_price > 0 else 0
                                            profit_amount = sell_amount - buy_amount
                                        
                                        # sold_coins에 저장 (지정가 매도 정보가 있으면 병합)
                                        if coin in self.sold_coins:
                                            # 기존 지정가 매도 정보와 병합
                                            existing = self.sold_coins[coin]
                                            existing['buy_amount'] = existing.get('buy_amount', 0) + buy_amount
                                            existing['sell_amount'] = existing.get('sell_amount', 0) + sell_amount
                                            existing['coin_balance'] = existing.get('coin_balance', 0) + coin_balance
                                            # 전체 수익률 재계산
                                            if existing['buy_amount'] > 0:
                                                existing['profit_pct'] = ((existing['sell_amount'] / existing['buy_amount']) - 1) * 100
                                                existing['profit_amount'] = existing['sell_amount'] - existing['buy_amount']
                                            existing['sell_reason'] = existing.get('sell_reason', '') + ', 종료시간'
                                        else:
                                            self.sold_coins[coin] = {
                                                'buy_price': buy_price,
                                                'sell_price': sell_price,
                                                'buy_amount': buy_amount,
                                                'sell_amount': sell_amount,
                                                'coin_balance': coin_balance,  # 프로그램이 매수한 실제 수량 저장
                                                'profit_pct': profit_pct,
                                                'profit_amount': profit_amount,
                                                'sell_time': get_kst_now(),
                                                'sell_reason': '종료시간'
                                            }
                                        
                                        profit_results.append({
                                            'coin': coin,
                                            'buy_price': buy_price,
                                            'sell_price': sell_price,
                                            'buy_amount': buy_amount,
                                            'sell_amount': sell_amount,
                                            'profit_pct': profit_pct,
                                            'profit_amount': profit_amount
                                        })
                                        
                                        coins_to_remove.append(coin)
                                    else:
                                        self.logger.log(f"  ❌ {coin_symbol}: 전량 매도 실패", "ERROR")
                                
                                # 처리 완료된 코인 제거
                                for coin in coins_to_remove:
                                    self.purchased_coins.pop(coin, None)
                                
                                # 2. 손절된 코인들도 수익률 계산에 포함
                                for coin, info in self.sold_coins.items():
                                    # 이미 profit_results에 있는지 확인 (중복 방지)
                                    coin_exists = any(r['coin'] == coin for r in profit_results)
                                    if not coin_exists:
                                        profit_results.append({
                                            'coin': coin,
                                            'buy_price': info.get('buy_price', 0),
                                            'sell_price': info.get('sell_price', 0),
                                            'buy_amount': info.get('buy_amount', 0),
                                            'sell_amount': info.get('sell_amount', 0),
                                            'profit_pct': info.get('profit_pct', 0),
                                            'profit_amount': info.get('profit_amount', 0)
                                        })
                                
                                self.logger.log("=" * 60, "INFO")
                                self.logger.log(f"종료 시간 ({self.end_hour:02d}:{self.end_minute:02d}) 전량 매도 완료", "SUCCESS")
                                self.logger.log("=" * 60, "INFO")
                                
                                # 수익률 팝업창 표시 (손절 포함 모든 코인)
                                if profit_results:
                                    self.logger.log(f"수익률 팝업창 표시 중... (총 {len(profit_results)}개 코인)", "INFO")
                                    show_profit_popup(profit_results)
                                    
                                    # CSV 파일로 저장 (수익률 보기 버튼에서 불러오기 위해)
                                    self.save_profit_results_to_csv(profit_results)
                                    
                                    # sold_coins 초기화 (다음 날을 위해)
                                    self.sold_coins.clear()
                            
                            # 다음 날까지 대기 (1분 후 다시 체크)
                            time.sleep(60)
                        else:
                            time.sleep(60)
                    else:
                        # 종료 시간까지 남은 시간 계산 및 표시
                        end_time = now.replace(hour=self.end_hour, minute=self.end_minute, second=0, microsecond=0)
                        if end_time <= now:
                            # 종료 시간이 오늘 지났으면 내일로 설정
                            end_time += timedelta(days=1)
                        
                        time_until_end = end_time - now
                        hours_left = time_until_end.seconds // 3600
                        minutes_left = (time_until_end.seconds % 3600) // 60
                        seconds_left = time_until_end.seconds % 60
                        
                        # 매수한 코인이 있고, 매 분마다 또는 1분 이하일 때는 매 10초마다 로그 출력
                        if self.purchased_coins or self.sold_coins:
                            if now.second % 10 == 0:  # 10초마다
                                if hours_left > 0:
                                    self.logger.log(f"⏰ 종료 시간까지 남은 시간: {hours_left}시간 {minutes_left}분 ({self.end_hour:02d}:{self.end_minute:02d})", "INFO")
                                elif minutes_left > 0:
                                    self.logger.log(f"⏰ 종료 시간까지 남은 시간: {minutes_left}분 {seconds_left}초 ({self.end_hour:02d}:{self.end_minute:02d})", "INFO")
                                else:
                                    self.logger.log(f"⏰ 종료 시간까지 남은 시간: {seconds_left}초 ({self.end_hour:02d}:{self.end_minute:02d})", "WARNING")
                        
                        time.sleep(10)  # 10초마다 시간 확인
                except Exception as e:
                    self.logger.log(f"종료 시간 스케줄러 오류: {e}", "ERROR")
                    time.sleep(60)
        
        scheduler_thread = threading.Thread(target=check_and_sell, daemon=True)
        scheduler_thread.start()


def main():
    """메인 함수"""
    root = tk.Tk()
    app = TradingGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

