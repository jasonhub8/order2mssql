
import tkinter as tk
from tkinter import ttk
from threading import Thread, Lock
from DrissionPage import ChromiumPage, ChromiumOptions
import time
import pymssql
import os
import sys
import pystray
from PIL import Image, ImageDraw, ImageFont
import configparser


class OrderMonitor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OTA订单监听")
        self.root.geometry("200x100")
        self.root.overrideredirect(True)
        self.meituan_last_time = 0
        self.xiecheng_last_time = 0
        self.chrome = None
        self.current_listening_tab_id = None
        self.running = False
        self.tab_switch_monitor = None
        self.lock = Lock()
        self.last_check_time = time.time()
        self.sleep_monitor_thread = None
        
        # 数据库连接配置
        config = configparser.ConfigParser()
        if getattr(sys, 'frozen', False):
            # 打包成exe运行
            current_path = os.path.dirname(sys.executable)
        else:
            # 开发环境运行
            current_path = os.path.dirname(os.path.abspath(__file__))
        ini_path = os.path.join(current_path, 'Setting.ini')
        config.read(ini_path, encoding='GBK')
        
        self.db_config = {
            'server': config.get('FrmMain', 'RoomStrDbServer'),
            'user': config.get('FrmMain', 'RoomStrDbUser'),
            'password': config.get('FrmMain', 'RoomStrDbPsw'),
            'database': config.get('FrmMain', 'RoomStrDbName'),
            'charset': 'utf8'
        }
        
        # 初始化托盘图标
        self.tray_icon = None
        self.setup_tray()
        
        self.create_ui()
        self._drag_x = 0
        self._drag_y = 0
        self.root.bind("<Button-1>", self._on_start_drag)
        self.root.bind("<B1-Motion>", self._on_drag)

        Thread(target=self.init_browser, daemon=True).start()
        Thread(target=self.monitor_system_sleep, daemon=True).start()
        Thread(target=self.run_tray, daemon=True).start()
    
    def setup_tray(self):
        # 创建一个更专业的托盘图标
        image = Image.new('RGB', (64, 64), color='#2C3E50')
        dc = ImageDraw.Draw(image)
        
        # 绘制背景渐变效果
        dc.ellipse([4, 4, 60, 60], fill='#3498DB')
        dc.ellipse([12, 12, 52, 52], fill='#2980B9')
        
        # 绘制订单图标 - 一个文档形状
        dc.rectangle([20, 16, 44, 48], fill='white')
        dc.rectangle([20, 16, 44, 24], fill='#E74C3C')
        
        # 绘制一些细节
        dc.rectangle([26, 30, 38, 32], fill='#34495E')
        dc.rectangle([26, 36, 38, 38], fill='#34495E')
        dc.rectangle([26, 42, 38, 44], fill='#34495E')
        
        menu = (
            pystray.MenuItem('显示窗口', self.show_window),
            pystray.MenuItem('退出', self.on_exit),
        )
        
        self.tray_icon = pystray.Icon("ota_order_monitor", image, "OTA订单监听服务", menu)
    
    def show_window(self, icon, item):
        self.root.deiconify()
        self.root.lift()
    
    def create_ui(self):
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        ttk.Label(main_frame, text="OTA订单监听运行中...").pack(pady=10)

    def _on_start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        deltax = event.x - self._drag_x
        deltay = event.y - self._drag_y
        x = self.root.winfo_x() + deltax
        y = self.root.winfo_y() + deltay
        self.root.geometry(f"+{x}+{y}")
    def monitor_system_sleep(self):
        while True:
            try:
                current_time = time.time()
                time_diff = current_time - self.last_check_time
                
                if time_diff > 8:
                    print(f"检测到系统时间跳变 {time_diff:.1f} 秒，可能是从休眠中恢复，准备重启...")
                    self.root.after(0, self.restart_app)
                    break
                
                self.last_check_time = current_time
                time.sleep(5)
            except Exception as e:
                print(f"休眠监控错误: {e}")
                time.sleep(5)
    
    def restart_app(self):
        self.running = False
        self.root.destroy()
        python = sys.executable
        os.spawnv(os.P_DETACH, python, [python] + sys.argv)
        sys.exit()
    
    def on_exit(self, icon=None, item=None):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()
    
    def run_tray(self):
        print("OTA订单监听服务已启动，托盘图标显示在右下角")
        self.tray_icon.run()
    
    def parse_meituan_order(self, data):
        elements = {}
        elements['订单号'] = data.get('orderId', '')
        elements['订单状态'] = data.get('status', '')
        elements['房型名称'] = data.get('roomName', '')
        elements['入住日期'] = data.get('checkInDateString', '')
        elements['离店日期'] = data.get('checkOutDateString', '')

        part_refund = data.get('partRefundInfo', {})
        elements['天数'] = f"{part_refund.get('totalRoomNightCount', '')}天"
        elements['间数'] = f"{data.get('roomCount', '')}间"

        price_info = data.get('priceInfo', [])
        floor_prices = []
        for price in price_info:
            floor_price = price.get('floorPrice', '')
            if floor_price:
                try:
                    floor_price_yuan = float(floor_price) / 100
                    floor_prices.append(f"{floor_price_yuan:.2f}")
                except:
                    floor_prices.append(str(floor_price))
        elements['底价构成s'] = ', '.join(floor_prices)
        elements['底价构成'] = floor_prices[0] if floor_prices else None
        breakfast_info = data.get('breakfastInfo', [])
        breakfasts = []
        for bf in breakfast_info:
            breakfasts.append(bf.get('breakfastDesc', ''))
        elements['早餐s'] = ', '.join(breakfasts)
        if '不含早' in elements['早餐s']:
            elements['早餐'] = '不含早'
        elif '含1早' in elements['早餐s']:
            elements['早餐'] = '单早'
        elif '含2早' in elements['早餐s']:
            elements['早餐'] = '双早'
        else:
            elements['早餐'] = ''

        invoice_model = data.get('invoiceTagModel', {})
        invoice_money = invoice_model.get('invoiceMoney', '')
        if invoice_money:
            try:
                invoice_money_yuan = float(invoice_money) / 100
                elements['发票要求'] = f"{invoice_money_yuan:.2f}"
            except:
                elements['发票要求'] = invoice_money
        else:
            elements['发票要求'] = ''

        guests = data.get('guests', [])
        guest_names = []
        for guest in guests:
            guest_names.append(guest.get('name', ''))
        elements['入住人'] = ', '.join(guest_names)
        elements['特殊要求'] = ''
        elements['平台'] = '美团'
        return elements
    
    def parse_xiecheng_order(self, data):
        elements = {}
        elements['订单号'] = data.get('orderID', '')
        elements['订单状态'] = data.get('orderStatusDesc', '')
        elements['房型名称'] = data.get('roomName', '')
        elements['入住日期'] = data.get('arrival', '')
        elements['离店日期'] = data.get('departure', '')
        elements['天数'] = f"{data.get('nights', '')}天"
        elements['间数'] = f"{data.get('quantity', '')}间"
        room_prices = data.get('orderRoomPrices', [])
        prices = []
        breakfasts = []
        for rp in room_prices:
            price = rp.get('price', '')
            if price:
                try:
                    price_yuan = float(price)
                    prices.append(f"{price_yuan:.2f}")
                except:
                    prices.append(str(price))
            breakfasts.append(str(rp.get('breakfast', '')))
        elements['底价构成s'] = ', '.join(prices)
        elements['底价构成'] = prices[0] if prices else None
        elements['早餐s'] = ', '.join(breakfasts)
        if '0' in elements['早餐s']:
            elements['早餐'] = '不含早'
        elif '1' in elements['早餐s']:
            elements['早餐'] = '单早'
        elif '2' in elements['早餐s']:
            elements['早餐'] = '双早'
        else:
            elements['早餐'] = ''
        invoice = data.get('invoice', {})
        elements['发票要求'] = invoice.get('info', '')
        elements['入住人'] = data.get('clientName', '')
        elements['特殊要求'] = data.get('remarks', '') if 'remarks' in data and data.get('remarks', '') else ''
        elements['平台'] = '携程（预付）'
        return elements
    
    def insert_order_to_db(self, elements):
        order_id = elements.get('订单号', '')
        
        try:
            conn = pymssql.connect(**self.db_config)
            cursor = conn.cursor()
            
            # 检查数据库中是否已存在
            cursor.execute("SELECT 订单状态 FROM 读取OTA平台订单 WHERE 订单号 = %s", (order_id,))
            result = cursor.fetchone()
            
            if result:
                db_status = result[0]
                new_status = elements.get('订单状态', '')

                if db_status == new_status:
                    print(f'订单 {order_id} 已存在于数据库中且状态相同，跳过')
                    cursor.close()
                    conn.close()
                    return
                else:
                    # 更新订单状态
                    update_sql = """
                        UPDATE 读取OTA平台订单 
                        SET 订单状态 = %s 
                        WHERE 订单号 = %s
                    """
                    cursor.execute(update_sql, (new_status, order_id))
                    conn.commit()
                    print(f'订单 {order_id} 状态已从 {db_status} 更新为 {new_status}')
                    cursor.close()
                    conn.close()
                    return
            
            # 插入新订单
            insert_sql = """
                INSERT INTO 读取OTA平台订单 
                (订单号, 平台, 订单状态, 房型名称, 入住日期, 离店日期, 天数, 间数, 底价构成s, 底价构成, 早餐s, 早餐, 发票要求, 入住人, 特殊要求)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            data = (
                elements.get('订单号', ''),
                elements.get('平台', ''),
                elements.get('订单状态', ''),
                elements.get('房型名称', ''),
                elements.get('入住日期', ''),
                elements.get('离店日期', ''),
                elements.get('天数', ''),
                elements.get('间数', ''),
                elements.get('底价构成s', ''),
                elements.get('底价构成'),
                elements.get('早餐s', ''),
                elements.get('早餐', ''),
                elements.get('发票要求', ''),
                elements.get('入住人', ''),
                elements.get('特殊要求', '')
            )
            
            cursor.execute(insert_sql, data)
            conn.commit()
            
            print(f'订单 {order_id} 已成功插入数据库')
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f'数据库操作失败: {e}')
    
    def init_browser(self):
        try:
            self.chrome = ChromiumPage(addr='127.0.0.1:9333')
        except:
            options = ChromiumOptions().set_local_port(9333).set_user_data_path(r'D:\Default')
            self.chrome = ChromiumPage(addr_or_opts=options)
            meituan_tab = self.chrome.new_tab()
            meituan_tab.get(
                'https://me.meituan.com/ebooking/merchant/ebIframe?iUrl=%2Febooking%2Forder-eb%2Findex.html%23%2FallCheckin')
            time.sleep(2)
            xiecheng_tab = self.chrome.new_tab()
            xiecheng_tab.get('https://ebooking.ctrip.com/ebkorderv3/domestic?tab=0#tab=0')
            time.sleep(2)

        self.running = True
        self.tab_switch_monitor = Thread(target=self.monitor_tab_switch, daemon=True)
        self.tab_switch_monitor.start()
    
    def monitor_tab_switch(self):
        while self.running:
            try:
                latest_tab = self.chrome.latest_tab
                if latest_tab:
                    current_tab_id = latest_tab.tab_id
                    if current_tab_id != self.current_listening_tab_id:
                        with self.lock:
                            self.current_listening_tab_id = current_tab_id
                        print(f"切换到标签页: {current_tab_id}")
                        Thread(target=self.start_listen, args=(latest_tab,), daemon=True).start()
            except Exception as e:
                print(f"监控标签页切换错误: {e}")
            time.sleep(1)
    
    def start_listen(self, tab):
        try:
            url = tab.url
            if 'meituan.com' in url:
                self.listen_meituan(tab)
            elif 'ebooking.com' in url or 'ctrip.com' in url:
                self.listen_xiecheng(tab)
        except Exception as e:
            print(f"启动监听错误: {e}")
    
    def listen_meituan(self, tab):
        print("开始美团监听")
        listening_active = False

        try:
            tab.listen.start('https://eb.meituan.com/api/v1/ebooking/orders/', method='GET')
            listening_active = True
        except Exception as e:
            print(f"美团监听启动错误: {e}")
            return

        while self.running:
            with self.lock:
                if self.current_listening_tab_id != tab.tab_id:
                    print("停止美团监听 - 标签页已切换")
                    break

            try:
                if not listening_active:
                    try:
                        tab.listen.start('https://eb.meituan.com/api/v1/ebooking/orders/', method='GET')
                        listening_active = True
                    except:
                        time.sleep(0.5)
                        continue

                req = tab.listen.wait(timeout=2, raise_err=False)
                if req and req.response:
                    response_data = req.response.body
                    if response_data:
                        data = response_data
                        if isinstance(data, dict) and data.get('status') == 0 and 'data' in data:
                            order_data = data['data']
                            with self.lock:
                                self.meituan_last_time = time.time()
                            order_id = order_data.get('orderId', '')
                            print(f"监听到美团订单: {order_id} - 状态: {order_data.get('status', '')}")
                            
                            # 解析并插入数据库
                            elements = self.parse_meituan_order(order_data)
                            self.insert_order_to_db(elements)

            except Exception as e:
                print(f"美团监听循环错误: {e}")
                listening_active = False
            time.sleep(0.1)

        try:
            tab.listen.stop()
        except:
            pass
        print("美团监听已停止")
    
    def listen_xiecheng(self, tab):
        print("开始携程监听")
        listening_active = False

        try:
            tab.listen.start('getOrderDetail', method='POST')
            listening_active = True
        except Exception as e:
            print(f"携程监听启动错误: {e}")
            return

        while self.running:
            with self.lock:
                if self.current_listening_tab_id != tab.tab_id:
                    print("停止携程监听 - 标签页已切换")
                    break

            try:
                if not listening_active:
                    try:
                        tab.listen.start('getOrderDetail', method='POST')
                        listening_active = True
                    except:
                        time.sleep(0.5)
                        continue

                req = tab.listen.wait(timeout=2, raise_err=False)
                if req and req.response:
                    response_data = req.response.body
                    if response_data:
                        data = response_data
                        if isinstance(data, dict) and 'detail' in data:
                            order_data = data['detail']
                            with self.lock:
                                self.xiecheng_last_time = time.time()
                            order_id = order_data.get('orderID', '')
                            print(f"监听到携程订单: {order_id} - 状态: {order_data.get('orderStatusDesc', '')}")
                            
                            # 解析并插入数据库
                            elements = self.parse_xiecheng_order(order_data)
                            self.insert_order_to_db(elements)
            except Exception as e:
                print(f"携程监听循环错误: {e}")
                listening_active = False
            time.sleep(0.1)

        try:
            tab.listen.stop()
        except:
            pass
        print("携程监听已停止")
    
    def run(self):
        self.root.mainloop()
        self.running = False


if __name__ == "__main__":
    app = OrderMonitor()
    app.run()
