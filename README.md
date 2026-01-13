# Screen Apps

Collection of applications for framebuffer and screen interaction on embedded systems.

## Apps

### fb-http

HTTP server for viewing and interacting with the framebuffer device (`/dev/fb0`). Provides:

- Real-time framebuffer streaming as PNG images
- Touch input support via `/dev/input/event0`
- Web-based interface for remote screen viewing and interaction

## Building

```bash
make
```

## Installation

```bash
make install DESTDIR=/path/to/install
```

## Running

### Local Development

```bash
./scripts/run-fb-http.sh
```

### Deploy and Run on Remote Host

```bash
./scripts/deploy-run.sh <host> scripts/run-fb-http.sh
```

## Requirements

- Python 3
- Pillow (PIL) for PNG encoding
- Access to `/dev/fb0` and `/dev/input/event0` (requires root)

## License

See LICENSE file for details.
