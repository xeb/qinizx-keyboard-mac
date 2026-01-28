#!/usr/bin/env python3
"""
QINIZX 2-Key Keyboard Programmer

Protocol discovered from reverse engineering Windows software (Run-me.exe):
- Read command: 0x55 (returns 6 config slots)
- Write command: [key_index] + key data bytes
- Key data format depends on mode:
  - Mode 0x01 = combo key (modifier + key)
  - Mode 0x02 = mouse
  - Mode 0x03 = media key
  - Mode 0x04 = string/macro (multiple keycodes typed in sequence)
- Data length for "2K" keyboard = 0x35 (53) bytes
"""

import ctypes
import time
import sys

# HID key codes (USB HID Usage Tables)
KEY_CODES = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07, 'e': 0x08, 'f': 0x09,
    'g': 0x0A, 'h': 0x0B, 'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13, 'q': 0x14, 'r': 0x15,
    's': 0x16, 't': 0x17, 'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
    'y': 0x1C, 'z': 0x1D,
    '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21, '5': 0x22, '6': 0x23,
    '7': 0x24, '8': 0x25, '9': 0x26, '0': 0x27,
    'enter': 0x28, 'esc': 0x29, 'backspace': 0x2A, 'tab': 0x2B, 'space': 0x2C,
    ' ': 0x2C,  # alias for space
    '-': 0x2D, '=': 0x2E, '[': 0x2F, ']': 0x30, '\\': 0x31,
    ';': 0x33, "'": 0x34, '`': 0x35, ',': 0x36, '.': 0x37, '/': 0x38,
    'f1': 0x3A, 'f2': 0x3B, 'f3': 0x3C, 'f4': 0x3D, 'f5': 0x3E, 'f6': 0x3F,
    'f7': 0x40, 'f8': 0x41, 'f9': 0x42, 'f10': 0x43, 'f11': 0x44, 'f12': 0x45,
}

# Extended keycodes for shifted characters (discovered from Windows app IL code)
# The IL stores hex strings: "96" = 0x96, "AB" = 0xAB, etc.
SHIFTED_KEYCODES = {
    '!': 0x96,
    '@': 0x97,
    '#': 0x98,
    '$': 0x99,
    '%': 0x9A,
    '^': 0x9B,
    '&': 0x9C,
    '*': 0x9D,
    '(': 0x9E,
    ')': 0x9F,
    '_': 0xA1,
    '+': 0xA2,
    '{': 0xA3,
    '}': 0xA4,
    '|': 0xA5,
    ':': 0xA6,
    '"': 0xA7,
    '<': 0xA8,
    '>': 0xA9,
    '?': 0xAA,
    '~': 0x95,
}

# Extended keycodes for uppercase letters (A-Z = 0xAB-0xC4)
UPPERCASE_KEYCODES = {chr(ord('A') + i): 0xAB + i for i in range(26)}

# Mode constants
MODE_COMBO = 0x01     # Single key with modifier
MODE_MOUSE = 0x02     # Mouse action
MODE_MEDIA = 0x03     # Media key
MODE_STRING = 0x04    # String/macro mode (sequence of keys)

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
hidapi.hid_read_timeout.restype = ctypes.c_int
hidapi.hid_read_timeout.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]

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
DATA_LEN = 0x35  # 53 bytes for 2K keyboard


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


def read_config(handle):
    """Read current keyboard configuration."""
    buf = ctypes.create_string_buffer(64)

    # Send read command
    cmd = bytes([0x55] + [0]*63)
    cbuf = ctypes.create_string_buffer(cmd)
    hidapi.hid_write(handle, cbuf, 64)

    # Read responses (6 config slots)
    configs = []
    for _ in range(6):
        result = hidapi.hid_read_timeout(handle, buf, 64, 200)
        if result > 0:
            configs.append(bytes(buf.raw[:result]))

    return configs


def hid_send(handle, data):
    """
    Send data to keyboard using the Windows app protocol.

    From IL analysis of K2Form::hidSend:
    1. Create array of size (data.length + 1)
    2. Set array[0] = data.length (the length byte)
    3. Copy data starting at array[1]
    4. Create HidReport with this data
    5. WriteReport with 500ms timeout

    The data should be exactly DATA_LEN (53) bytes.
    Final payload: [length] [data...] padded to 64 bytes.
    """
    # Ensure data is exactly DATA_LEN bytes
    if len(data) < DATA_LEN:
        data = list(data) + [0] * (DATA_LEN - len(data))
    data = data[:DATA_LEN]

    # Prepend length byte (this is what the Windows app does!)
    payload = bytes([len(data)]) + bytes(data)
    # Pad to 64 bytes for HID report
    payload = payload + bytes(64 - len(payload))

    cbuf = ctypes.create_string_buffer(payload)
    result = hidapi.hid_write(handle, cbuf, 64)

    # Sleep 20ms like Windows app does (IL shows Thread.Sleep(0x14) = 20ms)
    time.sleep(0.02)

    return result


def program_single_key(handle, key_num, keycode, modifier=0):
    """
    Program a key with a single keycode (combo mode).

    key_num: 1 or 2 (physical key number)
    keycode: HID keycode (e.g., 0x04 for 'A')
    modifier: Modifier byte (0 for none)
    """
    # Build key data: [key_index, mode, modifier, keycode, ...padding...]
    # Mode 0x01 = combo key
    key_data = [key_num, MODE_COMBO, modifier, keycode] + [0x00] * (DATA_LEN - 3)
    key_data = key_data[:DATA_LEN]  # Ensure exactly DATA_LEN bytes after key_index

    print(f"  Data: {bytes(key_data[:10]).hex()}...")

    return hid_send(handle, key_data)


def char_to_keycode(char):
    """
    Convert a character to its extended keycode.
    Returns keycode or None if unknown.

    The keyboard firmware uses:
    - 0x04-0x1D for lowercase a-z
    - 0x1E-0x27 for digits 0-9
    - 0x96+ for shifted symbols
    - 0xAB+ for uppercase A-Z
    """
    # Check lowercase letters and numbers first
    if char in KEY_CODES:
        return KEY_CODES[char]

    # Check uppercase letters
    if char in UPPERCASE_KEYCODES:
        return UPPERCASE_KEYCODES[char]

    # Check shifted symbols
    if char in SHIFTED_KEYCODES:
        return SHIFTED_KEYCODES[char]

    return None


def program_string(handle, key_num, text):
    """
    Program a key to type a string (macro mode).

    key_num: 1 or 2 (physical key number)
    text: String to type when key is pressed

    Uses extended keycodes (0x96+ for shifted symbols, 0xAB+ for uppercase).
    """
    # Convert text to extended keycodes
    keycodes = []
    for char in text:
        keycode = char_to_keycode(char)
        if keycode is not None:
            keycodes.append(keycode)
        else:
            print(f"Warning: Unknown character '{char}', skipping")

    if not keycodes:
        print("Error: No valid keycodes")
        return -1

    # Format: [key_num, MODE_STRING, 0x00, keycode1, keycode2, ...]
    key_data = [key_num, MODE_STRING, 0x00] + keycodes

    # Pad with 0x00 to reach DATA_LEN total
    remaining = DATA_LEN - len(key_data)
    if remaining > 0:
        key_data += [0x00] * remaining

    key_data = key_data[:DATA_LEN]  # Ensure exactly DATA_LEN bytes

    print(f"  Data ({len(key_data)} bytes): {bytes(key_data[:24]).hex()}...")

    return hid_send(handle, key_data)


def program_key(handle, key_num, keycode, modifier=0):
    """Legacy wrapper for single key programming."""
    return program_single_key(handle, key_num, keycode, modifier)


def main():
    if len(sys.argv) < 3:
        print("Usage: python program_key.py <key_num> <keycode_or_string>")
        print("  key_num: 1 or 2")
        print("  keycode: HID keycode in hex (e.g., 04) or key name (e.g., 'a')")
        print("  string: Text to type (prefix with 'string:' for macro mode)")
        print()
        print("Examples:")
        print("  python program_key.py 1 a              # Set key 1 to 'A'")
        print("  python program_key.py 2 enter          # Set key 2 to Enter")
        print("  python program_key.py 1 'string:hello' # Key 1 types 'hello'")
        print("  python program_key.py 1 'string:rock and roll'")
        print()
        print("Available key names:", ', '.join(sorted(KEY_CODES.keys())))
        return

    key_num = int(sys.argv[1])
    if key_num not in [1, 2]:
        print("Error: key_num must be 1 or 2")
        return

    arg = sys.argv[2]

    # Check if this is a string/macro mode
    is_string_mode = arg.lower().startswith('string:')

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

    # Read current config
    print("\nCurrent configuration:")
    configs = read_config(handle)
    for i, cfg in enumerate(configs):
        if cfg:
            print(f"  Slot {i}: {cfg[:8].hex()}")

    hidapi.hid_close(handle)

    # Reopen for write
    handle = hidapi.hid_open_path(path.encode())

    if is_string_mode:
        # String/macro mode
        text = arg[7:]  # Remove 'string:' prefix
        print(f"\nProgramming key {key_num} to type: '{text}'")
        result = program_string(handle, key_num, text)
        print(f"  Write result: {result} bytes")

        # Send twice (as Windows app does)
        time.sleep(0.1)
        result = program_string(handle, key_num, text)
        print(f"  Write result (2nd): {result} bytes")
    else:
        # Single key mode
        keycode_arg = arg.lower()
        if keycode_arg in KEY_CODES:
            keycode = KEY_CODES[keycode_arg]
        else:
            try:
                keycode = int(keycode_arg, 16)
            except ValueError:
                print(f"Error: Unknown key '{keycode_arg}'")
                print("Available key names:", ', '.join(sorted(KEY_CODES.keys())))
                hidapi.hid_close(handle)
                hidapi.hid_exit()
                return

        print(f"\nProgramming key {key_num} to keycode 0x{keycode:02X}")
        result = program_single_key(handle, key_num, keycode)
        print(f"  Write result: {result} bytes")

        # Send twice (as Windows app does)
        time.sleep(0.1)
        result = program_single_key(handle, key_num, keycode)
        print(f"  Write result (2nd): {result} bytes")

    hidapi.hid_close(handle)

    # Re-read config to verify
    time.sleep(0.2)
    handle = hidapi.hid_open_path(path.encode())
    print("\nConfiguration after programming:")
    configs = read_config(handle)
    for i, cfg in enumerate(configs):
        if cfg:
            print(f"  Slot {i}: {cfg[:8].hex()}")

    hidapi.hid_close(handle)
    hidapi.hid_exit()

    print("\nDone! Unplug and replug the keyboard to test.")


if __name__ == '__main__':
    main()
