"""
업비트 펌핑코인 알리미V2 - 유틸리티 함수
기존 auto_trading_system_gui.py의 함수들을 재사용
"""
import sys
import os
import types

# 현재 디렉토리 경로 추가 (같은 폴더에 있는 파일 사용)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# tkinter를 mock 처리 (Streamlit 환경에서는 필요 없음)
class MockTkinter:
    """tkinter 모듈을 mock 처리"""
    class Tk:
        pass
    class Toplevel:
        pass
    class Label:
        pass
    class Button:
        pass
    class Frame:
        pass
    class StringVar:
        pass
    class BooleanVar:
        pass
    class IntVar:
        pass
    class DoubleVar:
        pass
    class END:
        pass
    class NORMAL:
        pass
    class DISABLED:
        pass
    class W:
        pass
    class E:
        pass
    class N:
        pass
    class S:
        pass
    class LEFT:
        pass
    class RIGHT:
        pass
    class BOTH:
        pass
    class X:
        pass
    class Y:
        pass
    class WORD:
        pass
    class CENTER:
        pass
    class HORIZONTAL:
        pass
    class VERTICAL:
        pass
    class messagebox:
        @staticmethod
        def showinfo(*args, **kwargs):
            pass
        @staticmethod
        def showwarning(*args, **kwargs):
            pass
        @staticmethod
        def showerror(*args, **kwargs):
            pass
    class ttk:
        class Frame:
            pass
        class Label:
            pass
        class Button:
            pass
        class Entry:
            pass
        class Combobox:
            pass
        class Checkbutton:
            pass
        class LabelFrame:
            pass
        class Separator:
            pass
        class Style:
            pass
        class Scrollbar:
            pass
    class scrolledtext:
        class ScrolledText:
            pass

# tkinter를 mock으로 교체
sys.modules['tkinter'] = types.ModuleType('tkinter')
sys.modules['tkinter'].tk = MockTkinter()
sys.modules['tkinter'].ttk = MockTkinter.ttk
sys.modules['tkinter'].messagebox = MockTkinter.messagebox
sys.modules['tkinter'].scrolledtext = MockTkinter.scrolledtext
sys.modules['tkinter'].constants = types.ModuleType('constants')
for attr in ['Tk', 'Toplevel', 'Label', 'Button', 'Frame', 'StringVar', 'BooleanVar', 
             'IntVar', 'DoubleVar', 'END', 'NORMAL', 'DISABLED', 'W', 'E', 'N', 'S',
             'LEFT', 'RIGHT', 'BOTH', 'X', 'Y', 'WORD', 'CENTER', 'HORIZONTAL', 'VERTICAL']:
    setattr(sys.modules['tkinter'], attr, getattr(MockTkinter, attr, None))

# Lazy import를 위한 캐시
_auto_trading_module = None

def _get_auto_trading_module():
    """auto_trading_system_gui 모듈을 lazy import"""
    global _auto_trading_module
    if _auto_trading_module is None:
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "auto_trading_system_gui",
                os.path.join(current_dir, "auto_trading_system_gui.py")
            )
            _auto_trading_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_auto_trading_module)
        except Exception as e:
            import traceback
            print(f"Import 오류: {e}")
            print(f"현재 디렉토리: {current_dir}")
            print("현재 디렉토리의 auto_trading_system_gui.py 파일이 필요합니다.")
            traceback.print_exc()
            raise
    return _auto_trading_module

# 함수들을 lazy import wrapper로 래핑
def get_all_upbit_coins(*args, **kwargs):
    return _get_auto_trading_module().get_all_upbit_coins(*args, **kwargs)

def print_coins_under_price_and_volume(*args, **kwargs):
    return _get_auto_trading_module().print_coins_under_price_and_volume(*args, **kwargs)

def print_3minute_candles(*args, **kwargs):
    return _get_auto_trading_module().print_3minute_candles(*args, **kwargs)

def print_filtered_coins_by_price_volume(*args, **kwargs):
    return _get_auto_trading_module().print_filtered_coins_by_price_volume(*args, **kwargs)

def print_all_coins_market_buy_analysis(*args, **kwargs):
    return _get_auto_trading_module().print_all_coins_market_buy_analysis(*args, **kwargs)

def print_filtered_by_slippage(*args, **kwargs):
    return _get_auto_trading_module().print_filtered_by_slippage(*args, **kwargs)

def filter_by_day_candle(*args, **kwargs):
    return _get_auto_trading_module().filter_by_day_candle(*args, **kwargs)

def load_api_keys_from_json(*args, **kwargs):
    return _get_auto_trading_module().load_api_keys_from_json(*args, **kwargs)

def buy_coins_from_list(*args, **kwargs):
    return _get_auto_trading_module().buy_coins_from_list(*args, **kwargs)

def cancel_all_orders_and_sell_all(upbit, coin, logger=None, return_sell_price=False):
    """특정 코인의 모든 미체결 주문 취소 후 전량 매도 (utils 버전)"""
    module = _get_auto_trading_module()
    # TradingGUI 클래스의 메서드를 사용하기 위해 인스턴스 생성이 필요하지만,
    # 여기서는 직접 함수로 구현
    try:
        coin_symbol = coin.replace("KRW-", "")
        
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
        
        import time
        time.sleep(1)
        
        # 전량 매도
        coin_balance = upbit.get_balance(coin)
        if coin_balance and float(coin_balance) > 0:
            try:
                import pyupbit
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
                                                price = float(trade.get('price', 0))
                                                volume = float(trade.get('volume', 0))
                                                total_revenue += price * volume
                                                total_volume += volume
                                            
                                            if total_volume > 0:
                                                sell_price = total_revenue / total_volume
                                                sell_amount = total_revenue
                                                sell_quantity = total_volume
                                            else:
                                                # funds 필드 사용
                                                funds = float(order.get('funds', 0))
                                                if funds > 0:
                                                    sell_price = funds / executed_volume
                                                    sell_amount = funds
                                                    sell_quantity = executed_volume
                                    else:
                                        # funds 필드 사용
                                        funds = float(order.get('funds', 0))
                                        if funds > 0 and executed_volume > 0:
                                            sell_price = funds / executed_volume
                                            sell_amount = funds
                                            sell_quantity = executed_volume
                            except Exception as e:
                                if logger:
                                    logger.log(f"  {coin_symbol}: 매도 체결 내역 조회 실패: {e}", "WARNING")
                    
                    if return_sell_price:
                        return (True, sell_price, sell_amount)
                    return True
                else:
                    if logger:
                        logger.log(f"  {coin_symbol}: 전량 매도 주문 실패", "ERROR")
                    return (False, None, None) if return_sell_price else False
            except Exception as e:
                if logger:
                    logger.log(f"  {coin_symbol}: 전량 매도 중 오류: {e}", "ERROR")
                return (False, None, None) if return_sell_price else False
        else:
            if logger:
                logger.log(f"  {coin_symbol}: 매도할 수량이 없습니다.", "INFO")
            return (False, None, None) if return_sell_price else False
    except Exception as e:
        if logger:
            logger.log(f"  {coin_symbol}: cancel_all_orders_and_sell_all 오류: {e}", "ERROR")
        return (False, None, None) if return_sell_price else False
