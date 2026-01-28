#!/usr/bin/env python3
"""
QINIZX 2-Key Keyboard LED Controller

Protocol from reverse engineering Windows software (Run-me.exe):
- RGB mode command: 0x57 + mode_index
- Custom color command: 0x70 + G + R + B (note: GRB order, not RGB!)
"""

import ctypes
import time
import sys

# Load hidapi
for path in ['/opt/homebrew/lib/libhidapi.dylib', '/usr/local/lib/libhidapi.dylib']:
    try:
        hidapi = ctypes.CDLL(path)
        break
    except OSError:
        continue
else:
    print("Error: hidapi not found. Install with: brew install hidapi")
    sys.exit(1)

# Setup hidapi functions
hidapi.hid_init.restype = ctypes.c_int
hidapi.hid_exit.restype = ctypes.c_int
hidapi.hid_enumerate.restype = ctypes.c_void_p
hidapi.hid_enumerate.argtypes = [ctypes.c_ushort, ctypes.c_ushort]
hidapi.hid_open_path.restype = ctypes.c_void_p
hidapi.hid_open_path.argtypes = [ctypes.c_char_p]
hidapi.hid_close.argtypes = [ctypes.c_void_p]
hidapi.hid_write.restype = ctypes.c_int
hidapi.hid_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]

class hid_device_info(ctypes.Structure):
    pass
hid_device_info._fields_ = [
    ('path', ctypes.c_char_p),
    ('vendor_id', ctypes.c_ushort),
    ('product_id', ctypes.c_ushort),
    ('serial_number', ctypes.c_wchar_p),
    ('release_number', ctypes.c_ushort),
    ('manufacturer_string', ctypes.c_wchar_p),
    ('product_string', ctypes.c_wchar_p),
    ('usage_page', ctypes.c_ushort),
    ('usage', ctypes.c_ushort),
    ('interface_number', ctypes.c_int),
    ('next', ctypes.POINTER(hid_device_info)),
]

VENDOR_ID = 0x8808
PRODUCT_ID = 0x6601
DATA_LEN = 0x35  # 53 bytes

# RGB modes (discovered from IL code - these are index values)
RGB_MODES = {
    'off': 0,
    'static': 1,      # May be "custom" mode
    'breathing': 2,
    'rainbow': 3,
    'wave': 4,
    'reactive': 5,
    'custom': 6,      # Allows setting specific color
}


def find_device():
    """Find the vendor interface of the keyboard."""
    dev_info = ctypes.cast(
        hidapi.hid_enumerate(VENDOR_ID, PRODUCT_ID),
        ctypes.POINTER(hid_device_info)
    )

    vendor_path = None
    current = dev_info
    while current:
        info = current.contents
        if info.usage_page == 0xFF00:
            vendor_path = info.path.decode()
            break
        if info.next:
            current = info.next
        else:
            break

    return vendor_path


def hid_send(handle, data):
    """Send data to keyboard using the Windows app protocol."""
    # Ensure data is exactly DATA_LEN bytes
    if len(data) < DATA_LEN:
        data = list(data) + [0] * (DATA_LEN - len(data))
    data = data[:DATA_LEN]

    # Prepend length byte
    payload = bytes([len(data)]) + bytes(data)
    # Pad to 64 bytes for HID report
    payload = payload + bytes(64 - len(payload))

    cbuf = ctypes.create_string_buffer(payload)
    result = hidapi.hid_write(handle, cbuf, 64)
    time.sleep(0.02)
    return result


def set_rgb_mode(handle, mode_index):
    """
    Set the RGB lighting mode.

    Command format: [0x57, mode_index]
    """
    data = [0x57, mode_index]
    print(f"  Sending RGB mode command: {bytes(data[:8]).hex()}")

    result = hid_send(handle, data)
    time.sleep(0.1)
    # Send twice like Windows app does
    result2 = hid_send(handle, data)

    return result > 0 and result2 > 0


def set_custom_color(handle, r, g, b):
    """
    Set a custom static color.

    Command format: [0x70, R, G, B]
    """
    data = [0x70, r, g, b]
    print(f"  Sending color command: {bytes(data[:8]).hex()} (R={r}, G={g}, B={b})")

    result = hid_send(handle, data)
    time.sleep(0.1)
    # Send twice like Windows app does
    result2 = hid_send(handle, data)

    return result > 0 and result2 > 0


def parse_color(color_str):
    """Parse color from various formats."""
    color_str = color_str.lower().strip()

    # Named colors
    colors = {
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255),
        'white': (255, 255, 255),
        'yellow': (255, 255, 0),
        'cyan': (0, 255, 255),
        'magenta': (255, 0, 255),
        'purple': (128, 0, 128),
        'orange': (255, 165, 0),
        'pink': (255, 192, 203),
        'off': (0, 0, 0),
    }

    if color_str in colors:
        return colors[color_str]

    # Hex format: #RRGGBB or RRGGBB
    if color_str.startswith('#'):
        color_str = color_str[1:]

    if len(color_str) == 6:
        try:
            r = int(color_str[0:2], 16)
            g = int(color_str[2:4], 16)
            b = int(color_str[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass

    # RGB format: r,g,b
    if ',' in color_str:
        parts = color_str.split(',')
        if len(parts) == 3:
            try:
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            except ValueError:
                pass

    return None


def main():
    if len(sys.argv) < 2:
        print("QINIZX 2-Key Keyboard LED Controller")
        print()
        print("Usage:")
        print("  python led_control.py <mode>           # Set RGB mode")
        print("  python led_control.py color <color>    # Set custom color")
        print()
        print("RGB Modes:")
        for name, idx in sorted(RGB_MODES.items(), key=lambda x: x[1]):
            print(f"  {name} ({idx})")
        print()
        print("Color formats:")
        print("  Named: red, green, blue, white, yellow, cyan, magenta, purple, orange, pink, off")
        print("  Hex:   #FF0000 or FF0000")
        print("  RGB:   255,0,0")
        print()
        print("Examples:")
        print("  python led_control.py off              # Turn off LEDs")
        print("  python led_control.py rainbow          # Rainbow mode")
        print("  python led_control.py color red        # Static red")
        print("  python led_control.py color #00FF00    # Static green (hex)")
        print("  python led_control.py color 255,128,0  # Static orange (RGB)")
        return

    hidapi.hid_init()

    path = find_device()
    if not path:
        print("Keyboard not found!")
        hidapi.hid_exit()
        return

    print(f"Found keyboard at: {path}")

    handle = hidapi.hid_open_path(path.encode())
    if not handle:
        print("Failed to open device!")
        hidapi.hid_exit()
        return

    arg = sys.argv[1].lower()

    if arg == 'color':
        if len(sys.argv) < 3:
            print("Error: Please specify a color")
            hidapi.hid_close(handle)
            hidapi.hid_exit()
            return

        color = parse_color(sys.argv[2])
        if not color:
            print(f"Error: Unknown color format '{sys.argv[2]}'")
            hidapi.hid_close(handle)
            hidapi.hid_exit()
            return

        r, g, b = color
        print(f"\nSetting custom color: R={r}, G={g}, B={b}")

        # First set to custom mode, then set color
        print("Setting custom mode...")
        set_rgb_mode(handle, RGB_MODES.get('custom', 6))
        time.sleep(0.1)

        print("Setting color...")
        if set_custom_color(handle, r, g, b):
            print("Color set successfully!")
        else:
            print("Failed to set color")

    elif arg in RGB_MODES:
        mode_index = RGB_MODES[arg]
        print(f"\nSetting RGB mode: {arg} (index {mode_index})")

        if set_rgb_mode(handle, mode_index):
            print("Mode set successfully!")
        else:
            print("Failed to set mode")

    else:
        # Try to interpret as a mode index number
        try:
            mode_index = int(arg)
            print(f"\nSetting RGB mode index: {mode_index}")
            if set_rgb_mode(handle, mode_index):
                print("Mode set successfully!")
            else:
                print("Failed to set mode")
        except ValueError:
            print(f"Error: Unknown mode '{arg}'")
            print("Available modes:", ', '.join(RGB_MODES.keys()))

    hidapi.hid_close(handle)
    hidapi.hid_exit()
    print("\nDone!")


if __name__ == '__main__':
    main()
