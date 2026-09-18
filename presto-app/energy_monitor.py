# ICON monitoring
# NAME Solar & Energy
# DESC Live Solar, House Load, EVAC, Grid & Battery Monitor

import time
import network
import urequests
import secrets
import gc
from presto import Presto
from picovector import ANTIALIAS_BEST, PicoVector, Polygon, Transform

# --- Configuration ---
PI_API_URL = "http://172.18.2.2:5000/api/dashboard"

# Setup Presto display & hardware
presto = Presto(ambient_light=True)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()

# Colors
BLACK = display.create_pen(0, 0, 0)
WHITE = display.create_pen(255, 255, 255)

# Setup PicoVector for smooth fonts & rounded shapes
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
vector.set_font_size(22)
_, _, tw, _ = vector.measure_text("Starting Energy Monitor...")
vector.text("Starting Energy Monitor...", int((WIDTH / 2) - (tw / 2)), HEIGHT // 2)
presto.update()

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(secrets.WIFI_SSID, secrets.WIFI_PASSWORD)
        timeout = 15
        while not wlan.isconnected() and timeout > 0:
            time.sleep(1)
            timeout -= 1
    return wlan.isconnected()

connect_wifi()

class Widget(object):
    def __init__(self, x, y, w, h, radius=10, text_size=26):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.r = radius
        self.text = None
        self.size = text_size
        self.title = None

        # Rounded-corner background polygon
        self.bg = Polygon()
        self.bg.rectangle(
            self.x,
            self.y,
            self.w,
            self.h,
            corners=(self.r, self.r, self.r, self.r)
        )

    def draw(self, card_pen, text_pen):
        display.set_pen(card_pen)
        vector.draw(self.bg)

        # Title
        if self.title:
            display.set_pen(text_pen)
            vector.set_font_size(14)
            _, _, tw, _ = vector.measure_text(self.title)
            tx = int((self.x + self.w // 2) - (tw // 2))
            ty = self.y + 20
            vector.text(self.title, tx, ty)

        # Value text
        if self.text:
            display.set_pen(text_pen)
            vector.set_font_size(self.size)
            _, _, tw, th = vector.measure_text(self.text)
            tx = int((self.x + self.w // 2) - (tw // 2))
            ty = int((self.y + self.h // 2) + (th // 2))
            vector.text(self.text, tx, ty)

    def set_label(self, text):
        self.text = text

    def set_title(self, title):
        self.title = title


# --- Updated 2x2 Grid Layout (smaller boxes, tighter spacing) ---
widgets = [
    Widget(10, 10, 105, 70, 10, 22),     # Solar
    Widget(125, 10, 105, 70, 10, 22),    # Load
    Widget(10, 90, 105, 70, 10, 22),     # EVAC
    Widget(125, 90, 105, 70, 10, 22)     # Grid
]

widgets[0].set_title("Solar")
widgets[1].set_title("Load")
widgets[2].set_title("EVAC")
widgets[3].set_title("Grid")


# --- Larger battery card with SOC label inside ---
bat_card = Polygon()
bat_card.rectangle(10, 170, 220, 55, corners=(10, 10, 10, 10))

def draw_battery_progress_bar(soc, card_pen, text_pen):
    # Draw battery card background
    display.set_pen(card_pen)
    vector.draw(bat_card)

    # "Battery SOC" label INSIDE the battery box (lowered)
    display.set_pen(text_pen)
    vector.set_font_size(16)
    label = "Battery SOC"
    _, _, tw, _ = vector.measure_text(label)
    tx = int((WIDTH // 2) - (tw // 2))
    ty = 170 + 20   # lowered inside the box
    vector.text(label, tx, ty)

    # --- Windows 3.1 style block bar ---
    # Bar position
    bar_x = 20
    bar_y = 200
    bar_w = 200
    bar_h = 18

    # Draw outer border
    display.set_pen(BLACK)
    display.rectangle(bar_x, bar_y, bar_w, bar_h)

    # Inner background
    display.set_pen(display.create_pen(180, 180, 180))
    display.rectangle(bar_x + 2, bar_y + 2, bar_w - 4, bar_h - 4)

    # --- Block logic ---
    total_blocks = 10
    block_spacing = 2
    usable_w = bar_w - 4 - (block_spacing * (total_blocks - 1))
    block_w = usable_w // total_blocks
    block_h = bar_h - 6

    # SOC → number of blocks to fill
    fill_ratio = max(0.0, min(1.0, soc / 100.0)) if soc is not None else 0
    filled_blocks = int(fill_ratio * total_blocks)
    partial_block_ratio = (fill_ratio * total_blocks) - filled_blocks

    # Colour gradient: red → yellow → green
    # Leftmost block = red (hue 0.0)
    # Middle block = yellow (hue 0.15)
    # Rightmost block = green (hue 0.33)
    def block_color(i):
        # i ranges 0–9
        # Map to hue 0.0 → 0.33
        hue = 0.0 + (0.33 * (i / 9))
        return display.create_pen_hsv(hue, 0.9, 0.9)

    # Draw blocks
    for i in range(total_blocks):
        bx = bar_x + 2 + i * (block_w + block_spacing)
        by = bar_y + 3

        # Determine fill state
        if i < filled_blocks:
            # Full block
            display.set_pen(block_color(i))
            display.rectangle(bx, by, block_w, block_h)

        elif i == filled_blocks and partial_block_ratio > 0:
            # Partial block
            pw = int(block_w * partial_block_ratio)
            display.set_pen(block_color(i))
            display.rectangle(bx, by, pw, block_h)

        # Unfilled blocks remain grey (already drawn)

import machine

is_holding = False
touch_press_start = 0

def check_touch_exit():
    global is_holding, touch_press_start

    # Refresh touch state
    presto.touch_poll()
    touched = presto.touch.state
    current_time_ms = time.ticks_ms()

    # 1. Finger touches screen
    if touched and not is_holding:
        is_holding = True
        touch_press_start = current_time_ms

    # 2. Finger lifts off
    elif not touched and is_holding:
        is_holding = False

    # 3. Held long enough → exit
    if is_holding and time.ticks_diff(current_time_ms, touch_press_start) > 1500:
        # Optional: small visual feedback
        display.set_layer(1)
        display.set_pen(BLACK)
        display.clear()
        display.set_pen(display.create_pen(200, 200, 200))
        display.text("Exiting...", 5, 10, WIDTH, 2)
        presto.update()
        time.sleep(0.4)

        machine.reset()


# --- MAIN LOOP ---
last_fetch = 0
data = None
current_hue = None

# Update EVAC widget title cleanly
widgets[2].set_title("EVAC")

while True:
    check_touch_exit()
    
    if time.time() - last_fetch > 5 or data is None:
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
            connect_wifi()
        finally:
            if res:
                try:
                    res.close()
                except:
                    pass
            gc.collect()
            last_fetch = time.time()

    # Telemetry Processing & 5-Minute Staleness Guard
    if data and "error" not in data and not data.get("is_stale", False):
        pv_power = data.get('pv_power_kw', 0.0)
        grid_power = data.get('grid_power_kw', 0.0)
        load_power = data.get('load_power_kw', 0.0)
        ev_power = data.get('ev_power_kw', 0.0)  # Correctly reading live EV power
        battery_soc = data.get('battery_soc', 0.0)

        # Dynamic Theme Hues
        if grid_power > 0.05:
            target_hue = 0.0      # Red: Importing Grid Power
        elif pv_power > (load_power + ev_power):
            target_hue = 0.15     # Yellow: Excess Solar Generation
        else:
            target_hue = 0.33     # Green: Self-Sufficient / Battery Discharge

        # Update card text with live telemetry values
        widgets[0].set_label(f"{pv_power:.2f} kW")
        widgets[1].set_label(f"{load_power:.2f} kW")
        widgets[2].set_label(f"{ev_power:.2f} kW")   # Live EVAC value
        widgets[3].set_label(f"{grid_power:.2f} kW")
    else:
        # Fallback when Pi API is unreachable or data is older than 5 minutes
        target_hue = 0.33
        battery_soc = None
        for w in widgets:
            w.set_label("- -")

    # Update rear LEDs only on state change to prevent flickering
    if current_hue != target_hue:
        current_hue = target_hue
        for i in range(7):
            presto.set_led_hsv(i, current_hue, 1.0, 0.5)

    pen_bg = display.create_pen_hsv(current_hue, 0.65, 0.85)
    pen_box = display.create_pen_hsv(current_hue, 0.40, 1.00)
    pen_text = display.create_pen_hsv(current_hue, 0.9, 0.15)

    display.set_pen(pen_bg)
    display.clear()

    for w in widgets:
        w.draw(pen_box, pen_text)

    draw_battery_progress_bar(battery_soc, pen_box, pen_text)

    presto.update()
    time.sleep(0.1)

