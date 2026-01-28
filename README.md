# QINIZX 2-Key Keyboard Programmer for macOS

Program your QINIZX 2-key mini USB keyboard on macOS without needing Windows.

## About the Keyboard

The QINIZX 2-key keyboard is a compact USB HID device commonly sold on Amazon. It's designed for custom macros, shortcuts, and password entry. The official configuration software only runs on Windows, which is a problem for Mac users.

**Device Information:**
- Vendor ID: `0x8808`
- Product ID: `0x6601`
- Also sold under brand names: KOOLERTRON, Vortex, and generic "2-key keyboard"

## Features

- **Single key programming**: Map any HID keycode to either button
- **String/macro mode**: Program a button to type an entire string (passwords, phrases, etc.)
- **LED control**: Set RGB lighting modes and custom colors
- **Full character support**: Uppercase letters, numbers, and special characters (!@#$% etc.)

## Requirements

- macOS (tested on macOS 14+)
- Python 3.8+
- hidapi library

## Installation

1. **Install hidapi:**
   ```bash
   brew install hidapi
   ```

2. **Clone this repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/qinizx-keyboard-mac.git
   cd qinizx-keyboard-mac
   ```

3. **No additional Python packages required** - uses only standard library + hidapi via ctypes.

## Usage

### Program a Single Key

```bash
# Set key 1 to type 'a'
python3 program_key.py 1 a

# Set key 2 to Enter
python3 program_key.py 2 enter

# Set key 1 to F5
python3 program_key.py 1 f5
```

### Program a String (Macro Mode)

```bash
# Set key 1 to type "hello world"
python3 program_key.py 1 "string:hello world"

# Set key 1 to type a password with special characters
python3 program_key.py 1 "string:MyP@ssw0rd!"
```

**Important:** Use double quotes for strings containing `!` to avoid shell escaping issues.

### Control LED Lighting

```bash
# Turn off LEDs
python3 led_control.py off

# Set rainbow mode
python3 led_control.py rainbow

# Set breathing mode
python3 led_control.py breathing

# Set a custom color (red)
python3 led_control.py color red

# Set custom color by hex
python3 led_control.py color "#FF00FF"

# Set custom color by RGB values
python3 led_control.py color 255,128,0
```

### Available Key Names

Letters: `a-z`
Numbers: `0-9`
Function keys: `f1-f12`
Special keys: `enter`, `esc`, `backspace`, `tab`, `space`
Punctuation: `-`, `=`, `[`, `]`, `\`, `;`, `'`, `` ` ``, `,`, `.`, `/`

### Supported Special Characters in Strings

All standard shifted characters are supported:
`!`, `@`, `#`, `$`, `%`, `^`, `&`, `*`, `(`, `)`, `_`, `+`, `{`, `}`, `|`, `:`, `"`, `<`, `>`, `?`, `~`

## After Programming

**Important:** Unplug and replug the keyboard after programming for changes to take effect.

## Troubleshooting

### "Keyboard not found!"
- Make sure the keyboard is plugged in
- Try a different USB port
- Check if another application has the device open

### "Failed to open device!"
- Close any other applications that might be accessing the keyboard
- Try unplugging and replugging the keyboard

### String shows wrong characters
- Make sure you're using double quotes for strings with special characters
- Example: `"string:Test!"` not `'string:Test!'`

## How It Works

The protocol was reverse-engineered from the Windows configuration software (Run-me.exe) by decompiling its .NET IL code. Key discoveries:

- **HID Interface**: Uses vendor-specific usage page `0xFF00`
- **Data Length**: 53 bytes per command (0x35)
- **Modes**:
  - `0x01` = Single key (combo)
  - `0x02` = Mouse
  - `0x03` = Media key
  - `0x04` = String/macro
- **Extended Keycodes**:
  - `0x96-0xAA` for shifted symbols (!@#$ etc.)
  - `0xAB-0xC4` for uppercase A-Z

## License

MIT License - feel free to use, modify, and distribute.

## Contributing

Pull requests welcome! Areas that could use improvement:
- Support for other QINIZX keyboard models (3-key, 6-key, etc.)
- Linux support
- GUI application

## Credits

Protocol reverse-engineered using .NET IL decompilation of the official Windows software.
