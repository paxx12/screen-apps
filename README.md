# Screen Apps

Collection of applications for framebuffer and screen interaction on embedded systems.

## Apps

### fb-http

HTTP server for viewing and interacting with the framebuffer device (`/dev/fb0`). Provides:

- Real-time framebuffer streaming as PNG images via HTTP polling with ETag caching
- Touch input support via `/dev/input/event0`
- Web-based interface for remote screen viewing and interaction

Default port: `8092`

### fb-http-ws

WebSocket variant of `fb-http`. The client drives frame delivery by requesting
snapshots over a single WebSocket connection instead of HTTP polling. Touch
events are sent over the same connection as `action:x:y` text frames.
Runs on a fixed 100ms interval with no REST endpoints.

Default port: `8093`

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
