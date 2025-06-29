# PIXNET Protocol Specification - Expanded

## 1. Overview

PIXNET is a custom graphical web protocol that transmits pixel-based pages with associated behavioral metadata. It allows the creation of interactive, shader-like interfaces rendered and interpreted entirely by the client.

The protocol enables interaction through pixel-based categories, which define the behavior of interface regions (e.g., navigation, interaction, input zones).

## 2. Connection & Session Management

### 2.1 Transport

* **Transport**: TCP (recommended), QUIC (optional)
* **Port**: 7621 (suggested default)
* **Encoding**: Binary (big-endian)

### 2.2 Connection Lifecycle

1. **Handshake**: Client connects and sends initial request
2. **Session**: Bidirectional communication with frame exchanges
3. **Keepalive**: Periodic ping/pong to maintain connection
4. **Termination**: Graceful close or timeout handling

### 2.3 Initial Handshake

Client → Server:

```
[MAGIC: 6 bytes "PIXHND"]
[Version: 1 byte] (client supported version)
[Capabilities: 2 bytes] (bitfield of client capabilities)
[User-Agent Length: uint8]
[User-Agent: ASCII string]
```

Server → Client:

```
[MAGIC: 6 bytes "PIXACK"]
[Version: 1 byte] (negotiated version)
[Session ID: 8 bytes] (unique session identifier)
[Server Capabilities: 2 bytes]
```

### 2.4 Capability Flags

* Bit 0: Compression support (zlib)
* Bit 1: Partial frame updates
* Bit 2: Animation frames
* Bit 3: Audio support
* Bit 4-15: Reserved for future use

## 3. Protocol Structure

Each message ("frame") consists of the following sections in order:

### 3.1 Frame Header

| Field | Size (bytes) | Description |
|-------|--------------|-------------|
| Magic | 6 | ASCII "PIXNET" |
| Frame Type | 1 | 0=Full Frame, 1=Partial, 2=Animation |
| Sequence | 4 | Frame sequence number |
| Timestamp | 8 | Unix timestamp (microseconds) |
| Flags | 2 | Frame flags (compressed, etc.) |
| Version | 1 | Protocol version (e.g., 1) |
| Width | 2 | Page width in pixels |
| Height | 2 | Page height in pixels |
| Format | 1 | Pixel format (0 = RGBA8) |
| Checksum | 4 | CRC32 of frame data |

### 3.2 Pixel Data

* Size: `width * height * bytes_per_pixel`
* Format: RGBA8 (4 bytes per pixel, R G B A)
* Raw, uncompressed pixel array (row-major order)
* **Compression**: If flag set, pixel data is zlib-compressed

### 3.3 Category Map

* Size: `width * height * 2` bytes
* Each entry: `uint16` category ID per pixel
* Category ID 0 = no behavior (background)

### 3.4 Category Definitions

Structure:

```
[Category Count: uint16]
[Repeated for each category:]
  - ID: uint16
  - Name Length: uint8
  - Name: ASCII string
  - Behavior ID: uint8
  - Priority: uint8 (0-255, higher = more priority)
  - Behavior Data Length: uint16
  - Behavior Data: raw bytes (depends on behavior)
```

## 4. Enhanced Behavior Types

| ID | Name | Description |
|----|------|-------------|
| 0 | None | No behavior |
| 1 | Navigate | Client loads another page |
| 2 | EmitEvent | Client sends named event to server |
| 3 | InputZone | User input (text, selection) |
| 4 | HoverEffect | Visual effect on hover (client-side) |
| 5 | ClickEffect | Visual feedback on click |
| 6 | DragZone | Draggable region |
| 7 | DropZone | Drop target for drag operations |
| 8 | ScrollZone | Scrollable content area |
| 9 | MediaZone | Audio/video playback control |

### 4.1 Navigate (ID 1)

Behavior Data:

```
[URL Length: uint16]
[URL: UTF-8 string]
[Target: uint8] (0=same session, 1=new session)
```

### 4.2 EmitEvent (ID 2)

Behavior Data:

```
[Event Name Length: uint8]
[Event Name: ASCII string]
[Event Type: uint8] (0=click, 1=doubleclick, 2=keypress)
[Debounce MS: uint16] (minimum time between events)
```

### 4.3 InputZone (ID 3)

Behavior Data:

```
[Input Type: uint8] (0=text, 1=checkbox, 2=radio, 3=select, 4=textarea)
[Zone ID: uint16]
[Max Length: uint16] (for text inputs)
[Validation Flags: uint8] (required, numeric, email, etc.)
[Placeholder Length: uint8]
[Placeholder: UTF-8 string]
```

### 4.4 HoverEffect (ID 4)

Behavior Data:

```
[Effect Type: uint8] (0=highlight, 1=darken, 2=custom)
[Color: 4 bytes RGBA] (effect color)
[Intensity: uint8] (0-255)
```

### 4.5 DragZone (ID 6)

Behavior Data:

```
[Drag Type: uint8] (0=move, 1=copy, 2=link)
[Data Type: uint8] (0=text, 1=image, 2=file)
[Data Length: uint16]
[Data: raw bytes]
```

### 4.6 ScrollZone (ID 8)

Behavior Data:

```
[Content Width: uint16]
[Content Height: uint16]
[Scroll X: uint16] (current position)
[Scroll Y: uint16] (current position)
[Scroll Flags: uint8] (horizontal, vertical, smooth)
```

## 5. Client → Server Messages

### 5.1 Emit Event

```
[MAGIC: 6 bytes "PIXEVT"]
[Session ID: 8 bytes]
[Sequence: 4 bytes]
[Zone ID: uint16]
[Event Type: uint8]
[Timestamp: 8 bytes]
[Mouse X: uint16] (cursor position)
[Mouse Y: uint16]
[Modifier Keys: uint8] (ctrl, shift, alt flags)
[Event Name Length: uint8]
[Event Name: ASCII string]
[Payload Length: uint16]
[Payload: raw bytes / UTF-8 string]
```

### 5.2 Input Submit

```
[MAGIC: 6 bytes "PIXINP"]
[Session ID: 8 bytes]
[Sequence: 4 bytes]
[Zone ID: uint16]
[Input Type: uint8]
[Validation Status: uint8] (0=valid, 1=invalid)
[Payload Length: uint16]
[Payload: raw input data]
```

### 5.3 Scroll Update

```
[MAGIC: 6 bytes "PIXSCR"]
[Session ID: 8 bytes]
[Zone ID: uint16]
[Scroll X: uint16]
[Scroll Y: uint16]
```

### 5.4 Drag/Drop Event

```
[MAGIC: 6 bytes "PIXDRG"]
[Session ID: 8 bytes]
[Event Type: uint8] (0=start, 1=move, 2=drop, 3=cancel)
[Source Zone: uint16]
[Target Zone: uint16]
[Mouse X: uint16]
[Mouse Y: uint16]
[Data Length: uint16]
[Data: raw bytes]
```

### 5.5 Keepalive Ping

```
[MAGIC: 6 bytes "PIXPNG"]
[Session ID: 8 bytes]
[Timestamp: 8 bytes]
```

## 6. Server → Client Control Messages

### 6.1 Keepalive Pong

```
[MAGIC: 6 bytes "PIXPOG"]
[Session ID: 8 bytes]
[Timestamp: 8 bytes] (echo from ping)
```

### 6.2 Error Response

```
[MAGIC: 6 bytes "PIXERR"]
[Session ID: 8 bytes]
[Error Code: uint16]
[Error Message Length: uint8]
[Error Message: UTF-8 string]
```

### 6.3 Session Termination

```
[MAGIC: 6 bytes "PIXBYE"]
[Session ID: 8 bytes]
[Reason Code: uint8]
[Reason Length: uint8]
[Reason: UTF-8 string]
```

## 7. Error Codes

| Code | Name | Description |
|------|------|-------------|
| 1000 | PROTOCOL_ERROR | Invalid message format |
| 1001 | UNSUPPORTED_VERSION | Version not supported |
| 1002 | INVALID_SESSION | Session ID not found |
| 1003 | FRAME_TOO_LARGE | Frame exceeds size limits |
| 1004 | CHECKSUM_MISMATCH | Frame corruption detected |
| 1005 | TIMEOUT | Connection timeout |
| 1006 | RATE_LIMITED | Too many requests |
| 1007 | INVALID_ZONE | Zone ID not found |
| 1008 | VALIDATION_FAILED | Input validation error |

## 8. Implementation Guidelines

### 8.1 Client Requirements

* **Rendering**: Must support RGBA pixel rendering
* **Event Handling**: Mouse, keyboard, and touch events
* **Memory Management**: Efficient frame buffering
* **Network**: Async I/O with proper error handling
* **UI Thread**: Non-blocking rendering pipeline

### 8.2 Server Requirements

* **Session Management**: Track multiple concurrent sessions
* **State Management**: Maintain application state per session
* **Frame Generation**: Efficient pixel buffer creation
* **Event Processing**: Handle client interactions
* **Resource Limits**: Prevent DoS through size/rate limiting

### 8.3 Performance Considerations

* **Frame Size Limits**: Max 4096x4096 pixels recommended
* **Compression**: Use zlib for pixel data when beneficial
* **Caching**: Client should cache repeated frame elements
* **Delta Updates**: Future versions should support partial frames
* **Connection Pooling**: Reuse TCP connections where possible

### 8.4 Security Considerations

* **Input Validation**: Sanitize all client inputs
* **Resource Limits**: Enforce maximum frame sizes and rates
* **Session Security**: Use cryptographically secure session IDs
* **DoS Prevention**: Rate limiting and connection limits
* **Data Validation**: Verify checksums and message integrity

## 9. Reference Implementation Structure

### 9.1 Client Architecture

```
┌─────────────────┐
│   Application   │
├─────────────────┤
│  Event Handler  │
├─────────────────┤
│    Renderer     │
├─────────────────┤
│ Protocol Client │
├─────────────────┤
│  Network Layer  │
└─────────────────┘
```

### 9.2 Server Architecture

```
┌─────────────────┐
│   Application   │
├─────────────────┤
│ Session Manager │
├─────────────────┤
│ Frame Generator │
├─────────────────┤
│ Protocol Server │
├─────────────────┤
│  Network Layer  │
└─────────────────┘
```

## 10. Example Message Flows

### 10.1 Initial Page Load

1. Client → Server: Handshake
2. Server → Client: Acknowledgment
3. Client → Server: Page request (EmitEvent)
4. Server → Client: Full frame with page content

### 10.2 Form Interaction

1. User clicks input field
2. Client → Server: EmitEvent (focus)
3. Server → Client: Frame with cursor/highlight
4. User types text
5. Client → Server: InputSubmit
6. Server → Client: Frame with updated content

### 10.3 Navigation

1. User clicks navigation element
2. Client → Server: EmitEvent (navigate)
3. Server → Client: New frame with different page

## 11. Testing Requirements

### 11.1 Protocol Compliance Tests

* Message format validation
* Checksum verification
* Error handling
* Session management
* Timeout behavior

### 11.2 Performance Tests

* Large frame handling
* High-frequency updates
* Memory usage patterns
* Network efficiency
* Concurrent sessions

### 11.3 Interoperability Tests

* Different client implementations
* Version negotiation
* Capability detection
* Graceful degradation

## 12. Future Extensions

### 12.1 Planned Features

* **Partial Updates**: Delta frames for efficiency
* **Animation Frames**: Smooth transitions
* **Audio Streams**: Embedded audio playback
* **Vector Graphics**: SVG-like scalable elements
* **3D Support**: Basic 3D rendering primitives

### 12.2 Backward Compatibility

* Version negotiation ensures compatibility
* Capability flags allow graceful degradation
* Protocol designed for extensibility

## 13. User Experience & URL Scheme

### 13.1 PIXNET URL Scheme

PIXNET uses a custom URL scheme for user-friendly navigation:

**Format:**

```
pixnet://[hostname|ip][:port][/path][?parameters]
```

**Examples:**

```
pixnet://example.com/homepage
pixnet://192.168.1.100:7621/app
pixnet://myserver.local/dashboard
pixnet://game-server.com:8080/lobby?room=main
```

### 13.2 URL Components

* **Scheme**: Always `pixnet://`

* **Hostname/IP**: Server address (domain name or IP address)
* **Port**: Optional, defaults to 7621
* **Path**: Optional application path sent to server
* **Parameters**: Optional query parameters for application state

### 13.3 Client Integration Approaches

#### 13.3.1 Dedicated PIXNET Browser

* Standalone application with address bar

* Native pixnet:// URL handling
* Bookmark management for PIXNET sites
* History and navigation controls

#### 13.3.2 Web Browser Extension

* Browser extension handling pixnet:// links

* Embedded PIXNET viewer in web pages
* Seamless integration with web browsing
* Context menu "Open with PIXNET"

#### 13.3.3 Progressive Web App (PWA)

* Web-based PIXNET client

* Installable on mobile and desktop
* Offline capability
* Native app-like experience

### 13.4 Connection User Interface

#### 13.4.1 Address Bar Interface

```
┌─────────────────────────────────────────────────────┐
│ pixnet://server.com/path    [Go] [Bookmarks ▼]     │
└─────────────────────────────────────────────────────┘
```

#### 13.4.2 Connection Dialog

```
┌─────────────────────────────────────────┐
│ Connect to PIXNET Server                │
├─────────────────────────────────────────┤
│ Server: [game-server.com            ]   │
│ Port:   [7621                       ]   │
│ Path:   [/lobby                     ]   │
│                                         │
│ Recent Connections:                     │
│ • pixnet://myapp.local/dashboard        │
│ • pixnet://192.168.1.100/game           │
│                                         │
│     [Connect]    [Cancel]               │
└─────────────────────────────────────────┘
```

### 13.5 URL Processing Algorithm

Client URL processing steps:

1. Parse pixnet:// URL
2. Extract hostname, port (default 7621), and path
3. Validate hostname/IP format
4. Establish TCP connection to host:port
5. Send handshake with path information
6. Handle connection success/failure

**URL Parsing Example:**

```javascript
const url = new URL("pixnet://server.com:8080/app?mode=admin");
const host = url.hostname;      // "server.com"
const port = url.port || 7621;  // 8080
const path = url.pathname;      // "/app"
const params = url.searchParams; // mode=admin
```

### 13.6 Service Discovery

#### 13.6.1 mDNS/Bonjour Integration

* PIXNET servers advertise via mDNS

* Service type: `_pixnet._tcp.local`
* Clients display "Available PIXNET Services"
* Zero-configuration local network discovery

**mDNS Service Record:**

```
Service Name: My PIXNET App._pixnet._tcp.local
Port: 7621
TXT Records:
  - version=1
  - path=/main
  - description=Interactive Dashboard
```

#### 13.6.2 QR Code Connection

* Servers generate QR codes with pixnet:// URLs

* Mobile clients scan for instant connection
* Useful for IoT devices and temporary access

**QR Code Content:**

```
pixnet://192.168.1.50:7621/device-control?id=sensor01
```

### 13.7 Common Usage Patterns

#### 13.7.1 Gaming Applications

```
pixnet://game-lobby.com/                    # Main lobby
pixnet://minecraft-server.local:7621/admin  # Server admin
pixnet://tournament.gg/bracket?id=2024      # Tournament view
```

#### 13.7.2 Enterprise Applications

```
pixnet://factory-hmi.internal/line-1        # Manufacturing HMI
pixnet://dashboard.company.com/metrics      # Business dashboard
pixnet://monitoring.local/alerts            # System monitoring
```

#### 13.7.3 Personal/Development

```
pixnet://192.168.1.100/home-automation      # Home control
pixnet://localhost:7621/dev-app             # Development testing
pixnet://pi.local/weather-station           # IoT dashboard
```

### 13.8 Bookmark and History Management

#### 13.8.1 Bookmark Format

```json
{
  "title": "Factory Dashboard",
  "url": "pixnet://factory.local/dashboard",
  "favicon": "data:image/png;base64,iVBOR...",
  "lastVisited": "2025-06-29T10:30:00Z",
  "tags": ["work", "monitoring"]
}
```

#### 13.8.2 History Tracking

* Store visited pixnet:// URLs with timestamps

* Track session duration and interaction frequency
* Support history search and filtering
* Privacy controls for history retention

### 13.9 Error Handling for URLs

#### 13.9.1 Connection Errors

* **DNS Resolution Failed**: Show "Server not found" message

* **Connection Refused**: Show "Server unavailable" with retry option
* **Timeout**: Show "Connection timeout" with network troubleshooting
* **Protocol Error**: Show "Incompatible server version"

#### 13.9.2 User-Friendly Error Messages

```
┌─────────────────────────────────────────┐
│ Connection Failed                       │
├─────────────────────────────────────────┤
│ Could not connect to:                   │
│ pixnet://game-server.com/lobby          │
│                                         │
│ • Check your internet connection       │
│ • Verify the server address            │
│ • Try again later                       │
│                                         │
│     [Retry]    [Edit URL]               │
└─────────────────────────────────────────┘
```

### 13.10 Security Considerations for URLs

#### 13.10.1 URL Validation

* Validate hostname format (DNS names, IP addresses)

* Restrict port ranges (avoid well-known system ports)
* Sanitize path components
* Limit URL length to prevent buffer overflows

#### 13.10.2 Trusted Domains

* Allow users to mark domains as trusted

* Warn about connections to untrusted hosts
* Support certificate-based authentication for secure servers
* Implement domain whitelisting for enterprise deployments

## 14. Licensing

This protocol is open and royalty-free. Contributions are welcome.

---

## Implementation Checklist

### Client Implementation

* [ ] TCP/QUIC connection handling

* [ ] Binary message parsing
* [ ] RGBA pixel rendering
* [ ] Category map interpretation
* [ ] Behavior system implementation
* [ ] Event capture and transmission
* [ ] Session management
* [ ] Error handling
* [ ] Compression support

### Server Implementation

* [ ] Network server setup

* [ ] Session management
* [ ] Frame generation
* [ ] Pixel buffer creation
* [ ] Category definition system
* [ ] Event processing
* [ ] Input validation
* [ ] Error responses
* [ ] Performance monitoring
