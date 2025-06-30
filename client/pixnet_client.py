#!/usr/bin/env python3
"""
PIXNET Protocol Client
A simple client implementation for the PIXNET graphical web protocol
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import socket
import struct
import threading
import time
import zlib
from PIL import Image, ImageTk
import io
from typing import Dict, Tuple, Optional, List
from dataclasses import dataclass
from enum import IntEnum

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
class Category:
    id: int
    name: str
    behavior_id: int
    priority: int
    behavior_data: bytes

@dataclass
class FrameData:
    sequence: int
    timestamp: int
    width: int
    height: int
    pixels: bytes
    categories: Dict[int, Category]
    category_map: bytes

class PIXNETClient:
    def __init__(self):
        self.socket = None
        self.session_id = None
        self.connected = False
        self.current_frame = None
        self.sequence_counter = 0
        
    def connect(self, host: str, port: int = 7621) -> bool:
        """Connect to PIXNET server and perform handshake"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10.0)
            self.socket.connect((host, port))
            
            # Send handshake
            handshake = struct.pack('>6sB2H8s',
                b'PIXHND',  # Magic
                1,          # Version
                0x01,       # Capabilities (compression)
                10,         # User-agent length
                b'PyPixnet\x00\x00'  # User-agent (padded)
            )
            self.socket.send(handshake)
            
            # Receive acknowledgment
            response = self.socket.recv(17)
            if len(response) < 17:
                return False
                
            magic, version, session_id, server_caps = struct.unpack('>6sB8s2s', response)
            
            if magic != b'PIXACK':
                return False
                
            self.session_id = session_id
            self.connected = True
            return True
            
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from server"""
        if self.socket:
            try:
                # Send termination message
                if self.session_id:
                    goodbye = struct.pack('>6s8sBB',
                        b'PIXBYE',
                        self.session_id,
                        0,  # Reason code
                        0   # Reason length
                    )
                    self.socket.send(goodbye)
                self.socket.close()
            except:
                pass
            finally:
                self.socket = None
                self.connected = False
                self.session_id = None
    
    def send_event(self, zone_id: int, event_type: int, event_name: str, 
                   mouse_x: int = 0, mouse_y: int = 0, payload: bytes = b''):
        """Send an event to the server"""
        if not self.connected:
            return
            
        try:
            self.sequence_counter += 1
            timestamp = int(time.time() * 1000000)  # microseconds
            
            event_name_bytes = event_name.encode('ascii')
            message = struct.pack('>6s8sLHBQ2HB',
                b'PIXEVT',           # Magic
                self.session_id,     # Session ID
                self.sequence_counter, # Sequence
                zone_id,             # Zone ID
                event_type,          # Event type
                timestamp,           # Timestamp
                mouse_x,             # Mouse X
                mouse_y,             # Mouse Y
                0                    # Modifier keys
            )
            
            message += struct.pack('>BH',
                len(event_name_bytes),
                len(payload)
            )
            message += event_name_bytes + payload
            
            self.socket.send(message)
            
        except Exception as e:
            print(f"Failed to send event: {e}")
    
    def receive_frame(self) -> Optional[FrameData]:
        """Receive and parse a frame from server"""
        if not self.connected:
            return None
            
        try:
            # Read frame header - let's calculate the correct size
            # Magic(6) + FrameType(1) + Sequence(4) + Timestamp(8) + Flags(2) + Version(1) + Width(2) + Height(2) + Format(1) + Checksum(4) = 31 bytes
            header_data = self._recv_exact(31)
            if not header_data:
                return None
                
            print(f"Received header: {len(header_data)} bytes")
            
            # Unpack header fields according to protocol spec
            # Format: Magic(6) + FrameType(1) + Sequence(4) + Timestamp(8) + Flags(2) + Version(1) + Width(2) + Height(2) + Format(1) + Checksum(4)
            header = struct.unpack('>6sBLQHB2HB4s', header_data)
            magic, frame_type, sequence, timestamp, flags, version, width, height, format_type, checksum_bytes = header
            
            if magic != b'PIXNET':
                print(f"Invalid frame magic: {magic}")
                return None
                
            print(f"Frame: {width}x{height}, type={frame_type}, seq={sequence}")
            
            checksum = struct.unpack('>L', checksum_bytes)[0]
            
            # Calculate pixel data size
            bytes_per_pixel = 4 if format_type == 0 else 4  # RGBA8
            pixel_data_size = width * height * bytes_per_pixel
            category_map_size = width * height * 2
            
            print(f"Expecting {pixel_data_size} pixel bytes, {category_map_size} category bytes")
            
            # Read pixel data
            pixel_data = self._recv_exact(pixel_data_size)
            if not pixel_data:
                print("Failed to receive pixel data")
                return None
                
            # Decompress if needed
            if flags & 0x01:  # Compression flag
                print("Decompressing pixel data")
                pixel_data = zlib.decompress(pixel_data)
            
            # Read category map
            category_map = self._recv_exact(category_map_size)
            if not category_map:
                print("Failed to receive category map")
                return None
            
            # Read category definitions
            categories = self._read_categories()
            print(f"Received {len(categories)} categories")
            
            return FrameData(
                sequence=sequence,
                timestamp=timestamp,
                width=width,
                height=height,
                pixels=pixel_data,
                categories=categories,
                category_map=category_map
            )
            
        except struct.error as e:
            print(f"Struct unpack error: {e}")
            print(f"Header data length: {len(header_data) if 'header_data' in locals() else 'unknown'}")
            return None
        except Exception as e:
            print(f"Failed to receive frame: {e}")
            return None
    
    def _recv_exact(self, size: int) -> Optional[bytes]:
        """Receive exactly 'size' bytes from socket"""
        data = b''
        while len(data) < size:
            try:
                chunk = self.socket.recv(size - len(data))
                if not chunk:
                    print(f"Socket closed while expecting {size} bytes, got {len(data)}")
                    return None
                data += chunk
            except socket.timeout:
                print(f"Timeout while receiving {size} bytes, got {len(data)}")
                return None
            except Exception as e:
                print(f"Error receiving {size} bytes: {e}")
                return None
        return data
    
    def _read_categories(self) -> Dict[int, Category]:
        """Read category definitions from socket"""
        categories = {}
        try:
            count_data = self._recv_exact(2)
            if not count_data:
                return categories
                
            count = struct.unpack('>H', count_data)[0]
            
            for _ in range(count):
                # Read category header: ID(2) + NameLength(1) + Name + BehaviorID(1) + Priority(1) + BehaviorDataLength(2) + BehaviorData
                cat_id_data = self._recv_exact(2)
                if not cat_id_data:
                    break
                cat_id = struct.unpack('>H', cat_id_data)[0]
                
                name_len_data = self._recv_exact(1)
                if not name_len_data:
                    break
                name_len = struct.unpack('>B', name_len_data)[0]
                
                # Read category name
                name_data = self._recv_exact(name_len)
                if not name_data:
                    break
                name = name_data.decode('ascii')
                
                # Read behavior ID and priority
                behavior_data = self._recv_exact(2)
                if not behavior_data:
                    break
                behavior_id, priority = struct.unpack('>BB', behavior_data)
                
                # Read behavior data length
                data_len_data = self._recv_exact(2)
                if not data_len_data:
                    break
                data_len = struct.unpack('>H', data_len_data)[0]
                
                # Read behavior data
                behavior_data = self._recv_exact(data_len)
                if not behavior_data:
                    break
                
                categories[cat_id] = Category(
                    id=cat_id,
                    name=name,
                    behavior_id=behavior_id,
                    priority=priority,
                    behavior_data=behavior_data
                )
                
        except Exception as e:
            print(f"Failed to read categories: {e}")
            
        return categories

class PIXNETClientGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("PIXNET Client")
        self.root.geometry("1000x700")
        
        self.client = PIXNETClient()
        self.receive_thread = None
        self.running = False
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Top frame for connection controls
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Connection controls
        ttk.Label(top_frame, text="Server:").pack(side=tk.LEFT)
        self.server_entry = ttk.Entry(top_frame, width=20)
        self.server_entry.pack(side=tk.LEFT, padx=5)
        self.server_entry.insert(0, "localhost")
        
        ttk.Label(top_frame, text="Port:").pack(side=tk.LEFT)
        self.port_entry = ttk.Entry(top_frame, width=8)
        self.port_entry.pack(side=tk.LEFT, padx=5)
        self.port_entry.insert(0, "7621")
        
        self.connect_btn = ttk.Button(top_frame, text="Connect", command=self.connect)
        self.connect_btn.pack(side=tk.LEFT, padx=5)
        
        self.disconnect_btn = ttk.Button(top_frame, text="Disconnect", command=self.disconnect, state=tk.DISABLED)
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)
        
        # Status label
        self.status_label = ttk.Label(top_frame, text="Disconnected", foreground="red")
        self.status_label.pack(side=tk.RIGHT, padx=5)
        
        # Main content area
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas for PIXNET content
        canvas_frame = ttk.LabelFrame(main_frame, text="PIXNET Display")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", width=600, height=400)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Motion>", self.on_canvas_motion)
        
        # Info panel
        info_frame = ttk.LabelFrame(main_frame, text="Information")
        info_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        
        # Frame info
        self.info_text = tk.Text(info_frame, width=30, height=15, wrap=tk.WORD)
        info_scroll = ttk.Scrollbar(info_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scroll.set)
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        info_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Test controls
        test_frame = ttk.LabelFrame(main_frame, text="Test Controls")
        test_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        
        ttk.Button(test_frame, text="Send Test Event", command=self.send_test_event).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Button(test_frame, text="Request Page", command=self.request_page).pack(side=tk.LEFT, padx=5, pady=5)
        
    def connect(self):
        """Connect to PIXNET server"""
        server = self.server_entry.get().strip()
        try:
            port = int(self.port_entry.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid port number")
            return
            
        if not server:
            messagebox.showerror("Error", "Please enter a server address")
            return
            
        self.status_label.config(text="Connecting...", foreground="orange")
        self.root.update()
        
        if self.client.connect(server, port):
            self.status_label.config(text="Connected", foreground="green")
            self.connect_btn.config(state=tk.DISABLED)
            self.disconnect_btn.config(state=tk.NORMAL)
            
            # Start receive thread
            self.running = True
            self.receive_thread = threading.Thread(target=self.receive_loop, daemon=True)
            self.receive_thread.start()
            
            # Request initial page
            self.request_page()
            
        else:
            self.status_label.config(text="Connection Failed", foreground="red")
            messagebox.showerror("Error", f"Failed to connect to {server}:{port}")
    
    def disconnect(self):
        """Disconnect from server"""
        self.running = False
        self.client.disconnect()
        
        self.status_label.config(text="Disconnected", foreground="red")
        self.connect_btn.config(state=tk.NORMAL)
        self.disconnect_btn.config(state=tk.DISABLED)
        
        self.canvas.delete("all")
        self.info_text.delete(1.0, tk.END)
    
    def receive_loop(self):
        """Background thread for receiving frames"""
        while self.running and self.client.connected:
            try:
                frame = self.client.receive_frame()
                if frame:
                    self.root.after(0, self.update_display, frame)
                else:
                    time.sleep(0.1)  # Brief pause if no frame received
            except Exception as e:
                print(f"Error in receive loop: {e}")
                break
    
    def update_display(self, frame: FrameData):
        """Update the display with new frame data"""
        try:
            # Convert pixel data to PIL Image
            image = Image.frombytes('RGBA', (frame.width, frame.height), frame.pixels)
            
            # Scale to fit canvas
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width > 1 and canvas_height > 1:  # Canvas is initialized
                scale_x = canvas_width / frame.width
                scale_y = canvas_height / frame.height
                scale = min(scale_x, scale_y, 1.0)  # Don't upscale
                
                new_width = int(frame.width * scale)
                new_height = int(frame.height * scale)
                
                if scale < 1.0:
                    image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Display image
            photo = ImageTk.PhotoImage(image)
            self.canvas.delete("all")
            self.canvas.create_image(canvas_width//2, canvas_height//2, image=photo, anchor=tk.CENTER)
            self.canvas.image = photo  # Keep reference
            
            # Store current frame for interaction
            self.client.current_frame = frame
            
            # Update info panel
            self.update_info_panel(frame)
            
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def update_info_panel(self, frame: FrameData):
        """Update the information panel"""
        self.info_text.delete(1.0, tk.END)
        
        info = f"Frame #{frame.sequence}\n"
        info += f"Size: {frame.width}x{frame.height}\n"
        info += f"Timestamp: {frame.timestamp}\n\n"
        
        info += f"Categories ({len(frame.categories)}):\n"
        for cat_id, category in frame.categories.items():
            behavior_name = BehaviorType(category.behavior_id).name
            info += f"  {cat_id}: {category.name} ({behavior_name})\n"
        
        self.info_text.insert(1.0, info)
    
    def on_canvas_click(self, event):
        """Handle canvas click events"""
        if not self.client.current_frame:
            return
            
        # Convert canvas coordinates to frame coordinates
        frame = self.client.current_frame
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            return
            
        scale_x = canvas_width / frame.width
        scale_y = canvas_height / frame.height
        scale = min(scale_x, scale_y, 1.0)
        
        # Calculate offset for centered image
        scaled_width = int(frame.width * scale)
        scaled_height = int(frame.height * scale)
        offset_x = (canvas_width - scaled_width) // 2
        offset_y = (canvas_height - scaled_height) // 2
        
        # Convert to frame coordinates
        frame_x = int((event.x - offset_x) / scale)
        frame_y = int((event.y - offset_y) / scale)
        
        if 0 <= frame_x < frame.width and 0 <= frame_y < frame.height:
            # Get category at clicked position
            category_index = (frame_y * frame.width + frame_x) * 2
            if category_index < len(frame.category_map):
                category_id = struct.unpack('>H', frame.category_map[category_index:category_index+2])[0]
                
                if category_id in frame.categories:
                    category = frame.categories[category_id]
                    print(f"Clicked category {category_id}: {category.name}")
                    
                    # Send appropriate event based on behavior
                    if category.behavior_id == BehaviorType.EMIT_EVENT:
                        self.client.send_event(category_id, 0, "click", frame_x, frame_y)
                    elif category.behavior_id == BehaviorType.NAVIGATE:
                        self.client.send_event(category_id, 0, "navigate", frame_x, frame_y)
    
    def on_canvas_motion(self, event):
        """Handle canvas motion events for hover effects"""
        # Could implement hover effects here
        pass
    
    def send_test_event(self):
        """Send a test event to the server"""
        if self.client.connected:
            self.client.send_event(0, 0, "test_event", 100, 100, b"Hello from client!")
    
    def request_page(self):
        """Request the main page from server"""
        if self.client.connected:
            self.client.send_event(0, 0, "page_request", 0, 0, b"/")
    
    def run(self):
        """Start the GUI main loop"""
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
    
    def on_closing(self):
        """Handle application closing"""
        self.running = False
        self.client.disconnect()
        self.root.destroy()

if __name__ == "__main__":
    # Check if PIL is available
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("Error: This client requires Pillow (PIL) for image handling.")
        print("Install it with: pip install Pillow")
        exit(1)
    
    client = PIXNETClientGUI()
    client.run()