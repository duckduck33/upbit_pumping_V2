# ====== 텔레그램 정보 ======
TELEGRAM_BOT_TOKEN = '6865900648:AAHL3VUd26fMubuyXRWqZRf5yCrPle7QzG8'
CHAT_ID = "1748799133"
channel_id = '1748799133'  # 그룹 채널 id는 음수 
# channel_id = '-1002204342572'  # 그룹 채널 id는 음수 

import requests
from datetime import datetime
import pytz

KST = pytz.timezone('Asia/Seoul')

def get_kst_now():
    """한국 시간(KST)으로 현재 시간을 반환합니다."""
    return datetime.now(KST)

def send_telegram_message(message, chat_id=None, parse_mode='HTML'):
    """텔레그램 메시지를 전송합니다.
    
    Args:
        message: 전송할 메시지 내용
        chat_id: 채팅 ID (None이면 기본 CHAT_ID 사용)
        parse_mode: 메시지 파싱 모드 (HTML, Markdown 등)
    """
    if chat_id is None:
        chat_id = CHAT_ID
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': parse_mode
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"텔레그램 메시지 전송 실패: {e}")
        return False

def send_analysis_start_notification(settings_info):
    """프로그램 시작 알림을 전송합니다."""
    now = get_kst_now()
    message = f"""
🚀 <b>업비트 펌핑코인 알리미 - 분석 시작</b>

⏰ 시작 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}

📋 <b>분석 설정</b>
• 분봉: 1분봉 (정시 기준 비교)
• 가격 변동률: {settings_info.get('price_change_min', 0.2)}% ~ {settings_info.get('price_change_max', 5.0)}%
• 거래량 변동 최소: {settings_info.get('volume_change_min', 100)}%
• 슬리피지 최대: {settings_info.get('slippage', 0.3)}%
• 호가스프레드 최대: {settings_info.get('max_spread', 0.2)}%
• 일봉 필터링: {'활성화' if settings_info.get('day_candle_filter', False) else '비활성화'}
• 자동매매: {'활성화' if settings_info.get('auto_trade', False) else '비활성화'}
"""
    if settings_info.get('exclude_coins'):
        message += f"• 제외 코인: {settings_info.get('exclude_coins')}\n"
    
    send_telegram_message(message, chat_id=channel_id)

def send_filtering_result_notification(filtered_results, enable_day_candle_filter=False):
    """최종 필터링 결과 알림을 전송합니다."""
    if not filtered_results:
        message = """
📊 <b>필터링 결과</b>

❌ 필터링 통과 코인이 없습니다.
"""
        send_telegram_message(message, chat_id=channel_id)
        return
    
    now = get_kst_now()
    message = f"""
📊 <b>최종 필터링 결과</b>

⏰ 분석 완료 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}
✅ 통과 코인: {len(filtered_results)}개

<b>상위 10개 코인:</b>
"""
    
    # 일봉 필터링이 활성화된 경우 통과한 코인만 표시
    if enable_day_candle_filter:
        passed_coins = [r for r in filtered_results if r.get('day_candle_pass', False)]
        display_coins = passed_coins[:10]
    else:
        display_coins = filtered_results[:10]
    
    for idx, result in enumerate(display_coins, 1):
        coin = result.get('coin', '').replace("KRW-", "")
        price_change = result.get('price_change', 0)
        volume_change = result.get('volume_change', 0)
        slippage = result.get('price_diff_pct', 0)
        spread = result.get('spread_pct', 0)
        day_filter = "✅" if result.get('day_candle_pass', False) else "❌"
        
        message += f"""
{idx}. <b>{coin}</b> {day_filter}
   가격변동: +{price_change:.2f}%
   거래량변동: +{volume_change:.2f}%
   슬리피지: {slippage:.4f}%
   호가스프레드: {spread:.4f}%
"""
    
    if len(filtered_results) > 10:
        message += f"\n... 외 {len(filtered_results) - 10}개 코인"
    
    send_telegram_message(message, chat_id=channel_id)

def send_auto_trade_end_notification(time_str):
    """자동매매 종료 알림을 전송합니다.
    
    Args:
        time_str: 종료 시간 문자열 (예: "5분", "2시간")
    """
    now = get_kst_now()
    message = f"""
⏰ <b>자동매매 종료 알림</b>

종료 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}
설정된 종료 시간 ({time_str})이 경과하여 자동으로 전량 매도가 완료되었습니다.
"""
    send_telegram_message(message, chat_id=channel_id)

def send_profit_notification(profit_results):
    """최종 수익률 알림을 전송합니다."""
    if not profit_results:
        return
    
    now = get_kst_now()
    
    # 각 코인의 buy_amount와 sell_amount를 정확히 합산
    # sold_coins에 저장된 buy_amount와 sell_amount는 이미 지정가 매도 + 종료시간 매도가 누적된 값
    # 하지만 각 코인별로 직접 계산하여 정확성 보장
    total_buy_amount = 0
    total_sell_amount = 0
    
    for r in profit_results:
        buy_price = r.get('buy_price', 0)
        buy_quantity = r.get('buy_quantity', 0)
        limit_sell_price = r.get('limit_sell_price', 0)
        limit_sell_quantity = r.get('limit_sell_quantity', 0)
        end_sell_price = r.get('end_sell_price', 0)
        end_sell_quantity = r.get('end_sell_quantity', 0)
        
        # 매도 사유 확인
        sell_reason = r.get('sell_reason', '')
        is_stop_loss = sell_reason == '손절'
        
        # 각 코인의 실제 매수금액과 매도금액 계산
        coin_buy_amount = 0
        coin_sell_amount = 0
        
        # 손절 매도인 경우
        if is_stop_loss:
            # 손절은 전량 매도이므로 sold_coins에 저장된 값 사용
            coin_buy_amount = r.get('buy_amount', 0)
            coin_sell_amount = r.get('sell_amount', 0)
        else:
            # 지정가 매도 부분
            if limit_sell_price > 0 and limit_sell_quantity > 0:
                coin_buy_amount += limit_sell_quantity * buy_price  # 지정가 매도된 부분의 매수금액
                coin_sell_amount += limit_sell_price * limit_sell_quantity  # 지정가 매도 금액
            
            # 종료시간 매도 부분
            if end_sell_price > 0 and end_sell_quantity > 0:
                coin_buy_amount += end_sell_quantity * buy_price  # 종료시간 매도된 부분의 매수금액
                coin_sell_amount += end_sell_price * end_sell_quantity  # 종료시간 매도 금액
            
            # 지정가 매도와 종료시간 매도가 모두 없는 경우 (이론적으로는 발생하지 않아야 함)
            if coin_buy_amount == 0 and coin_sell_amount == 0:
                # sold_coins에 저장된 값 사용
                coin_buy_amount = r.get('buy_amount', 0)
                coin_sell_amount = r.get('sell_amount', 0)
        
        total_buy_amount += coin_buy_amount
        total_sell_amount += coin_sell_amount
    
    # 총 수익률과 수익금액 계산
    total_profit_amount = total_sell_amount - total_buy_amount
    total_profit_pct = ((total_sell_amount / total_buy_amount) - 1) * 100 if total_buy_amount > 0 else 0
    
    message = f"""
💰 <b>최종 수익률 알림</b>

⏰ 계산 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}
📊 매매 코인 수: {len(profit_results)}개

<b>코인별 수익률:</b>
"""
    
    for idx, result in enumerate(profit_results, 1):
        coin = result.get('coin', '').replace("KRW-", "")
        buy_price = result.get('buy_price', 0)
        buy_quantity = result.get('buy_quantity', 0)
        sell_price = result.get('sell_price', 0)  # 전체 평균 매도가
        profit_pct = result.get('profit_pct', 0)
        profit_amount = result.get('profit_amount', 0)
        profit_emoji = "📈" if profit_pct >= 0 else "📉"
        
        # 매도 사유 확인
        sell_reason = result.get('sell_reason', '')
        is_stop_loss = sell_reason == '손절'
        
        # 지정가 매도 정보
        limit_sell_price = result.get('limit_sell_price', 0)
        limit_sell_quantity = result.get('limit_sell_quantity', 0)
        limit_sell_executed = limit_sell_price > 0 and limit_sell_quantity > 0
        
        # 종료시간 매도 정보
        end_sell_price = result.get('end_sell_price', 0)
        end_sell_quantity = result.get('end_sell_quantity', 0)
        
        message += f"""
{idx}. <b>{coin}</b> {profit_emoji}
   매수가: {buy_price:,.0f}원 (수량: {buy_quantity:.6f})
   전체 수익률: {profit_pct:+.2f}%
   전체 수익금액: {profit_amount:+,.0f}원
"""
        
        # 손절 매도인 경우
        if is_stop_loss:
            message += f"""
   ⚠️ <b>손절 매도</b>
   • 매도가: {sell_price:,.0f}원
   • 매도수량: {buy_quantity:.6f}
   • 손절 수익률: {profit_pct:+.2f}%
   • 손절 수익금액: {profit_amount:+,.0f}원
"""
        # 지정가 매도 체결 여부 및 수익률
        elif limit_sell_executed:
            # 지정가 매도된 부분의 매수금액 계산
            limit_buy_amount = (limit_sell_quantity / buy_quantity) * (buy_quantity * buy_price) if buy_quantity > 0 else 0
            limit_sell_amount = limit_sell_price * limit_sell_quantity
            limit_profit_pct = ((limit_sell_price / buy_price) - 1) * 100 if buy_price > 0 else 0
            limit_profit_amount = limit_sell_amount - limit_buy_amount
            
            message += f"""
   ✅ <b>지정가 매도 체결</b>
   • 체결가: {limit_sell_price:,.0f}원
   • 체결수량: {limit_sell_quantity:.6f}
   • 지정가 수익률: {limit_profit_pct:+.2f}%
   • 지정가 수익금액: {limit_profit_amount:+,.0f}원
"""
            
            # 종료시간 매도 정보 (지정가 매도가 체결된 경우)
            if end_sell_price > 0 and end_sell_quantity > 0:
                end_buy_amount = (end_sell_quantity / buy_quantity) * (buy_quantity * buy_price) if buy_quantity > 0 else 0
                end_sell_amount = end_sell_price * end_sell_quantity
                end_profit_pct = ((end_sell_price / buy_price) - 1) * 100 if buy_price > 0 else 0
                end_profit_amount = end_sell_amount - end_buy_amount
                
                message += f"""
   ⏰ <b>종료시간 매도 (남은 절반)</b>
   • 매도가: {end_sell_price:,.0f}원
   • 매도수량: {end_sell_quantity:.6f}
   • 종료시간 수익률: {end_profit_pct:+.2f}%
   • 종료시간 수익금액: {end_profit_amount:+,.0f}원
"""
        else:
            message += f"""
   ❌ <b>지정가 매도 미체결</b>
"""
            
            # 종료시간 매도 정보 (지정가 매도가 미체결된 경우)
            if end_sell_price > 0 and end_sell_quantity > 0:
                end_buy_amount = (end_sell_quantity / buy_quantity) * (buy_quantity * buy_price) if buy_quantity > 0 else 0
                end_sell_amount = end_sell_price * end_sell_quantity
                end_profit_pct = ((end_sell_price / buy_price) - 1) * 100 if buy_price > 0 else 0
                end_profit_amount = end_sell_amount - end_buy_amount
                
                message += f"""
   ⏰ <b>종료시간 매도</b>
   • 매도가: {end_sell_price:,.0f}원
   • 매도수량: {end_sell_quantity:.6f}
   • 종료시간 수익률: {end_profit_pct:+.2f}%
   • 종료시간 수익금액: {end_profit_amount:+,.0f}원
"""
    
    message += f"""
━━━━━━━━━━━━━━━━━━━━
<b>합계</b>
총 매수금액: {total_buy_amount:,.0f}원
총 매도금액: {total_sell_amount:,.0f}원
총 수익률: {total_profit_pct:+.2f}%
총 수익금액: {total_profit_amount:+,.0f}원
"""
    
    send_telegram_message(message, chat_id=channel_id)
