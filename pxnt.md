# PXNT File Format Specification v1.0

## 1. Overview

PXNT (PixNet Template) is a binary file format designed to store and interchange PIXNET pages. It encapsulates all components required to render and interact with a PIXNET page: pixel data, behavioral metadata, animations, and page properties.

The format is optimized for:
- Fast loading and parsing
- Efficient storage with optional compression
- Version compatibility
- Streaming capabilities
- Caching and offline use

## 2. File Structure

A PXNT file consists of the following sections in order:

```
┌─────────────────┐
│  File Header    │  (32 bytes)
├─────────────────┤
│  Page Metadata  │  (variable)
├─────────────────┤
│  Pixel Data     │  (width × height × 4 bytes)
├─────────────────┤
│  Category Map   │  (width × height × 2 bytes)
├─────────────────┤
│ Category Defs   │  (variable)
├─────────────────┤
│ Animation Data  │  (optional, variable)
├─────────────────┤
│  Audio Data     │  (optional, variable)
├─────────────────┤
│   Metadata      │  (optional, variable)
├─────────────────┤
│  File Footer    │  (16 bytes)
└─────────────────┘
```

## 3. File Header

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Magic | ASCII "PXNT" |
| 4 | 2 | Version | File format version (1) |
| 6 | 2 | Flags | Format flags (compressed, etc.) |
| 8 | 4 | File Size | Total file size in bytes |
| 12 | 4 | Created | Unix timestamp (seconds) |
| 16 | 4 | Modified | Last modified timestamp |
| 20 | 4 | CRC32 | Checksum of entire file |
| 24 | 2 | Width | Page width in pixels |
| 26 | 2 | Height | Page height in pixels |
| 28 | 1 | Pixel Format | 0=RGBA8, 1=RGB8, 2=RGBA16 |
| 29 | 1 | Compression | 0=None, 1=zlib, 2=lz4 |
| 30 | 2 | Reserved | Must be zero |

### 3.1 Format Flags

| Bit | Name | Description |
|-----|------|-------------|
| 0 | COMPRESSED | Pixel data is compressed |
| 1 | HAS_ANIMATION | File contains animation data |
| 2 | HAS_AUDIO | File contains audio streams |
| 3 | HAS_METADATA | File contains extended metadata |
| 4 | STREAMING | File supports streaming/partial loading |
| 5 | ENCRYPTED | File is encrypted (future use) |
| 6-15 | Reserved | Must be zero |

## 4. Page Metadata

| Field | Size | Type | Description |
|-------|------|------|-------------|
| Title Length | 2 | uint16 | Length of page title |
| Title | variable | UTF-8 | Page title string |
| Author Length | 1 | uint8 | Length of author name |
| Author | variable | UTF-8 | Author name |
| Description Length | 2 | uint16 | Length of description |
| Description | variable | UTF-8 | Page description |
| URL Length | 2 | uint16 | Length of canonical URL |
| URL | variable | UTF-8 | Canonical pixnet:// URL |
| Keywords Count | 1 | uint8 | Number of keywords |
| Keywords | variable | UTF-8[] | Array of keyword strings |
| Custom Fields Count | 1 | uint8 | Number of custom metadata fields |
| Custom Fields | variable | Key-Value[] | Custom metadata pairs |

### 4.1 Custom Field Format

```
[Key Length: uint8]
[Key: UTF-8 string]
[Value Length: uint16]
[Value: UTF-8 string]
```

## 5. Pixel Data Section

### 5.1 Uncompressed Format

- Raw pixel array in row-major order
- RGBA8: 4 bytes per pixel (R, G, B, A)
- RGB8: 3 bytes per pixel (R, G, B) - Alpha assumed 255
- RGBA16: 8 bytes per pixel (R, G, B, A as uint16)

### 5.2 Compressed Format

```
[Uncompressed Size: uint32]
[Compressed Data: variable length]
```

Compression algorithms:
- **zlib**: Standard deflate compression
- **lz4**: Fast compression for real-time applications

## 6. Category Map Section

- Size: `width × height × 2` bytes
- Each pixel maps to a category ID (uint16)
- Category ID 0 = no behavior (background)
- Little-endian byte order

### 6.1 Compression

If COMPRESSED flag is set:

```
[Uncompressed Size: uint32]
[Compressed Category Map: variable]
```

## 7. Category Definitions Section

```
[Category Count: uint16]
[Repeated for each category:]
  ├─ Category Header (8 bytes)
  ├─ Category Name (variable)
  ├─ Behavior Data (variable)
  └─ Extended Properties (optional)
```

### 7.1 Category Header

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 2 | ID | Category identifier |
| 2 | 1 | Behavior ID | Behavior type (see PIXNET spec) |
| 3 | 1 | Priority | Execution priority (0-255) |
| 4 | 2 | Name Length | Length of category name |
| 6 | 2 | Data Length | Length of behavior data |

### 7.2 Extended Properties

Optional key-value pairs for future extensibility:

```
[Property Count: uint8]
[Repeated for each property:]
  ├─ Key Length: uint8
  ├─ Key: UTF-8 string
  ├─ Value Type: uint8 (0=string, 1=int, 2=float, 3=bool)
  ├─ Value Length: uint16
  └─ Value: typed data
```

## 8. Animation Data Section

Present only if HAS_ANIMATION flag is set.

```
[Animation Header: 16 bytes]
[Frame Count: uint32]
[Frame Index: Frame Count × 12 bytes]
[Frame Data: variable]
```

### 8.1 Animation Header

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Duration | Total animation duration (ms) |
| 4 | 2 | FPS | Target frames per second |
| 6 | 1 | Loop Type | 0=none, 1=infinite, 2=count |
| 7 | 1 | Loop Count | Number of loops (if type=2) |
| 8 | 4 | Easing | Easing function ID |
| 12 | 4 | Reserved | Must be zero |

### 8.2 Frame Index Entry

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Timestamp | Frame time offset (ms) |
| 4 | 4 | Data Offset | Offset to frame data |
| 8 | 4 | Data Size | Size of frame data |

### 8.3 Frame Data Types

- **Full Frame**: Complete pixel + category data
- **Delta Frame**: Only changed pixels
- **Category Only**: Only category map changes
- **Transform**: Geometric transformations

## 9. Audio Data Section

Present only if HAS_AUDIO flag is set.

```
[Audio Header: 24 bytes]
[Stream Count: uint32]
[Stream Index: Stream Count × 16 bytes]
[Audio Streams: variable]
```

### 9.1 Audio Header

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Format | Audio format (0=PCM, 1=OGG, 2=MP3) |
| 4 | 4 | Sample Rate | Samples per second |
| 8 | 2 | Channels | Number of audio channels |
| 10 | 2 | Bit Depth | Bits per sample |
| 12 | 4 | Total Samples | Total number of samples |
| 16 | 4 | Loop Start | Loop start sample |
| 20 | 4 | Loop End | Loop end sample |

### 9.2 Stream Index Entry

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 2 | Stream ID | Unique stream identifier |
| 2 | 2 | Trigger Type | 0=autoplay, 1=click, 2=hover |
| 4 | 4 | Data Offset | Offset to audio data |
| 8 | 4 | Data Size | Size of audio data |
| 12 | 4 | Reserved | Must be zero |

## 10. Extended Metadata Section

Present only if HAS_METADATA flag is set.

```
[Metadata Header: 8 bytes]
[Section Count: uint32]
[Section Index: Section Count × 12 bytes]
[Section Data: variable]
```

### 10.1 Metadata Sections

Predefined section types:

| Type ID | Name | Description |
|---------|------|-------------|
| 1 | THUMBNAIL | Page thumbnail image |
| 2 | PALETTE | Color palette information |
| 3 | FONTS | Font definitions |
| 4 | SCRIPTS | Embedded JavaScript |
| 5 | TEMPLATES | Reusable components |
| 6 | HISTORY | Edit history |
| 7 | COMMENTS | Developer comments |
| 8 | PERFORMANCE | Performance hints |

### 10.2 Section Index Entry

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Type ID | Section type identifier |
| 4 | 4 | Data Offset | Offset to section data |
| 8 | 4 | Data Size | Size of section data |

## 11. File Footer

| Offset | Size | Field | Description |
|--------|------|-------|-------------|
| 0 | 4 | Magic | ASCII "TNXP" (PXNT reversed) |
| 4 | 4 | Header CRC | CRC32 of file header |
| 8 | 4 | Data CRC | CRC32 of all data sections |
| 12 | 4 | File Size | Echo of total file size |

## 12. MIME Type and File Extensions

- **MIME Type**: `application/vnd.pixnet.pxnt`
- **File Extension**: `.pxnt`
- **Content-Type Header**: `application/vnd.pixnet.pxnt; version=1`

## 13. Validation and Integrity

### 13.1 Validation Steps

1. Verify file magic number "PXNT"
2. Check file size matches header declaration
3. Validate CRC32 checksums
4. Verify section boundaries
5. Check required fields are present
6. Validate pixel format and dimensions

### 13.2 Error Codes

| Code | Name | Description |
|------|------|-------------|
| 1000 | INVALID_MAGIC | File magic number incorrect |
| 1001 | UNSUPPORTED_VERSION | File version not supported |
| 1002 | CHECKSUM_MISMATCH | File corruption detected |
| 1003 | INVALID_DIMENSIONS | Width/height out of bounds |
| 1004 | TRUNCATED_FILE | File appears incomplete |
| 1005 | INVALID_COMPRESSION | Compression format error |
| 1006 | SECTION_OVERFLOW | Section data exceeds boundaries |

## 14. Performance Considerations

### 14.1 Memory Mapping

- Files designed for memory mapping
- Sequential access patterns for streaming
- Lazy loading of optional sections
- Efficient random access to pixel regions

### 14.2 Size Limits

- **Maximum Dimensions**: 65535 × 65535 pixels
- **Maximum File Size**: 4GB (uint32 limit)
- **Maximum Categories**: 65535
- **Maximum Animation Frames**: 16777215

### 14.3 Optimization Hints

- Use compression for large uniform areas
- Delta frames for animations
- Separate audio streams for better caching
- Thumbnail generation for previews

## 15. Streaming Support

### 15.1 Progressive Loading

Files can be designed for progressive loading:

1. **Header + Metadata**: Basic page information
2. **Low-res Preview**: Downsampled pixel data
3. **Category Map**: Interaction regions
4. **Full Resolution**: Complete pixel data
5. **Optional Data**: Animation, audio, metadata

### 15.2 Chunk-based Access

```
[Chunk Header: 8 bytes]
├─ Chunk Type: uint32
├─ Chunk Size: uint32
[Chunk Data: variable]
```

## 16. Security Considerations

### 16.1 Input Validation

- Validate all field lengths
- Check array bounds
- Verify compression ratios
- Sanitize text fields

### 16.2 Resource Limits

- Maximum memory allocation limits
- Decompression bomb protection
- Animation frame rate limiting
- Audio stream duration limits

## 17. Tools and Utilities

### 17.1 Reference Implementation

Suggested command-line tools:

- `pxnt-info`: Display file information
- `pxnt-extract`: Extract components from PXNT
- `pxnt-convert`: Convert between formats
- `pxnt-validate`: File validation
- `pxnt-optimize`: Compression optimization

### 17.2 Library Interface

```c
// Core API functions
pxnt_file_t* pxnt_open(const char* filename);
int pxnt_get_dimensions(pxnt_file_t* file, uint16_t* width, uint16_t* height);
int pxnt_get_pixels(pxnt_file_t* file, uint8_t* buffer);
int pxnt_get_categories(pxnt_file_t* file, uint16_t* buffer);
void pxnt_close(pxnt_file_t* file);
```

## 18. Examples

### 18.1 Minimal PXNT File

A minimal 1×1 pixel PXNT file structure:

```
PXNT                    # Magic
0001                    # Version 1
0000                    # No flags
00000048                # File size: 72 bytes
[timestamp]             # Created time
[timestamp]             # Modified time
[crc32]                 # File checksum
0001                    # Width: 1
0001                    # Height: 1
00                      # RGBA8 format
00                      # No compression
0000                    # Reserved

# Page Metadata (minimal)
0000                    # No title
00                      # No author
0000                    # No description
0000                    # No URL
00                      # No keywords
00                      # No custom fields

# Pixel Data (1 pixel RGBA)
FF FF FF FF             # White pixel

# Category Map (1 entry)
0000                    # Category 0 (no behavior)

# Category Definitions
0000                    # No categories

TNXP                    # Footer magic
[header_crc]            # Header checksum
[data_crc]              # Data checksum
00000048                # File size echo
```

### 18.2 File Creation Example

```python
import struct

def create_minimal_pxnt():
    # Header
    header = struct.pack('<4sHHIIIIHHBBH',
        b'PXNT',    # Magic
        1,          # Version
        0,          # Flags
        72,         # File size
        1640995200, # Created
        1640995200, # Modified
        0,          # CRC (calculate later)
        1,          # Width
        1,          # Height
        0,          # RGBA8
        0,          # No compression
        0           # Reserved
    )
    
    # Metadata (all empty)
    metadata = struct.pack('<HBHHBB', 0, 0, 0, 0, 0, 0)
    
    # Pixel data (white pixel)
    pixels = struct.pack('<BBBB', 255, 255, 255, 255)
    
    # Category map
    categories = struct.pack('<H', 0)
    
    # Category definitions
    cat_defs = struct.pack('<H', 0)
    
    # Footer
    footer = struct.pack('<4sIII', b'TNXP', 0, 0, 72)
    
    return header + metadata + pixels + categories + cat_defs + footer
```

## 19. Version History

- **v1.0**: Initial specification
  - Basic pixel and category support
  - Animation and audio extensions
  - Compression support
  - Streaming capabilities

## 20. Future Extensions

### 20.1 Planned Features

- **Vector Graphics**: SVG-like scalable elements
- **3D Data**: Basic 3D geometry support
- **Encryption**: File-level encryption
- **Differential Updates**: Efficient page updates
- **Multi-language**: Localization support

### 20.2 Backward Compatibility

- Version field ensures compatibility
- Unknown sections can be safely ignored
- Extensible metadata system
- Optional feature flags

---

## Implementation Checklist

### File Writer Implementation

- [ ] Binary file writing with proper endianness
- [ ] CRC32 checksum calculation
- [ ] Compression integration (zlib/lz4)
- [ ] Animation frame processing
- [ ] Audio stream encoding
- [ ] Metadata serialization
- [ ] Input validation and error handling

### File Reader Implementation

- [ ] Memory-mapped file access
- [ ] Progressive loading support
- [ ] Decompression handling
- [ ] Category map parsing
- [ ] Animation playback support
- [ ] Audio stream decoding
- [ ] Robust error handling
- [ ] Security validation

### Testing Requirements

- [ ] Round-trip conversion tests
- [ ] Corruption detection tests
- [ ] Large file handling
- [ ] Memory usage validation
- [ ] Performance benchmarks
- [ ] Cross-platform compatibility