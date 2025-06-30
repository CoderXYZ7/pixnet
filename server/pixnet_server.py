#!/usr/bin/env python3
"""
PIXNET Protocol Server - Complete Implementation
Supports PXNT file format with full protocol features including:
- Multi-page navigation
- Interactive elements
- Animation support
- Audio streaming
- Session management
- Error handling
"""

import socket
import struct
import threading
import time
import zlib
import os
import glob
import secrets
import argparse
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass
from enum import IntEnum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pixnet_server.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('PIXNETServer')

# Protocol constants
MAGIC_PIXNET = b"PIXNET"
MAGIC_HANDSHAKE = b"PIXHND"
MAGIC_ACK = b"PIXACK"
MAGIC_EVENT = b"PIXEVT"
MAGIC_INPUT = b"PIXINP"
MAGIC_PING = b"PIXPNG"
MAGIC_PONG = b"PIXPOG"
MAGIC_ERROR = b"PIXERR"
MAGIC_BYE = b"PIXBYE"

DEFAULT_PORT = 7621
PROTOCOL_VERSION = 1
MAX_SESSION_AGE = 300  # 5 minutes in seconds

# Frame types
class FrameType(IntEnum):
    FULL = 0
    PARTIAL = 1
    ANIMATION = 2

# Error codes
class ErrorCode(IntEnum):
    PROTOCOL_ERROR = 1000
    UNSUPPORTED_VERSION = 1001
    INVALID_SESSION = 1002
    FILE_NOT_FOUND = 1003
    SERVER_ERROR = 1004

# Behavior types
class BehaviorType(IntEnum):
    NONE = 0
    NAVIGATE = 1
    EMIT_EVENT = 2
    INPUT_ZONE = 3
    HOVER_EFFECT = 4
    CLICK_EFFECT = 5
    DRAG_ZONE = 6
    DROP_ZONE = 7
    SCROLL_ZONE = 8
    MEDIA_ZONE = 9

@dataclass
class AnimationFrame:
    pixels: bytes
    duration: int  # in milliseconds

@dataclass
class AudioStream:
    format: int
    sample_rate: int
    channels: int
    data: bytes

@dataclass
class Category:
    id: int
    name: str
    behavior_id: int
    priority: int
    behavior_data: bytes

class PXNTFile:
    """PXNT file parser and container with full format support"""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.header = {}
        self.metadata = {}
        self.pixels = b''
        self.category_map = b''
        self.categories: List[Category] = []
        self.animation_frames: List[AnimationFrame] = []
        self.audio_stream: Optional[AudioStream] = None
        self.extended_metadata = {}
        self.loaded = False
        
        try:
            self.load_file()
            self.loaded = True
        except Exception as e:
            logger.error(f"Failed to load PXNT file {filepath}: {str(e)}")
            raise
    
    def load_file(self):
        """Load and parse a PXNT file"""
        with open(self.filepath, 'rb') as f:
            # Read and validate file header
            self._parse_header(f)
            
            # Read page metadata
            self._parse_metadata(f)
            
            # Read pixel data
            self._parse_pixel_data(f)
            
            # Read category map
            self._parse_category_map(f)
            
            # Read category definitions
            self._parse_category_definitions(f)
            
            # Read optional sections
            if self.header.get('flags', 0) & 0x02:  # HAS_ANIMATION
                self._parse_animation_data(f)
            
            if self.header.get('flags', 0) & 0x04:  # HAS_AUDIO
                self._parse_audio_data(f)
            
            if self.header.get('flags', 0) & 0x08:  # HAS_METADATA
                self._parse_extended_metadata(f)
            
            logger.info(f"Loaded PXNT file: {self.filepath}")
    
    def _parse_header(self, f):
        """Parse PXNT file header"""
        header_data = f.read(32)
        if len(header_data) != 32:
            raise ValueError("Invalid PXNT file header length")
        
        magic = header_data[:4]
        if magic != b'PXNT':
            raise ValueError("Invalid PXNT file magic number")
        
        (version, flags, file_size, created, modified, crc32,
         width, height, pixel_format, compression, reserved) = struct.unpack(
            '<HHIIIIHHBBH', header_data[4:])
        
        self.header = {
            'version': version,
            'flags': flags,
            'file_size': file_size,
            'created': created,
            'modified': modified,
            'crc32': crc32,
            'width': width,
            'height': height,
            'pixel_format': pixel_format,
            'compression': compression
        }
    
    def _parse_metadata(self, f):
        """Parse page metadata section"""
        # Title
        title_len = struct.unpack('<H', f.read(2))[0]
        title = f.read(title_len).decode('utf-8') if title_len > 0 else ""
        
        # Author
        author_len = struct.unpack('<B', f.read(1))[0]
        author = f.read(author_len).decode('utf-8') if author_len > 0 else ""
        
        # Description
        desc_len = struct.unpack('<H', f.read(2))[0]
        description = f.read(desc_len).decode('utf-8') if desc_len > 0 else ""
        
        # URL
        url_len = struct.unpack('<H', f.read(2))[0]
        url = f.read(url_len).decode('utf-8') if url_len > 0 else ""
        
        # Keywords
        keyword_count = struct.unpack('<B', f.read(1))[0]
        keywords = []
        for _ in range(keyword_count):
            kw_len = struct.unpack('<B', f.read(1))[0]
            keywords.append(f.read(kw_len).decode('utf-8'))
        
        # Custom fields
        custom_count = struct.unpack('<B', f.read(1))[0]
        custom_fields = {}
        for _ in range(custom_count):
            key_len = struct.unpack('<B', f.read(1))[0]
            key = f.read(key_len).decode('utf-8')
            value_len = struct.unpack('<H', f.read(2))[0]
            value = f.read(value_len).decode('utf-8')
            custom_fields[key] = value
        
        self.metadata = {
            'title': title,
            'author': author,
            'description': description,
            'url': url,
            'keywords': keywords,
            'custom_fields': custom_fields
        }
    
    def _parse_pixel_data(self, f):
        """Parse pixel data section"""
        width = self.header['width']
        height = self.header['height']
        pixel_format = self.header['pixel_format']
        compression = self.header['compression']
        
        # Calculate expected pixel data size
        bytes_per_pixel = 4 if pixel_format == 0 else (3 if pixel_format == 1 else 8)
        expected_size = width * height * bytes_per_pixel
        
        if compression == 0:  # No compression
            self.pixels = f.read(expected_size)
        else:
            uncompressed_size = struct.unpack('<I', f.read(4))[0]
            compressed_size = struct.unpack('<I', f.read(4))[0]
            compressed_data = f.read(compressed_size)
            
            if compression == 1:  # zlib
                self.pixels = zlib.decompress(compressed_data)
            else:
                raise ValueError(f"Unsupported compression: {compression}")
        
        # Convert to RGBA8 if needed
        if pixel_format == 1:  # RGB8 -> RGBA8
            rgba_pixels = bytearray()
            for i in range(0, len(self.pixels), 3):
                rgba_pixels.extend(self.pixels[i:i+3])
                rgba_pixels.append(255)  # Add alpha
            self.pixels = bytes(rgba_pixels)
    
    def _parse_category_map(self, f):
        """Parse category map section"""
        width = self.header['width']
        height = self.header['height']
        expected_size = width * height * 2
        
        if self.header['flags'] & 0x01:  # COMPRESSED
            uncompressed_size = struct.unpack('<I', f.read(4))[0]
            compressed_size = struct.unpack('<I', f.read(4))[0]
            compressed_data = f.read(compressed_size)
            self.category_map = zlib.decompress(compressed_data)
        else:
            self.category_map = f.read(expected_size)
    
    def _parse_category_definitions(self, f):
        """Parse category definitions section"""
        category_count = struct.unpack('<H', f.read(2))[0]
        
        for _ in range(category_count):
            # Category header
            cat_id = struct.unpack('<H', f.read(2))[0]
            behavior_id = struct.unpack('<B', f.read(1))[0]
            priority = struct.unpack('<B', f.read(1))[0]
            name_len = struct.unpack('<H', f.read(2))[0]
            data_len = struct.unpack('<H', f.read(2))[0]
            
            # Category name
            name = f.read(name_len).decode('utf-8')
            
            # Behavior data
            behavior_data = f.read(data_len)
            
            self.categories.append(Category(
                id=cat_id,
                name=name,
                behavior_id=behavior_id,
                priority=priority,
                behavior_data=behavior_data
            ))
    
    def _parse_animation_data(self, f):
        """Parse animation data section"""
        frame_count = struct.unpack('<I', f.read(4))[0]
        base_delay = struct.unpack('<I', f.read(4))[0]  # ms
        
        for _ in range(frame_count):
            frame_delay = struct.unpack('<I', f.read(4))[0]
            frame_size = struct.unpack('<I', f.read(4))[0]
            frame_data = f.read(frame_size)
            
            if self.header['compression'] == 1:  # zlib
                frame_data = zlib.decompress(frame_data)
            
            self.animation_frames.append(AnimationFrame(
                pixels=frame_data,
                duration=frame_delay if frame_delay > 0 else base_delay
            ))
    
    def _parse_audio_data(self, f):
        """Parse audio data section"""
        format = struct.unpack('<B', f.read(1))[0]
        sample_rate = struct.unpack('<I', f.read(4))[0]
        channels = struct.unpack('<B', f.read(1))[0]
        data_size = struct.unpack('<I', f.read(4))[0]
        audio_data = f.read(data_size)
        
        self.audio_stream = AudioStream(
            format=format,
            sample_rate=sample_rate,
            channels=channels,
            data=audio_data
        )
    
    def _parse_extended_metadata(self, f):
        """Parse extended metadata section"""
        section_count = struct.unpack('<H', f.read(2))[0]
        
        for _ in range(section_count):
            section_type = struct.unpack('<B', f.read(1))[0]
            section_size = struct.unpack('<I', f.read(4))[0]
            section_data = f.read(section_size)
            
            # Store raw section data - can be parsed by specific handlers
            self.extended_metadata[section_type] = section_data

@dataclass
class ClientSession:
    """Represents a client session with state"""
    session_id: bytes
    client_socket: socket.socket
    client_address: Tuple[str, int]
    sequence: int = 0
    current_page: str = "index"
    input_values: Dict[int, str] = None
    last_activity: float = time.time()
    user_agent: str = "Unknown"
    
    def __post_init__(self):
        self.input_values = {}
    
    def is_active(self) -> bool:
        """Check if session is still active"""
        return (time.time() - self.last_activity) < MAX_SESSION_AGE
    
    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = time.time()

class PixnetServer:
    """PIXNET protocol server with complete feature set"""
    
    def __init__(self, host: str = 'localhost', port: int = DEFAULT_PORT, 
                 content_dir: str = 'content', max_connections: int = 100):
        self.host = host
        self.port = port
        self.content_dir = content_dir
        self.max_connections = max_connections
        self.sessions: Dict[bytes, ClientSession] = {}
        self.running = False
        self.server_socket = None
        self.pxnt_files: Dict[str, PXNTFile] = {}
        self.stats = {
            'connections': 0,
            'pages_served': 0,
            'errors': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }
        
        # Initialize content
        self._initialize_content()
        
        # Start session cleanup thread
        self.cleanup_thread = threading.Thread(target=self._session_cleanup_loop, daemon=True)
        self.cleanup_thread.start()
    
    def _initialize_content(self):
        """Initialize content directory and load PXNT files"""
        try:
            if not os.path.exists(self.content_dir):
                logger.info(f"Creating content directory: {self.content_dir}")
                os.makedirs(self.content_dir, exist_ok=True)
                self._create_sample_content()
            
            self._load_pxnt_files()
            
            if not self.pxnt_files:
                logger.warning("No PXNT files found, creating samples")
                self._create_sample_content()
                self._load_pxnt_files()
                
            if "index" not in self.pxnt_files:
                logger.error("No index page found, creating default")
                self._create_sample_index()
                self._load_pxnt_files()
                
        except Exception as e:
            logger.error(f"Content initialization failed: {str(e)}")
            raise
    
    def _load_pxnt_files(self):
        """Load all PXNT files from content directory"""
        pxnt_pattern = os.path.join(self.content_dir, "*.pxnt")
        
        for filepath in glob.glob(pxnt_pattern):
            try:
                filename = os.path.basename(filepath)
                page_name = os.path.splitext(filename)[0]
                self.pxnt_files[page_name] = PXNTFile(filepath)
                logger.info(f"Loaded page: {page_name}")
            except Exception as e:
                logger.error(f"Failed to load {filepath}: {str(e)}")
                if page_name == "index":
                    logger.warning("Critical: Failed to load index page")
                    self._create_sample_index()
                    self.pxnt_files["index"] = PXNTFile(os.path.join(self.content_dir, "index.pxnt"))
    
    def _create_sample_content(self):
        """Create sample content for demonstration"""
        logger.info("Creating sample content...")
        
        # Create index page
        self._create_sample_page("index", "Welcome to PIXNET", [
            {"text": "Home", "x": 50, "y": 100, "w": 80, "h": 30, "behavior": BehaviorType.NAVIGATE, "target": "index"},
            {"text": "About", "x": 150, "y": 100, "w": 80, "h": 30, "behavior": BehaviorType.NAVIGATE, "target": "about"},
            {"text": "Demo", "x": 250, "y": 100, "w": 80, "h": 30, "behavior": BehaviorType.EMIT_EVENT, "event": "demo_click"},
        ])
        
        # Create about page
        self._create_sample_page("about", "About PIXNET", [
            {"text": "Back", "x": 50, "y": 50, "w": 60, "h": 30, "behavior": BehaviorType.NAVIGATE, "target": "index"},
        ])
    
    def _create_sample_index(self):
        """Create a minimal index page"""
        self._create_sample_page("index", "PIXNET Server", [
            {"text": "Home", "x": 50, "y": 100, "w": 80, "h": 30, "behavior": BehaviorType.NAVIGATE, "target": "index"},
        ])
    
    def _create_sample_page(self, name: str, title: str, elements: List[Dict]):
        """Create a sample PXNT page"""
        width, height = 640, 480
        filepath = os.path.join(self.content_dir, f"{name}.pxnt")
        
        # Create pixel data (RGBA8)
        pixels = bytearray(width * height * 4)
        category_map = bytearray(width * height * 2)
        
        # Background gradient
        for y in range(height):
            for x in range(width):
                idx = (y * width + x) * 4
                if name == "index":
                    r, g, b = 50, 100 + int((y / height) * 100), 200
                elif name == "about":
                    r, g, b = 100 + int((y / height) * 100), 150, 100
                else:
                    r, g, b = 150, 100, 150 + int((y / height) * 100)
                pixels[idx:idx+4] = [r, g, b, 255]
        
        # Title bar
        for y in range(60):
            for x in range(width):
                idx = (y * width + x) * 4
                pixels[idx:idx+4] = [30, 30, 60, 255]
        
        # Create elements
        categories = []
        category_id = 1
        
        for element in elements:
            x, y, w, h = element["x"], element["y"], element["w"], element["h"]
            
            # Draw element
            for ey in range(h):
                for ex in range(w):
                    px, py = x + ex, y + ey
                    if px < width and py < height:
                        # Element background
                        pixel_idx = (py * width + px) * 4
                        pixels[pixel_idx:pixel_idx+4] = [200, 200, 255, 255]
                        
                        # Set category map
                        cat_idx = (py * width + px) * 2
                        category_map[cat_idx:cat_idx+2] = struct.pack('<H', category_id)
            
            # Create behavior data
            behavior_data = self._create_behavior_data(
                element["behavior"],
                element.get("target"),
                element.get("event")
            )
            
            categories.append(Category(
                id=category_id,
                name=f"{element['text'].lower()}_{category_id}",
                behavior_id=element["behavior"],
                priority=128,
                behavior_data=behavior_data
            ))
            
            category_id += 1
        
        # Write PXNT file
        self._write_pxnt_file(filepath, title, width, height, pixels, category_map, categories)
        logger.info(f"Created sample page: {name}")
    
    def _create_behavior_data(self, behavior_type: BehaviorType, target: Optional[str] = None, 
                            event_name: Optional[str] = None) -> bytes:
        """Create behavior data based on type"""
        if behavior_type == BehaviorType.NAVIGATE and target:
            return self._create_nav_behavior(target)
        elif behavior_type == BehaviorType.EMIT_EVENT and event_name:
            return self._create_event_behavior(event_name)
        else:
            return b''  # Default empty behavior
    
    def _create_nav_behavior(self, target: str) -> bytes:
        """Create navigation behavior data"""
        data = bytearray()
        data.extend(struct.pack('<B', len(target)))
        data.extend(target.encode('utf-8'))
        data.extend(struct.pack('<H', 100))  # Debounce time (ms)
        return bytes(data)
    
    def _create_event_behavior(self, event_name: str) -> bytes:
        """Create event behavior data"""
        data = bytearray()
        data.extend(struct.pack('<B', len(event_name)))
        data.extend(event_name.encode('utf-8'))
        data.extend(struct.pack('<B', 0))  # Event type (0=click)
        data.extend(struct.pack('<H', 100))  # Debounce time (ms)
        return bytes(data)
    
    def _write_pxnt_file(self, filepath: str, title: str, width: int, height: int,
                        pixels: bytes, category_map: bytes, categories: List[Category]):
        """Write a PXNT file to disk"""
        with open(filepath, 'wb') as f:
            # File header
            header = struct.pack('<4sHHIIIIHHBBH',
                b'PXNT',           # Magic
                1,                 # Version
                0,                 # Flags
                0,                 # File size (placeholder)
                int(time.time()),  # Created
                int(time.time()),  # Modified
                0,                 # CRC32 (placeholder)
                width,             # Width
                height,            # Height
                0,                 # RGBA8 format
                0,                 # No compression
                0                  # Reserved
            )
            f.write(header)
            
            # Page metadata
            title_bytes = title.encode('utf-8')
            f.write(struct.pack('<H', len(title_bytes)))  # Title length
            f.write(title_bytes)                          # Title
            f.write(struct.pack('<B', 0))                 # No author
            f.write(struct.pack('<H', 0))                 # No description
            f.write(struct.pack('<H', 0))                 # No URL
            f.write(struct.pack('<B', 0))                 # No keywords
            f.write(struct.pack('<B', 0))                 # No custom fields
            
            # Pixel data
            f.write(pixels)
            
            # Category map
            f.write(category_map)
            
            # Category definitions
            f.write(struct.pack('<H', len(categories)))   # Category count
            for cat in categories:
                name_bytes = cat.name.encode('utf-8')
                f.write(struct.pack('<H', cat.id))                    # ID
                f.write(struct.pack('<B', cat.behavior_id))           # Behavior ID
                f.write(struct.pack('<B', cat.priority))              # Priority
                f.write(struct.pack('<H', len(name_bytes)))           # Name length
                f.write(struct.pack('<H', len(cat.behavior_data)))    # Data length
                f.write(name_bytes)                                   # Name
                f.write(cat.behavior_data)                            # Behavior data
            
            # Footer with file size and CRC32
            file_size = f.tell()
            f.seek(6)  # Update file size in header
            f.write(struct.pack('<I', file_size))
            f.seek(0, 2)  # Seek to end
            
            # Simple footer
            footer = struct.pack('<4sIII', b'TNXP', 0, 0, 0)
            f.write(footer)
    
    def start(self):
        """Start the server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.max_connections)
        self.running = True
        
        logger.info(f"PIXNET Server started on {self.host}:{self.port}")
        logger.info(f"Available pages: {list(self.pxnt_files.keys())}")
        
        try:
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    client_socket.settimeout(10.0)  # Initial handshake timeout
                    
                    logger.info(f"New connection from {address[0]}:{address[1]}")
                    self.stats['connections'] += 1
                    
                    thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address),
                        daemon=True
                    )
                    thread.start()
                    
                except socket.timeout:
                    continue
                except OSError as e:
                    if self.running:
                        logger.error(f"Accept error: {str(e)}")
                    continue
        
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the server gracefully"""
        self.running = False
        
        # Close all client connections
        for session in list(self.sessions.values()):
            try:
                self._send_error(session.client_socket, ErrorCode.SERVER_ERROR, "Server shutting down")
                session.client_socket.close()
            except:
                pass
        
        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Print final statistics
        self._print_stats()
        logger.info("Server stopped")
    
    def _handle_client(self, client_socket: socket.socket, address: Tuple[str, int]):
        """Handle a client connection"""
        session = None
        
        try:
            # Handle handshake
            session = self._handle_handshake(client_socket, address)
            if not session:
                return
            
            # Send initial page
            self._send_page(session, "index")
            
            # Main client loop
            while self.running and session.is_active():
                try:
                    # Read message header
                    magic = client_socket.recv(6)
                    if not magic:
                        break  # Connection closed
                    
                    if len(magic) != 6:
                        logger.warning(f"Invalid message header from {address}")
                        break
                    
                    session.update_activity()
                    
                    # Handle different message types
                    if magic == MAGIC_EVENT:
                        self._handle_event(session)
                    elif magic == MAGIC_INPUT:
                        self._handle_input(session)
                    elif magic == MAGIC_PING:
                        self._handle_ping(session)
                    elif magic == MAGIC_BYE:
                        logger.info(f"Client {address} requested disconnect")
                        break
                    else:
                        logger.warning(f"Unknown message type: {magic.hex()} from {address}")
                        break
                
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"Error handling client {address}: {str(e)}")
                    break
        
        except Exception as e:
            logger.error(f"Client handler error for {address}: {str(e)}")
        finally:
            if session and session.session_id in self.sessions:
                del self.sessions[session.session_id]
            client_socket.close()
            logger.info(f"Client disconnected: {address}")
    
    def _handle_handshake(self, client_socket: socket.socket, address: Tuple[str, int]) -> Optional[ClientSession]:
        """Handle client handshake"""
        try:
            # Read handshake
            data = client_socket.recv(1024)
            if len(data) < 10:
                self._send_error(client_socket, ErrorCode.PROTOCOL_ERROR, "Invalid handshake")
                return None
            
            magic = data[:6]
            if magic != MAGIC_HANDSHAKE:
                self._send_error(client_socket, ErrorCode.PROTOCOL_ERROR, "Invalid handshake magic")
                return None
            
            version = data[6]
            if version != PROTOCOL_VERSION:
                self._send_error(client_socket, ErrorCode.UNSUPPORTED_VERSION, f"Unsupported version: {version}")
                return None
            
            capabilities = struct.unpack('>H', data[7:9])[0]
            user_agent_len = data[9]
            user_agent = data[10:10+user_agent_len].decode('ascii', errors='ignore')
            
            logger.info(f"Handshake from {address}: version={version}, capabilities={capabilities}, user-agent={user_agent}")
            
            # Generate session ID
            session_id = secrets.token_bytes(8)
            
            # Send acknowledgment
            response = MAGIC_ACK
            response += struct.pack('B', PROTOCOL_VERSION)  # Version
            response += session_id  # Session ID
            response += struct.pack('>H', 0x01)  # Server capabilities (compression)
            
            client_socket.send(response)
            
            # Create and store session
            session = ClientSession(
                session_id=session_id,
                client_socket=client_socket,
                client_address=address,
                user_agent=user_agent
            )
            self.sessions[session_id] = session
            
            return session
            
        except Exception as e:
            logger.error(f"Handshake error with {address}: {str(e)}")
            try:
                self._send_error(client_socket, ErrorCode.PROTOCOL_ERROR, "Handshake failed")
            except:
                pass
            return None
    
    def _send_page(self, session: ClientSession, page_name: str):
        """Send a PXNT page to the client"""
        if page_name not in self.pxnt_files:
            logger.warning(f"Page not found: {page_name}")
            page_name = "index"  # Fallback to index
        
        pxnt_file = self.pxnt_files[page_name]
        
        # Create frame header
        header = MAGIC_PIXNET
        header += struct.pack('B', FrameType.FULL)  # Frame type
        header += struct.pack('>I', session.sequence)  # Sequence
        header += struct.pack('>Q', int(time.time() * 1000000))  # Timestamp
        header += struct.pack('>H', 0x01)  # Flags (compression enabled)
        header += struct.pack('B', PROTOCOL_VERSION)  # Version
        header += struct.pack('>H', pxnt_file.header['width'])  # Width
        header += struct.pack('>H', pxnt_file.header['height'])  # Height
        header += struct.pack('B', 0)  # Format (RGBA8)
        
        # Compress pixel data
        compressed_pixels = zlib.compress(pxnt_file.pixels)
        
        # Calculate checksum (simplified)
        checksum = len(compressed_pixels) + len(pxnt_file.category_map)
        header += struct.pack('>I', checksum)
        
        # Serialize categories
        category_data = bytearray()
        category_data.extend(struct.pack('>H', len(pxnt_file.categories)))  # Category count
        
        for category in pxnt_file.categories:
            name_bytes = category.name.encode('ascii')
            cat_data = struct.pack('>H', category.id)  # ID
            cat_data += struct.pack('B', len(name_bytes))  # Name length
            cat_data += name_bytes  # Name
            cat_data += struct.pack('B', category.behavior_id)  # Behavior ID
            cat_data += struct.pack('B', category.priority)  # Priority
            cat_data += struct.pack('>H', len(category.behavior_data))  # Behavior data length
            cat_data += category.behavior_data  # Behavior data
            category_data.extend(cat_data)
        
        # Send frame
        try:
            session.client_socket.send(header)
            session.client_socket.send(compressed_pixels)
            session.client_socket.send(pxnt_file.category_map)
            session.client_socket.send(category_data)
            
            session.sequence += 1
            session.current_page = page_name
            self.stats['pages_served'] += 1
            self.stats['bytes_sent'] += len(header) + len(compressed_pixels) + len(pxnt_file.category_map) + len(category_data)
            
            logger.debug(f"Sent page '{page_name}' to {session.client_address}")
            
        except Exception as e:
            logger.error(f"Error sending page to {session.client_address}: {str(e)}")
            raise
    
    def _handle_event(self, session: ClientSession):
        """Handle an event message from client"""
        try:
            # Read event header (after magic)
            header = session.client_socket.recv(23)
            if len(header) < 23:
                raise ValueError("Incomplete event header")
            
            session_id = header[:8]
            if session_id != session.session_id:
                raise ValueError("Invalid session ID")
            
            sequence = struct.unpack('>I', header[8:12])[0]
            zone_id = struct.unpack('>H', header[12:14])[0]
            event_type = header[14]
            timestamp = struct.unpack('>Q', header[15:23])[0]
            
            # Read event name length
            name_len_data = session.client_socket.recv(1)
            if len(name_len_data) != 1:
                raise ValueError("Missing event name length")
            
            name_len = name_len_data[0]
            
            # Read event name
            event_name = session.client_socket.recv(name_len).decode('ascii', errors='ignore')
            
            # Read mouse position (optional)
            mouse_data = session.client_socket.recv(4)
            if len(mouse_data) == 4:
                mouse_x, mouse_y = struct.unpack('>HH', mouse_data)
            else:
                mouse_x, mouse_y = 0, 0
            
            logger.debug(f"Event from {session.client_address}: {event_name} (zone {zone_id}) at ({mouse_x}, {mouse_y})")
            
            # Handle navigation events
            if event_name.startswith("nav_"):
                target_page = event_name[4:]
                if target_page in self.pxnt_files:
                    logger.info(f"Navigation from {session.client_address}: {session.current_page} -> {target_page}")
                    self._send_page(session, target_page)
                else:
                    logger.warning(f"Invalid navigation target from {session.client_address}: {target_page}")
            
            # Update activity
            session.update_activity()
            
        except Exception as e:
            logger.error(f"Error handling event from {session.client_address}: {str(e)}")
            self.stats['errors'] += 1
            raise
    
    def _handle_input(self, session: ClientSession):
        """Handle an input message from client"""
        try:
            # Read input header (after magic)
            header = session.client_socket.recv(18)
            if len(header) < 18:
                raise ValueError("Incomplete input header")
            
            session_id = header[:8]
            if session_id != session.session_id:
                raise ValueError("Invalid session ID")
            
            sequence = struct.unpack('>I', header[8:12])[0]
            zone_id = struct.unpack('>H', header[12:14])[0]
            input_type = header[14]
            validation_status = header[15]
            payload_length = struct.unpack('>H', header[16:18])[0]
            
            # Read payload
            payload = session.client_socket.recv(payload_length).decode('utf-8', errors='ignore')
            
            # Store input value
            session.input_values[zone_id] = payload
            session.update_activity()
            
            logger.debug(f"Input from {session.client_address}: zone {zone_id} = '{payload}'")
            
        except Exception as e:
            logger.error(f"Error handling input from {session.client_address}: {str(e)}")
            self.stats['errors'] += 1
            raise
    
    def _handle_ping(self, session: ClientSession):
        """Handle a ping message from client"""
        try:
            # Read ping data (after magic)
            ping_data = session.client_socket.recv(16)
            if len(ping_data) < 16:
                raise ValueError("Incomplete ping data")
            
            session_id = ping_data[:8]
            timestamp = ping_data[8:16]
            
            if session_id != session.session_id:
                raise ValueError("Invalid session ID")
            
            # Send pong response
            pong = MAGIC_PONG + session_id + timestamp
            session.client_socket.send(pong)
            session.update_activity()
            
            logger.debug(f"Ping from {session.client_address}")
            
        except Exception as e:
            logger.error(f"Error handling ping from {session.client_address}: {str(e)}")
            self.stats['errors'] += 1
            raise
    
    def _send_error(self, client_socket: socket.socket, error_code: ErrorCode, message: str):
        """Send an error message to client"""
        try:
            message_bytes = message.encode('utf-8')
            error_msg = MAGIC_ERROR
            error_msg += struct.pack('>H', error_code)
            error_msg += struct.pack('>H', len(message_bytes))
            error_msg += message_bytes
            
            client_socket.send(error_msg)
            self.stats['errors'] += 1
        except:
            pass
    
    def _session_cleanup_loop(self):
        """Background thread to clean up inactive sessions"""
        while self.running:
            time.sleep(60)  # Run once per minute
            self._cleanup_sessions()
    
    def _cleanup_sessions(self):
        """Clean up inactive sessions"""
        inactive_sessions = [
            session_id for session_id, session in self.sessions.items()
            if not session.is_active()
        ]
        
        for session_id in inactive_sessions:
            try:
                session = self.sessions[session_id]
                logger.info(f"Cleaning up inactive session from {session.client_address}")
                session.client_socket.close()
                del self.sessions[session_id]
            except:
                pass
    
    def _print_stats(self):
        """Print server statistics"""
        logger.info("\nServer Statistics:")
        logger.info(f"Active sessions: {len(self.sessions)}")
        logger.info(f"Total connections: {self.stats['connections']}")
        logger.info(f"Pages served: {self.stats['pages_served']}")
        logger.info(f"Errors encountered: {self.stats['errors']}")
        logger.info(f"Bytes sent: {self.stats['bytes_sent']}")
        logger.info(f"Bytes received: {self.stats['bytes_received']}")

def main():
    """Main entry point for the PIXNET server"""
    parser = argparse.ArgumentParser(
        description='PIXNET Protocol Server with PXNT File Support',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--host', default='localhost', 
                       help='Host interface to bind to')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                       help='Port to listen on')
    parser.add_argument('--content', default='content',
                       help='Directory containing PXNT files')
    parser.add_argument('--max-conn', type=int, default=100,
                       help='Maximum simultaneous connections')
    
    args = parser.parse_args()
    
    try:
        server = PixnetServer(
            host=args.host,
            port=args.port,
            content_dir=args.content,
            max_connections=args.max_conn
        )
        server.start()
    except Exception as e:
        logger.critical(f"Server failed: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())