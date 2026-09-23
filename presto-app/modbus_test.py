# ICON monitoring
# NAME Modbus Test
# DESC Modbus TCP & Write Permission Diagnostic

import gc
import machine
import network
import secrets
import time
from picovector import ANTIALIAS_BEST, PicoVector, Polygon, Transform
from presto import Presto
import urequests

PI_API_URL = f"{secrets.PI_BASE_URL}/api/modbus/test"
TEST_INTERVAL = 5

presto = Presto(ambient_light=False, full_res=True)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()

BLACK = display.create_pen(0, 0, 0)
WHITE = display.create_pen(255, 255, 255)
GREEN = display.create_pen(0, 220, 100)
RED = display.create_pen(220, 50, 50)
YELLOW = display.create_pen(240, 200, 0)
GRAY = display.create_pen(120, 120, 120)
DARK_GRAY = display.create_pen(40, 40, 40)

vector = PicoVector(display)
vector.set_antialiasing(ANTIALIAS_BEST)
t = Transform()
vector.set_font("Roboto-Medium.af", 96)
vector.set_transform(t)

current_data = None
previous_data = None
last_test_time = "Never"
previous_test_time = "N/A"
is_testing = False

is_holding = False
touch_press_start = 0

def ensure_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    return wlan.isconnected()

def check_touch_exit():
    global is_holding, touch_press_start
    presto.touch_poll()
    touched = presto.touch.state
    current_time_ms = time.ticks_ms()

    if touched and not is_holding:
        is_holding = True
        touch_press_start = current_time_ms
    elif not touched and is_holding:
        is_holding = False

    if is_holding and time.ticks_diff(current_time_ms, touch_press_start) > 1000:
        display.set_pen(BLACK)
        display.clear()
        display.set_pen(WHITE)
        vector.set_font_size(26)
        vector.text("Returning to Menu...", 40, HEIGHT // 2)
        presto.update()
        time.sleep(0.4)
        machine.reset()

def format_server_time(data_dict):
    if isinstance(data_dict, dict):
        return data_dict.get("time_str", "N/A")
    return "N/A"

def draw_screen():
    display.set_pen(BLACK)
    display.clear()

    display.set_pen(WHITE)
    vector.set_font_size(26)
    vector.text("MODBUS TCP TEST", 30, 45)

    if is_testing:
        display.set_pen(YELLOW)
        vector.set_font_size(18)
        vector.text("[ TESTING... ]", 320, 45)
    else:
        display.set_pen(GRAY)
        vector.set_font_size(16)
        vector.text(f"Last: {last_test_time}", 310, 45)

    if current_data:
        port_open = current_data.get("port_open", False)
        read_ok = current_data.get("read_ok", False)
        write_ok = current_data.get("write_ok", False)
        msg = current_data.get("message", "Testing...")
    else:
        port_open = False
        read_ok = False
        write_ok = False
        msg = "Pi API Unreachable"

    display.set_pen(GREEN if port_open else RED)
    vector.set_font_size(22)
    vector.text(f"Port 502:    {'OPEN' if port_open else 'CLOSED'}", 30, 95)

    display.set_pen(GREEN if read_ok else RED)
    vector.text(f"Read Mode:   {'OK' if read_ok else 'FAIL'}", 30, 135)

    display.set_pen(GREEN if write_ok else RED)
    vector.text(f"Write Mode:  {'ENABLED' if write_ok else 'DISABLED'}", 30, 175)

    banner_pen = GREEN if write_ok else (YELLOW if port_open else RED)
    banner_card = Polygon()
    banner_card.rectangle(20, 215, 440, 95, corners=(10, 10, 10, 10))

    display.set_pen(banner_pen)
    vector.draw(banner_card)

    display.set_pen(BLACK)
    if write_ok:
        vector.set_font_size(22)
        vector.text("READY FOR EV CONTROL", 40, 250)
        vector.set_font_size(16)
        vector.text("Modbus TCP Write Verified", 40, 285)
    else:
        vector.set_font_size(22)
        vector.text("ACTION REQUIRED", 40, 250)
        vector.set_font_size(16)
        vector.text(msg[:32], 40, 285)

    prev_card = Polygon()
    prev_card.rectangle(20, 325, 440, 90, corners=(10, 10, 10, 10))

    display.set_pen(DARK_GRAY)
    vector.draw(prev_card)

    display.set_pen(GRAY)
    vector.set_font_size(16)
    vector.text(f"PREVIOUS TEST ({previous_test_time}):", 35, 350)

    if previous_data:
        p_write = previous_data.get("write_ok", False)
        p_msg = previous_data.get("message", "Unknown")
        p_status = "Ready / Write ENABLED" if p_write else p_msg
        p_pen = GREEN if p_write else YELLOW
    else:
        p_status = "No prior test recorded"
        p_pen = GRAY

    display.set_pen(p_pen)
    vector.set_font_size(18)
    vector.text(p_status[:36], 35, 385)

    display.set_pen(GRAY)
    vector.set_font_size(14)
    vector.text("Hold screen for 1s to return to main menu", 80, 455)

    presto.update()

def run_test():
    global current_data, previous_data, last_test_time, previous_test_time, is_testing

    is_testing = True
    draw_screen()

    if current_data is not None:
        previous_data = current_data
        previous_test_time = last_test_time

    ensure_wifi()

    res = None
    try:
        res = urequests.get(PI_API_URL)
        if res.status_code == 200:
            current_data = res.json()
            last_test_time = format_server_time(current_data)
        else:
            current_data = {
                "port_open": False,
                "read_ok": False,
                "write_ok": False,
                "message": f"HTTP {res.status_code}"
            }
            last_test_time = "Error"
    except Exception as e:
        current_data = {
            "port_open": False,
            "read_ok": False,
            "write_ok": False,
            "message": str(e)[:32]
        }
        last_test_time = "Error"
    finally:
        if res:
            try:
                res.close()
            except:
                pass
        gc.collect()

    is_testing = False
    draw_screen()

ensure_wifi()
run_test()
last_fetch = time.time()

while True:
    check_touch_exit()

    if time.time() - last_fetch >= TEST_INTERVAL:
        run_test()
        last_fetch = time.time()

    time.sleep(0.05)
