#!/usr/bin/env python3

import argparse
import base64
import ctypes
import fcntl
import hashlib
import mmap
import os
import struct
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from io import BytesIO
from urllib.parse import urlparse

from PIL import Image

FBIOGET_VSCREENINFO = 0x4600
FBIOGET_FSCREENINFO = 0x4602

class FbVarScreeninfo(ctypes.Structure):
    _fields_ = [
        ("xres", ctypes.c_uint32),
        ("yres", ctypes.c_uint32),
        ("xres_virtual", ctypes.c_uint32),
        ("yres_virtual", ctypes.c_uint32),
        ("xoffset", ctypes.c_uint32),
        ("yoffset", ctypes.c_uint32),
        ("bits_per_pixel", ctypes.c_uint32),
        ("grayscale", ctypes.c_uint32),
        ("red", ctypes.c_uint32 * 3),
        ("green", ctypes.c_uint32 * 3),
        ("blue", ctypes.c_uint32 * 3),
        ("transp", ctypes.c_uint32 * 3),
        ("nonstd", ctypes.c_uint32),
        ("activate", ctypes.c_uint32),
        ("height", ctypes.c_uint32),
        ("width", ctypes.c_uint32),
        ("accel_flags", ctypes.c_uint32),
        ("pixclock", ctypes.c_uint32),
        ("left_margin", ctypes.c_uint32),
        ("right_margin", ctypes.c_uint32),
        ("upper_margin", ctypes.c_uint32),
        ("lower_margin", ctypes.c_uint32),
        ("hsync_len", ctypes.c_uint32),
        ("vsync_len", ctypes.c_uint32),
        ("sync", ctypes.c_uint32),
        ("vmode", ctypes.c_uint32),
        ("rotate", ctypes.c_uint32),
        ("colorspace", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32 * 4),
    ]

class FbFixScreeninfo(ctypes.Structure):
    _fields_ = [
        ("id", ctypes.c_char * 16),
        ("smem_start", ctypes.c_ulong),
        ("smem_len", ctypes.c_uint32),
        ("type", ctypes.c_uint32),
        ("type_aux", ctypes.c_uint32),
        ("visual", ctypes.c_uint32),
        ("xpanstep", ctypes.c_uint16),
        ("ypanstep", ctypes.c_uint16),
        ("ywrapstep", ctypes.c_uint16),
        ("line_length", ctypes.c_uint32),
        ("mmio_start", ctypes.c_ulong),
        ("mmio_len", ctypes.c_uint32),
        ("accel", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint16),
        ("reserved", ctypes.c_uint16 * 2),
    ]

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0x00
BTN_TOUCH = 0x14a
ABS_X = 0x00
ABS_Y = 0x01
ABS_MT_SLOT = 0x2f
ABS_MT_TRACKING_ID = 0x39
ABS_MT_POSITION_X = 0x35
ABS_MT_POSITION_Y = 0x36

WS_GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def ws_send(conn, data):
    if isinstance(data, str):
        data, op = data.encode(), 0x80 | OP_TEXT
    else:
        op = 0x80 | OP_BINARY
    n = len(data)
    if n < 126:
        header = bytes([op, n])
    elif n < 65536:
        header = bytes([op, 126]) + struct.pack('>H', n)
    else:
        header = bytes([op, 127]) + struct.pack('>Q', n)
    conn.sendall(header + data)

def ws_recv(conn):
    def read(n):
        buf = b''
        while len(buf) < n:
            c = conn.recv(n - len(buf))
            if not c:
                raise ConnectionError
            buf += c
        return buf
    b0, b1 = struct.unpack('BB', read(2))
    n = b1 & 0x7f
    if n == 126:
        n = struct.unpack('>H', read(2))[0]
    elif n == 127:
        n = struct.unpack('>Q', read(8))[0]
    mask = read(4) if b1 & 0x80 else b''
    data = bytearray(read(n))
    if mask:
        for i in range(n):
            data[i] ^= mask[i % 4]
    return b0 & 0xf, bytes(data)

class Framebuffer:
    def __init__(self, device='/dev/fb0'):
        self.device = device
        self.fd = None
        self.mm = None
        self.width = 0
        self.height = 0
        self.virtual_width = 0
        self.virtual_height = 0
        self.bpp = 0
        self.line_length = 0
        self._cache_hash = None
        self._cache_raw = None
        self._cache_png = None
        self._cache_time = 0
        self._open()

    def _open(self):
        self.fd = os.open(self.device, os.O_RDONLY)
        vinfo = FbVarScreeninfo()
        fcntl.ioctl(self.fd, FBIOGET_VSCREENINFO, vinfo)
        finfo = FbFixScreeninfo()
        fcntl.ioctl(self.fd, FBIOGET_FSCREENINFO, finfo)

        self.width = vinfo.xres
        self.virtual_width = vinfo.xres_virtual
        self.height = vinfo.yres
        self.virtual_height = vinfo.yres_virtual
        self.bpp = vinfo.bits_per_pixel
        self.line_length = finfo.line_length

        size = self.line_length * self.virtual_height
        self.mm = mmap.mmap(self.fd, size, mmap.MAP_SHARED, mmap.PROT_READ)
        log(f"Framebuffer: {self.width}x{self.height} ({self.virtual_width}x{self.virtual_height} virtual) @ {self.bpp}bpp, line_length={self.line_length}")

    def get_snapshot(self, client_etag=None):
        vinfo = FbVarScreeninfo()
        fcntl.ioctl(self.fd, FBIOGET_VSCREENINFO, vinfo)
        offset = vinfo.yoffset * self.line_length

        self.mm.seek(offset)
        raw = self.mm.read(self.line_length * self.height)
        raw_hash = hashlib.md5(raw).hexdigest()[:16]
        if client_etag and client_etag == raw_hash:
            return raw_hash, None
        if raw_hash == self._cache_hash and self._cache_png:
            return raw_hash, self._cache_png
        if self.bpp == 32:
            img = Image.frombytes('RGBA', (self.width, self.height), raw, 'raw', 'BGRA', self.line_length)
            img = img.convert('RGB')
        elif self.bpp == 16:
            img = Image.frombytes('RGB', (self.width, self.height), raw, 'raw', 'BGR;16', self.line_length)
        else:
            img = Image.frombytes('RGB', (self.width, self.height), raw, 'raw', 'BGR', self.line_length)
        buf = BytesIO()
        img.save(buf, 'PNG', compress_level=6)
        png_data = buf.getvalue()
        self._cache_hash = raw_hash
        self._cache_png = png_data
        return raw_hash, png_data

    def close(self):
        if self.mm:
            self.mm.close()
        if self.fd:
            os.close(self.fd)

class TouchInput:
    def __init__(self, device='/dev/input/event0', fb_width=1024, fb_height=600):
        self.device = device
        self.fd = None
        self.fb_width = fb_width
        self.fb_height = fb_height
        self.touch_max_x = 1024
        self.touch_max_y = 600
        self._open()

    def _open(self):
        try:
            self.fd = os.open(self.device, os.O_WRONLY)
            self._get_abs_info()
            log(f"Touch device: {self.device}, range: {self.touch_max_x}x{self.touch_max_y}")
        except OSError as e:
            log(f"Failed to open touch device: {e}")
            self.fd = None

    def _get_abs_info(self):
        EVIOCGABS = lambda axis: 0x80184540 + axis
        try:
            buf = bytearray(24)
            fcntl.ioctl(self.fd, EVIOCGABS(ABS_MT_POSITION_X), buf)
            self.touch_max_x = struct.unpack('iiiii', buf[:20])[2]
            fcntl.ioctl(self.fd, EVIOCGABS(ABS_MT_POSITION_Y), buf)
            self.touch_max_y = struct.unpack('iiiii', buf[:20])[2]
        except OSError:
            try:
                fcntl.ioctl(self.fd, EVIOCGABS(ABS_X), buf)
                self.touch_max_x = struct.unpack('iiiii', buf[:20])[2]
                fcntl.ioctl(self.fd, EVIOCGABS(ABS_Y), buf)
                self.touch_max_y = struct.unpack('iiiii', buf[:20])[2]
            except OSError:
                pass

    def _write_event(self, ev_type, code, value):
        if self.fd is None:
            return
        tv_sec = int(time.time())
        tv_usec = int((time.time() % 1) * 1000000)
        event = struct.pack('llHHi', tv_sec, tv_usec, ev_type, code, value)
        os.write(self.fd, event)

    def _scale(self, x, y):
        touch_x = int(x * self.touch_max_x / self.fb_width)
        touch_y = int(y * self.touch_max_y / self.fb_height)
        return touch_x, touch_y

    def tap(self, x, y):
        if self.fd is None:
            log(f"Touch device not available, would tap at ({x}, {y})")
            return
        touch_x, touch_y = self._scale(x, y)
        log(f"Tap at ({x}, {y}) -> touch ({touch_x}, {touch_y})")
        self._write_event(EV_ABS, ABS_MT_SLOT, 0)
        self._write_event(EV_ABS, ABS_MT_TRACKING_ID, 1)
        self._write_event(EV_ABS, ABS_MT_POSITION_X, touch_x)
        self._write_event(EV_ABS, ABS_MT_POSITION_Y, touch_y)
        self._write_event(EV_KEY, BTN_TOUCH, 1)
        self._write_event(EV_SYN, SYN_REPORT, 0)
        time.sleep(0.05)
        self._write_event(EV_ABS, ABS_MT_TRACKING_ID, -1)
        self._write_event(EV_KEY, BTN_TOUCH, 0)
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def touch_down(self, x, y):
        if self.fd is None:
            return
        touch_x, touch_y = self._scale(x, y)
        log(f"Touch down at ({x}, {y})")
        self._write_event(EV_ABS, ABS_MT_SLOT, 0)
        self._write_event(EV_ABS, ABS_MT_TRACKING_ID, 1)
        self._write_event(EV_ABS, ABS_MT_POSITION_X, touch_x)
        self._write_event(EV_ABS, ABS_MT_POSITION_Y, touch_y)
        self._write_event(EV_KEY, BTN_TOUCH, 1)
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def touch_move(self, x, y):
        if self.fd is None:
            return
        touch_x, touch_y = self._scale(x, y)
        self._write_event(EV_ABS, ABS_MT_POSITION_X, touch_x)
        self._write_event(EV_ABS, ABS_MT_POSITION_Y, touch_y)
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def touch_up(self):
        if self.fd is None:
            return
        log(f"Touch up")
        self._write_event(EV_ABS, ABS_MT_TRACKING_ID, -1)
        self._write_event(EV_KEY, BTN_TOUCH, 0)
        self._write_event(EV_SYN, SYN_REPORT, 0)

    def close(self):
        if self.fd:
            os.close(self.fd)

class ScreenHandler(SimpleHTTPRequestHandler):
    framebuffer = None
    touch_input = None
    html_dir = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=self.html_dir, **kwargs)

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/ws' and self.headers.get('Upgrade', '').lower() == 'websocket':
            self.handle_websocket()
        else:
            super().do_GET()

    def handle_websocket(self):
        key = self.headers.get('Sec-WebSocket-Key', '').strip()
        accept = base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()
        self.wfile.write(
            f'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n'.encode()
        )
        self.wfile.flush()
        self.close_connection = True
        conn = self.connection
        last_hash = None
        log(f"WS connected: {self.client_address[0]}")
        try:
            while True:
                op, data = ws_recv(conn)
                if op == OP_CLOSE:
                    break
                if op == OP_TEXT:
                    text = data.decode()
                    if ':' in text:
                        parts = text.split(':')
                        a = parts[0]
                        x = int(parts[1]) if len(parts) > 1 else 0
                        y = int(parts[2]) if len(parts) > 2 else 0
                        if a == 'down':
                            self.touch_input.touch_down(x, y)
                        elif a == 'move':
                            self.touch_input.touch_move(x, y)
                        elif a == 'up':
                            self.touch_input.touch_up()
                        elif a == 'tap':
                            self.touch_input.tap(x, y)
                    else:
                        h, png = self.framebuffer.get_snapshot(last_hash)
                        if png:
                            last_hash = h
                            ws_send(conn, png)
                        else:
                            ws_send(conn, '=')
        except Exception:
            pass
        log(f"WS disconnected: {self.client_address[0]}")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_html_dir = os.path.join(script_dir, 'html')
    installed_html_dir = '/usr/share/fb-http-ws/html'

    if os.path.isdir(local_html_dir):
        default_html_dir = local_html_dir
    else:
        default_html_dir = installed_html_dir

    parser = argparse.ArgumentParser(description='Framebuffer WebSocket Server')
    parser.add_argument('-p', '--port', type=int, default=8093, help='HTTP port')
    parser.add_argument('--bind', default='0.0.0.0', help='Bind address')
    parser.add_argument('--fb', default='/dev/fb0', help='Framebuffer device')
    parser.add_argument('--touch', default='/dev/input/event0', help='Touch input device')
    parser.add_argument('--html-dir', default=default_html_dir, help='Path to HTML directory')
    args = parser.parse_args()

    fb = Framebuffer(args.fb)
    touch = TouchInput(args.touch, fb.width, fb.height)

    ScreenHandler.framebuffer = fb
    ScreenHandler.touch_input = touch
    ScreenHandler.html_dir = os.fspath(args.html_dir)

    server = ThreadingHTTPServer((args.bind, args.port), ScreenHandler)
    log(f"Server running on http://{args.bind}:{args.port}")
    log(f"  HTML directory: {args.html_dir}")
    log(f"  GET  /     - HTML viewer")
    log(f"  GET  /ws   - WebSocket (frame requests + touch events)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down...")
    finally:
        fb.close()
        touch.close()

if __name__ == '__main__':
    main()
