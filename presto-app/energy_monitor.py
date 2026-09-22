# ICON monitoring
# NAME Solar & Energy
# DESC Live Solar, House Load, EVAC, Grid & Battery Monitor (480x480)

import time
import network
import urequests
import secrets
import gc
import machine
from presto import Presto
from picovector import ANTIALIAS_BEST, PicoVector, Polygon, Transform

# Construct API endpoint dynamically from secrets.py
PI_API_URL = f"{secrets.PI_BASE_URL}/api/dashboard"

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Initialize Presto in native 480x480 resolution mode
presto = Presto(ambient_light=True, full_res=True)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()  # (480, 480)

# Colors
BLACK = display.create_pen(0, 0, 0)
WHITE = display.create_pen(255, 255, 255)
GRAY = display.create_pen(180, 180, 180)

# Setup PicoVector
vector = PicoVector(display)
vector.set_antialiasing(ANTIALIAS_BEST)
t = Transform()
t.scale(1.0, 1.0)
vector.set_font("Roboto-Medium.af", 96)
vector.set_transform(t)

# --- LOADING SCREEN ---
display.set_pen(BLACK)
display.clear()
display.set_pen(WHITE)
vector.set_font_size(28)
_, _, tw, _ = vector.measure_text("Starting Energy Monitor...")
vector.text("Starting Energy Monitor...", int((WIDTH / 2) - (tw / 2)), HEIGHT // 2)
presto.update()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        timeout = 10
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    return wlan.isconnected()

# Touch Exit Handler (Long press screen to reboot to main.py)
is_holding = False
touch_press_start = 0

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

    if is_holding and time.ticks_diff(current_time_ms, touch_press_start) > 1500:
        display.set_layer(1)
        display.set_pen(BLACK)
        display.clear()
        display.set_pen(WHITE)
        vector.set_font_size(24)
        vector.text("Exiting...", 20, 20)
        presto.update()
        time.sleep(0.4)
        machine.reset()

class Widget(object):
    def __init__(self, x, y, w, h, radius=12, text_size=28):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.r = radius
        self.text = None
        self.lines = None
        self.size = text_size
        self.title = None

        self.bg = Polygon()
        self.bg.rectangle(
            self.x, self.y, self.w, self.h, corners=(self.r, self.r, self.r, self.r)
        )

    def draw(self, card_pen, text_pen):
        display.set_pen(card_pen)
        vector.draw(self.bg)

        # Title
        if self.title:
            display.set_pen(text_pen)
            vector.set_font_size(20)
            _, _, tw, _ = vector.measure_text(self.title)
            tx = int((self.x + self.w // 2) - (tw // 2))
            ty = self.y + 26
            vector.text(self.title, tx, ty)

        # Multi-line rendering for Grid card (Import & Export)
        if self.lines:
            display.set_pen(text_pen)
            vector.set_font_size(17)
            start_y = self.y + 60
            line_height = 26
            for i, line in enumerate(self.lines):
                _, _, tw, _ = vector.measure_text(line)
                tx = int((self.x + self.w // 2) - (tw // 2))
                ty = start_y + (i * line_height)
                vector.text(line, tx, ty)

        # Single Value text (Solar, Load, EVAC)
        elif self.text is not None:
            display.set_pen(text_pen)
            vector.set_font_size(self.size)
            _, _, tw, th = vector.measure_text(self.text)
            tx = int((self.x + self.w // 2) - (tw // 2))
            ty = int((self.y + self.h // 2) + (th // 2)) + 10
            vector.text(self.text, tx, ty)

    def set_label(self, value):
        if isinstance(value, (list, tuple)):
            self.lines = value
            self.text = None
        else:
            self.text = value
            self.lines = None

    def set_title(self, title):
        self.title = title

# Pre-allocate Battery Progress Bar Card
bat_card = Polygon()
bat_card.rectangle(20, 325, 440, 135, corners=(12, 12, 12, 12))

def draw_battery_progress_bar(soc, card_pen, text_pen):
    display.set_pen(card_pen)
    vector.draw(bat_card)

    display.set_pen(text_pen)
    vector.set_font_size(22)
    soc_text = f"BATTERY SOC: {soc:.1f}%" if soc is not None else "BATTERY SOC: --%"
    vector.text(soc_text, 40, 358)

    # Windows 3.1 Progress Bar Frame
    bar_x, bar_y, bar_w, bar_h = 40, 375, 400, 48
    display.set_pen(BLACK)
    display.rectangle(bar_x, bar_y, bar_w, bar_h)
    display.set_pen(GRAY)
    display.rectangle(bar_x + 2, bar_y + 2, bar_w - 4, bar_h - 4)

    # 10 Gradient Blocks (Red -> Yellow -> Green)
    total_blocks = 10
    block_spacing = 4
    usable_w = bar_w - 8 - (block_spacing * (total_blocks - 1))
    block_w = usable_w // total_blocks
    block_h = bar_h - 10

    fill_ratio = max(0.0, min(1.0, soc / 100.0)) if soc is not None else 0.0
    filled_blocks = int(fill_ratio * total_blocks)
    partial_block_ratio = (fill_ratio * total_blocks) - filled_blocks

    def block_color(i):
        hue = 0.0 + (0.33 * (i / 9))
        return display.create_pen_hsv(hue, 0.9, 0.95)

    for i in range(total_blocks):
        bx = bar_x + 4 + i * (block_w + block_spacing)
        by = bar_y + 5

        if i < filled_blocks:
            display.set_pen(block_color(i))
            display.rectangle(bx, by, block_w, block_h)
        elif i == filled_blocks and partial_block_ratio > 0:
            pw = int(block_w * partial_block_ratio)
            if pw > 0:
                display.set_pen(block_color(i))
                display.rectangle(bx, by, pw, block_h)

# --- 2x2 Grid Layout ---
widgets = [
    Widget(20, 50, 210, 125, 12, 28),   # Solar
    Widget(250, 50, 210, 125, 12, 28),  # Load
    Widget(20, 185, 210, 125, 12, 28),  # EVAC
    Widget(250, 185, 210, 125, 12, 28)  # Grid
]

widgets[0].set_title("Solar")
widgets[1].set_title("Load")
widgets[2].set_title("EVAC")
widgets[3].set_title("Grid")

connect_wifi()

last_fetch = 0
data = None
current_hue = None

while True:
    check_touch_exit()

    # Poll API every 5 seconds
    if time.time() - last_fetch > 5 or data is None:
        # Check Wi-Fi status cleanly without disconnecting
        connect_wifi()

        res = None
        try:
            res = urequests.get(PI_API_URL)
            if res.status_code == 200:
                data = res.json()
            else:
                data = None
        except Exception as e:
            print("Fetch error:", e)
            data = None
        finally:
            if res:
                try:
                    res.close()
                except:
                    pass
            gc.collect()
            last_fetch = time.time()

    if data and "error" not in data and not data.get("is_stale", False):
        pv_power = data.get('pv_power_kw', 0.0)
        grid_power = data.get('grid_power_kw', 0.0)
        load_power = data.get('load_power_kw', 0.0)
        ev_power = data.get('ev_power_kw', 0.0)
        battery_soc = data.get('battery_soc', 0.0)

        grid_imp = max(0.0, grid_power)
        grid_exp = max(0.0, -grid_power)

        if grid_power > 0.05:
            target_hue = 0.0   # Red
        elif pv_power > (load_power + ev_power):
            target_hue = 0.15  # Yellow
        else:
            target_hue = 0.33  # Green

        widgets[0].set_label(f"{pv_power:.2f} kW")
        widgets[1].set_label(f"{load_power:.2f} kW")
        widgets[2].set_label(f"{ev_power:.2f} kW")
        widgets[3].set_label([
            f"Imp: {grid_imp:.2f} kW",
            f"Exp: {grid_exp:.2f} kW"
        ])
    else:
        target_hue = 0.33
        battery_soc = None
        widgets[0].set_label("- -")
        widgets[1].set_label("- -")
        widgets[2].set_label("- -")
        widgets[3].set_label(["Imp: - -", "Exp: - -"])

    if current_hue != target_hue:
        current_hue = target_hue
        for i in range(7):
            presto.set_led_hsv(i, current_hue, 1.0, 0.5)

    pen_bg = display.create_pen_hsv(current_hue, 0.65, 0.85)
    pen_box = display.create_pen_hsv(current_hue, 0.40, 1.00)
    pen_text = display.create_pen_hsv(current_hue, 0.9, 0.15)

    display.set_pen(pen_bg)
    display.clear()

    # --- Header: Time (Left) & Date (Right) ---
    try:
        if data and "timestamp" in data and data["timestamp"]:
            ts = int(data["timestamp"])
            if ts > 3000000000:
                ts = ts // 1000
            t_tuple = time.localtime(ts)
        else:
            t_tuple = time.localtime()
    except Exception:
        t_tuple = time.localtime()

    year, month, mday, hour, minute, _, weekday, _ = t_tuple
    time_str = f"{hour:02d}:{minute:02d}"
    date_str = f"{DAYS[weekday]} {mday} {MONTHS[month - 1]} {year}"

    display.set_pen(pen_text)
    vector.set_font_size(26)

    # Time (Left Aligned)
    vector.text(time_str, 20, 34)

    # Date (Right Aligned)
    _, _, tw, _ = vector.measure_text(date_str)
    vector.text(date_str, int(WIDTH - 20 - tw), 34)

    # Draw Grid Cards
    for w in widgets:
        w.draw(pen_box, pen_text)

    # Draw Battery Progress Bar
    draw_battery_progress_bar(battery_soc, pen_box, pen_text)

    presto.update()
    time.sleep(0.1)
