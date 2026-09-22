import time
from presto import Presto
import urequests
import secrets

# Construct Modbus test endpoint dynamically from secrets.py
PI_API_URL = f"{secrets.PI_BASE_URL}/api/modbus/test" 

presto = Presto(ambient_light=False, full_res=True)
display = presto.display
WIDTH, HEIGHT = display.get_bounds()  # 480x480

BLACK = display.create_pen(0, 0, 0)
WHITE = display.create_pen(255, 255, 255)
GREEN = display.create_pen(0, 220, 100)
RED = display.create_pen(220, 50, 50)
YELLOW = display.create_pen(240, 200, 0)


def draw_status(data):
    display.set_pen(BLACK)
    display.clear()

    # Header
    display.set_pen(WHITE)
    display.text("MODBUS TCP TEST", 30, 40, scale=3)

    if not data:
        display.set_pen(RED)
        display.text("Connecting to Pi...", 30, 120, scale=3)
        presto.update()
        return

    port_open = data.get("port_open", False)
    read_ok = data.get("read_ok", False)
    write_ok = data.get("write_ok", False)
    msg = data.get("message", "Testing...")

    # Indicator 1: Port 502 Status
    display.set_pen(GREEN if port_open else RED)
    display.text(
        f"Port 502:  {'OPEN' if port_open else 'CLOSED'}", 30, 120, scale=3
    )

    # Indicator 2: Read Permission
    display.set_pen(GREEN if read_ok else RED)
    display.text(f"Read Mode: {'OK' if read_ok else 'FAIL'}", 30, 180, scale=3)

    # Indicator 3: Write Permission
    display.set_pen(GREEN if write_ok else RED)
    display.text(
        f"Write Mode:{'ENABLED' if write_ok else 'DISABLED'}",
        30,
        240,
        scale=3,
    )

    # Summary Card Banner
    banner_pen = GREEN if write_ok else (YELLOW if port_open else RED)
    display.set_pen(banner_pen)
    display.rectangle(20, 320, WIDTH - 40, 120)

    display.set_pen(BLACK)
    if write_ok:
        display.text("READY FOR EV CONTROL", 40, 350, scale=3)
        display.text("Modbus TCP Write Verified", 40, 390, scale=2)
    else:
        display.text("ACTION REQUIRED", 40, 350, scale=3)
        display.text(msg[:28], 40, 390, scale=2)

    presto.update()


while True:
    try:
        res = urequests.get(PI_API_URL)
        if res.status_code == 200:
            payload = res.json()
            res.close()
            draw_status(payload)
        else:
            res.close()
            draw_status(None)
    except Exception as e:
        print("Fetch error:", e)
        draw_status(None)

    time.sleep(3)
