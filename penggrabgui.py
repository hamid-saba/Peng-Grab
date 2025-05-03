#pyinstaller --onefile --windowed --icon=icon.ico --add-data="icon.ico;." .\penggrabgui.py  --run this to create the exe (do not remove. this is for me))


# Add this at the VERY START of your script (first lines)
import os
if os.name == 'nt':  # Windows
    import ctypes
    # This makes the taskbar icon work properly
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PengGrab.1.2')

import yt_dlp
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import requests
from io import BytesIO
import threading
import os
import re
from pathlib import Path
from queue import Queue
import time
import subprocess
import json
import sys

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller bundle """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

icon_path = resource_path('icon.ico')

# Global variables
SCALING_FACTOR = 1.0
CURRENT_THEME = "light"
FONT_SIZES = {
    'small': 8,
    'medium': 12,
    'large': 16
}

APP_VERSION = "v1.2.0"

THEMES = {
    "light": {
        "bg": "#f0f0f0",
        "fg": "#000000",
        "button_bg": "#e0e0e0",
        "button_fg": "#000000",
        "entry_bg": "#ffffff",
        "entry_fg": "#000000",
        "highlight": "#4a90d9",
        "progress": "#4a90d9",
        "button_radius": 0,
        "combobox_font": ("Segoe UI", 16),  # Base font size (will be scaled)
        "font": ("Segoe UI", 10),
        "button_font": ("Segoe UI", 10, "normal")
    },
    "dark": {
        "bg": "#2d2d2d",
        "fg": "#ffffff",
        "button_bg": "#3d3d3d",
        "button_fg": "#ffffff",
        "entry_bg": "#1e1e1e",
        "entry_fg": "#ffffff",
        "highlight": "#5a9de9",
        "progress": "#5a9de9",
        "button_radius": 5,
        "combobox_font": ("Segoe UI", 16),
        "font": ("Segoe UI", 10),
        "button_font": ("Segoe UI", 10, "bold")
    },
    "orange": {
        "bg": "#fff0e0",
        "fg": "#333333",
        "button_bg": "#ffb366",
        "button_fg": "#333333",
        "entry_bg": "#ffffff",
        "entry_fg": "#333333",
        "highlight": "#ff8000",
        "progress": "#ff8000",
        "button_radius": 8,
        "combobox_font": ("Segoe UI", 16),
        "font": ("Comic Sans MS", 10),
        "button_font": ("Comic Sans MS", 10, "bold")
    },
    "modern": {
        "bg": "#f5f5f5",
        "fg": "#333333",
        "button_bg": "#4a90d9",
        "button_fg": "#ffffff",
        "entry_bg": "#ffffff",
        "entry_fg": "#333333",
        "highlight": "#3a7bc8",
        "progress": "#4a90d9",
        "button_radius": 15,
        "combobox_font": ("Segoe UI", 16),
        "font": ("Arial", 10),
        "button_font": ("Arial", 10, "bold")
    },
    "cyber": {
        "bg": "#121212",
        "fg": "#00ff00",
        "button_bg": "#003300",
        "button_fg": "#00ff00",
        "entry_bg": "#222222",
        "entry_fg": "#00ff00",
        "highlight": "#00cc00",
        "progress": "#00ff00",
        "button_radius": 0,
        "combobox_font": ("Segoe UI", 16),
        "font": ("Courier New", 10),
        "button_font": ("Courier New", 10, "bold")
    },
    "purple": {
        "bg": "#f0e0ff",
        "fg": "#330066",
        "button_bg": "#9966cc",
        "button_fg": "#ffffff",
        "entry_bg": "#ffffff",
        "entry_fg": "#330066",
        "highlight": "#663399",
        "progress": "#9966cc",
        "button_radius": 12,
        "combobox_font": ("Segoe UI", 16),
        "font": ("Verdana", 10),
        "button_font": ("Verdana", 10, "bold")
    },
    "contrasted": {
        "bg": "#FFFFFF",
        "fg": "#000000",
        "button_bg": "#FF6D00",
        "button_fg": "#FFFFFF",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#000000",
        "highlight": "#0057B7",
        "progress": "#FF0000",
        "button_radius": 8,
        "combobox_font": ("Segoe UI", 16),
        "font": ("Arial Bold", 12, "bold"),
        "button_font": ("Arial Bold", 12, "bold")
    }
}

class DownloadItem:
    def __init__(self, url, video_stream, audio_stream, output_path, audio_only=False, playlist_info=None):
        self.url = url
        self.video_stream = video_stream
        self.audio_stream = audio_stream
        self.output_path = output_path
        self.audio_only = audio_only
        self.paused = False
        self.cancelled = False
        self.completed = False
        self.progress = 0
        self.status = "Queued"
        self.thumbnail_url = None
        self.title = None
        self.playlist_info = playlist_info
        self.playlist_index = None
        self.playlist_total = None
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed = "0 B/s"

class DownloadManager:
    def __init__(self):
        self.download_queue = Queue()
        self.current_download = None
        self.active = False
        self.paused = False
        self.thread = None
        self.gui_update_callback = None

    def set_gui_update_callback(self, callback):
        self.gui_update_callback = callback

    def add_to_queue(self, download_item):
        self.download_queue.put(download_item)
        if not self.active:
            self.start_downloader()

    def start_downloader(self):
        if not self.active:
            self.active = True
            self.thread = threading.Thread(target=self._download_worker, daemon=True)
            self.thread.start()

    def _download_worker(self):
        while self.active:
            if self.paused:
                time.sleep(0.5)
                continue

            if self.current_download is None or self.current_download.completed or self.current_download.cancelled:
                if self.download_queue.empty():
                    self.active = False
                    break
                self.current_download = self.download_queue.get()
                if self.gui_update_callback:
                    self.gui_update_callback(self.current_download)

            if self.current_download.paused:
                time.sleep(0.5)
                continue

            self._download_item(self.current_download)

    def _download_item(self, download_item):
        def update_progress(data):
            if data['status'] == 'downloading':
                if 'total_bytes' in data or 'total_bytes_estimate' in data:
                    total = data.get('total_bytes') or data.get('total_bytes_estimate')
                    downloaded = data.get('downloaded_bytes', 0)
                    speed = data.get('_speed_str', '0 B/s')
                    
                    if total and downloaded:
                        progress = (downloaded / total) * 100
                        download_item.progress = progress
                        download_item.downloaded_bytes = downloaded
                        download_item.total_bytes = total
                        download_item.speed = speed
                        
                        if download_item.playlist_info:
                            status = f"Downloading {download_item.playlist_index}/{download_item.playlist_total} ({progress:.1f}%)"
                        else:
                            status = f"Downloading ({progress:.1f}%)"
                        download_item.status = status
                        if self.gui_update_callback:
                            self.gui_update_callback(download_item)

        format_str = ""
        if download_item.audio_only:
            format_str = download_item.audio_stream['format_id']
        else:
            format_str = f"{download_item.video_stream['format_id']}+{download_item.audio_stream['format_id']}"

        ydl_opts = {
            'format': format_str,
            'outtmpl': download_item.output_path,
            'progress_hooks': [update_progress],
            'quiet': True,
            'ignoreerrors': True
        }

        try:
            if download_item.playlist_info:
                download_item.status = f"Downloading {download_item.playlist_index}/{download_item.playlist_total} (0%)"
            else:
                download_item.status = "Downloading (0%)"
                
            if self.gui_update_callback:
                self.gui_update_callback(download_item)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([download_item.url])
            download_item.status = "Completed"
            download_item.completed = True
            download_item.progress = 100
        except Exception as e:
            download_item.status = f"Failed: {str(e)}"
            download_item.cancelled = True
        finally:
            if self.gui_update_callback:
                self.gui_update_callback(download_item)

def format_size(bytes):
    if bytes is None or bytes == 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024.0
    return f"{bytes:.1f} TB"

def get_streams_info(url):
    ydl_opts = {'quiet': True, 'no_warnings': True, 'ignoreerrors': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return None
                
            if 'entries' in info:
                playlist_info = []
                for entry in info['entries']:
                    if entry is not None:
                        playlist_info.append(entry)
                return playlist_info
            return info
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch video information: {e}")
            return None

def filter_streams(info, video_format, audio_codec, audio_only=False):
    streams = {'video': [], 'audio': []}
    if not info:
        return streams

    for f in info['formats']:
        if not f.get('format_id'):
            continue

        if not audio_only and f.get('vcodec') != 'none' and f.get('acodec') == 'none':
            if video_format.lower() == f['ext']:
                streams['video'].append(f)
        elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
            if audio_codec.lower() in str(f.get('acodec', '')).lower():
                streams['audio'].append(f)

    return streams

def update_thumbnail(thumbnail_url, thumbnail_label, title_label, width_reference):
    try:
        if not thumbnail_url:
            thumbnail_label.config(image='')
            thumbnail_label.image = None
            title_label.config(text='')
            return
            
        response = requests.get(thumbnail_url)
        img_data = BytesIO(response.content)
        image = Image.open(img_data)

        new_width = int(width_reference * SCALING_FACTOR)
        aspect_ratio = image.width / image.height
        new_height = int(new_width / aspect_ratio)

        image = image.resize((new_width, new_height))
        thumbnail_image = ImageTk.PhotoImage(image)

        thumbnail_label.config(image=thumbnail_image)
        thumbnail_label.image = thumbnail_image
        thumbnail_label.current_width = new_width
        thumbnail_label.image_url = thumbnail_url
        
        if title_label:
            title_label.config(text=thumbnail_label.video_title if hasattr(thumbnail_label, 'video_title') else '')
    except Exception as e:
        print(f"Error fetching thumbnail: {e}")
        thumbnail_label.config(image='')
        thumbnail_label.image = None
        if title_label:
            title_label.config(text='')

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def get_unique_filename(output_path, overwrite):
    if not os.path.exists(output_path):
        return output_path
    
    if overwrite:
        try:
            os.remove(output_path)
            return output_path
        except Exception as e:
            messagebox.showerror("Error", f"Could not overwrite file: {e}")
            return None
    
    base, ext = os.path.splitext(output_path)
    counter = 1
    while True:
        new_path = f"{base} ({counter}){ext}"
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def animate_spinner(label, spinner_chars=["|", "/", "-", "\\"]):
    def update():
        current = label.cget("text")
        if "Fetching" in current:
            idx = spinner_chars.index(current[-1]) if current[-1] in spinner_chars else 0
            next_char = spinner_chars[(idx + 1) % len(spinner_chars)]
            label.config(text=f"Fetching {next_char}")
            label.after(100, update)
    update()

def create_download_item(url, video_stream, audio_stream, output_folder, overwrite, audio_only, info=None, playlist_info=None, playlist_index=None, playlist_total=None):
    if info is None:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return None
    
    title = sanitize_filename(info.get('title', 'video'))
    
    if audio_only:
        audio_codec = audio_stream.get('acodec', 'none').split('.')[0] if audio_stream else 'none'
        ext = audio_stream.get('ext', 'm4a')
        filename = f"{title}_{audio_codec}.{ext}"
    else:
        video_res = f"{video_stream.get('width', '?')}x{video_stream.get('height', '?')}"
        audio_codec = audio_stream.get('acodec', 'none').split('.')[0] if audio_stream else 'none'
        ext = video_stream.get('ext', 'mp4')
        filename = f"{title}_{video_res}_{audio_codec}.{ext}"
    
    output_path = os.path.join(output_folder, filename)
    final_path = get_unique_filename(output_path, overwrite)
    
    if not final_path:
        return None
        
    item = DownloadItem(url, video_stream, audio_stream, final_path, audio_only, playlist_info)
    item.thumbnail_url = info.get('thumbnail')
    item.title = title
    item.playlist_index = playlist_index
    item.playlist_total = playlist_total
    return item

def convert_to_mp3(file_path):
    try:
        if not os.path.exists(file_path):
            messagebox.showerror("Error", "File not found for conversion")
            return False
            
        output_path = os.path.splitext(file_path)[0] + ".mp3"
        cmd = [
            'ffmpeg',
            '-i', file_path,
            '-codec:a', 'libmp3lame',
            '-q:a', '2',
            output_path
        ]
        
        subprocess.run(cmd, check=True)
        messagebox.showinfo("Success", f"Converted to MP3: {os.path.basename(output_path)}")
        return True
    except subprocess.CalledProcessError as e:
        messagebox.showerror("Error", f"Failed to convert to MP3: {e}")
        return False
    except Exception as e:
        messagebox.showerror("Error", f"Unexpected error during conversion: {e}")
        return False

def update_scaling(factor, widgets):
    global SCALING_FACTOR
    SCALING_FACTOR = float(factor)
    
    theme = THEMES[CURRENT_THEME]
    font_size = int(FONT_SIZES['medium'] * SCALING_FACTOR)
    button_font = (theme['button_font'][0], int(theme['button_font'][1] * SCALING_FACTOR), theme['button_font'][2])
    
    # Calculate scaled combobox font size based on theme's base size
    combobox_font_size = int(theme['combobox_font'][1] * SCALING_FACTOR)
    combobox_font = (theme['combobox_font'][0], combobox_font_size)
    
    # Update all widgets
    for widget_type, widget_list in widgets.items():
        for widget in widget_list:
            try:
                if widget_type == 'label':
                    widget.config(font=(theme['font'][0], font_size))
                elif widget_type == 'button':
                    widget.config(font=button_font)
                    if THEMES[CURRENT_THEME]['button_radius'] > 0:
                        widget.config(relief='solid', borderwidth=0, 
                                    highlightthickness=0, padx=int(10 * SCALING_FACTOR), 
                                    pady=int(5 * SCALING_FACTOR))
                elif widget_type == 'entry':
                    # Fixed width for entry widgets (20 characters)
                    widget.config(font=(theme['font'][0], font_size), width=20)
                elif widget_type == 'combobox':
                    # Apply scaled combobox font
                    widget.config(font=combobox_font)
                    style = ttk.Style()
                    style.configure('TCombobox', 
                                   font=combobox_font,
                                   padding=2)
                    style.configure('TCombobox.Listbox', 
                                   font=combobox_font,
                                   background=theme['entry_bg'],
                                   foreground=theme['entry_fg'])
                    # Force update of the combobox dropdown list font
                    root.option_add("*TCombobox*Listbox*Font", combobox_font)
                    # Recreate the combobox to apply the new font
                    if hasattr(widget, 'tk_popdown'):
                        widget.tk_popdown = None
                elif widget_type == 'radiobutton':
                    widget.config(font=(theme['font'][0], font_size))
                elif widget_type == 'checkbox':
                    widget.config(font=(theme['font'][0], font_size))
            except Exception as e:
                print(f"Error updating widget scaling: {e}")
                continue
    
    # Update padding and sizes
    for frame in widgets.get('frame', []):
        if not isinstance(frame, tk.Canvas):
            frame.config(padx=int(10 * SCALING_FACTOR), pady=int(10 * SCALING_FACTOR))
    
    # Update progressbar length
    for pb in widgets.get('progressbar', []):
        pb.config(length=int(300 * SCALING_FACTOR))
    
    # Update combobox widths (fixed character width)
    for cb in widgets.get('combobox', []):
        if 'width' in cb.configure():
            cb.config(width=25)
    
    # Update thumbnail if exists
    if 'thumbnail_label' in widgets and hasattr(widgets['thumbnail_label'][0], 'image_url'):
        thumbnail_label = widgets['thumbnail_label'][0]
        new_width = int(400 * SCALING_FACTOR)
        update_thumbnail(thumbnail_label.image_url, thumbnail_label, None, new_width)
    
    # Adjust queue column width based on scaling
    if 'entry' in widgets and len(widgets['entry']) > 0 and isinstance(widgets['entry'][-1], tk.Listbox):
        queue_listbox = widgets['entry'][-1]
        queue_listbox.config(width=int(30 + (10 * SCALING_FACTOR)))
    
    # Ensure window fits all content
    root.update_idletasks()
    root.geometry("")
    root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())

def reset_scaling(widgets):
    global SCALING_FACTOR
    SCALING_FACTOR = 1.0
    scaling_var.set('1.0')
    update_scaling('1.0', widgets)
    root.geometry("")
    root.minsize(1000, 600)

def apply_theme(theme_name, widgets):
    global CURRENT_THEME
    CURRENT_THEME = theme_name
    theme = THEMES[theme_name]
    
    style = ttk.Style()
    style.theme_use('clam')
    
    # Calculate scaled combobox font size based on theme's base size
    combobox_font_size = int(theme['combobox_font'][1] * SCALING_FACTOR)
    combobox_font = (theme['combobox_font'][0], combobox_font_size)
    
    # Configure combobox styles with scaled font
    style.configure('TCombobox', 
                   fieldbackground=theme['entry_bg'],
                   background=theme['entry_bg'],
                   foreground=theme['entry_fg'],
                   font=combobox_font,
                   padding=5)
    
    style.configure('TCombobox.Listbox',
                   font=combobox_font,
                   background=theme['entry_bg'],
                   foreground=theme['entry_fg'])
    
    # Force update of the combobox dropdown list font
    root.option_add("*TCombobox*Listbox*Font", combobox_font)
    
    style.configure('Horizontal.TProgressbar', 
                   background=theme['progress'], 
                   troughcolor=theme['bg'])
    
    # Apply to all widgets
    for widget_type, widget_list in widgets.items():
        for widget in widget_list:
            try:
                if widget_type == 'root':
                    widget.config(bg=theme['bg'])
                elif widget_type == 'frame':
                    widget.config(bg=theme['bg'])
                elif widget_type == 'label':
                    widget.config(bg=theme['bg'], fg=theme['fg'], font=theme['font'])
                elif widget_type == 'button':
                    widget.config(bg=theme['button_bg'], fg=theme['button_fg'], 
                                activebackground=theme['highlight'], activeforeground=theme['button_fg'],
                                font=theme['button_font'])
                    if theme['button_radius'] > 0:
                        widget.config(relief='solid', borderwidth=0, highlightthickness=0)
                elif widget_type == 'entry':
                    widget.config(bg=theme['entry_bg'], fg=theme['entry_fg'],
                                selectbackground=theme['highlight'],
                                font=theme['font'],
                                insertbackground=theme['fg'],
                                width=20)  # Fixed width
                elif widget_type == 'combobox':
                    widget.config(font=combobox_font)
                    # Force recreation of the dropdown list
                    if hasattr(widget, 'tk_popdown'):
                        widget.tk_popdown = None
                elif widget_type == 'radiobutton':
                    widget.config(bg=theme['bg'], fg=theme['fg'], 
                                activebackground=theme['bg'], activeforeground=theme['fg'],
                                selectcolor=theme['bg'],
                                font=theme['font'])
                elif widget_type == 'checkbox':
                    widget.config(bg=theme['bg'], fg=theme['fg'], 
                                activebackground=theme['bg'], activeforeground=theme['fg'],
                                selectcolor=theme['bg'],
                                font=theme['font'])
                elif widget_type == 'listbox':
                    widget.config(bg=theme['entry_bg'], fg=theme['entry_fg'],
                                selectbackground=theme['highlight'], font=theme['font'])
            except Exception as e:
                print(f"Error applying theme to widget: {e}")
                continue
    
    # Update scaling to apply new fonts
    update_scaling(SCALING_FACTOR, widgets)

def create_gui():
    global root, scaling_var
    
    root = tk.Tk()

    # Windows-specific DPI awareness
    if os.name == 'nt':
        ctypes.windll.shcore.SetProcessDpiAwareness(1)

    root.title(f"Penggraber {APP_VERSION} - Hachi Dono")
    root.minsize(1000, 600)

    # Set icon
    try:
        root.iconbitmap('icon.ico')
    except:
        try:
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
            root.iconbitmap(icon_path)
        except:
            root.iconbitmap('')

    # Set default download directory
    default_download_dir = str(Path.home() / "Downloads")

    # Create main container
    main_container = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=20)
    main_container.pack(fill=tk.BOTH, expand=True)

    # Left side - control frame
    control_frame = tk.Frame(main_container, padx=10, pady=10)
    main_container.add(control_frame, minsize=700)
    widgets = {
        'root': [root, main_container],
        'label': [],
        'button': [],
        'entry': [],
        'combobox': [],
        'frame': [control_frame],
        'progressbar': [],
        'radiobutton': [],
        'checkbox': [],
        'thumbnail_label': [],
        'listbox': []
    }

    # Right side - queue frame
    queue_frame = tk.Frame(main_container)
    main_container.add(queue_frame, minsize=300)
    widgets['frame'].append(queue_frame)

    # Initialize download manager
    download_manager = DownloadManager()

    # UI Scaling and Theme Control
    settings_frame = tk.Frame(control_frame)
    settings_frame.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['frame'].append(settings_frame)
    
    scaling_label = tk.Label(settings_frame, text="UI Scale:")
    scaling_label.pack(side="left")
    widgets['label'].append(scaling_label)
    
    scaling_var = tk.StringVar(value='1.0')
    scaling_options = ['0.5', '0.75', '1.0', '1.25', '1.5', '1.75', '2']
    scaling_dropdown = ttk.Combobox(settings_frame, textvariable=scaling_var, 
                                  values=scaling_options, state="readonly", width=5)
    scaling_dropdown.pack(side="left", padx=int(5 * SCALING_FACTOR))
    widgets['combobox'].append(scaling_dropdown)
    
    reset_scale_button = tk.Button(settings_frame, text="Reset", command=lambda: reset_scaling(widgets))
    reset_scale_button.pack(side="left", padx=int(5 * SCALING_FACTOR))
    widgets['button'].append(reset_scale_button)

    theme_label = tk.Label(settings_frame, text="Theme:")
    theme_label.pack(side="left", padx=(int(15 * SCALING_FACTOR), 0))
    widgets['label'].append(theme_label)
    
    theme_var = tk.StringVar(value='light')
    theme_options = ['light', 'dark', 'orange', 'modern', 'cyber', 'purple', 'contrasted']
    theme_dropdown = ttk.Combobox(settings_frame, textvariable=theme_var, 
                                values=theme_options, state="readonly", width=8)
    theme_dropdown.pack(side="left")
    widgets['combobox'].append(theme_dropdown)

    # URL Entry with fixed width
    url_frame = tk.Frame(control_frame)
    url_frame.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['frame'].append(url_frame)
    
    url_label = tk.Label(url_frame, text="YouTube URL:")
    url_label.pack(side="left")
    widgets['label'].append(url_label)
    
    url_entry = tk.Entry(url_frame, width=20)  # Fixed width of 20 characters
    url_entry.pack(side="left", padx=int(5 * SCALING_FACTOR), expand=True, fill=tk.X)
    widgets['entry'].append(url_entry)

    fetch_button = tk.Button(url_frame, text="Fetch Streams")
    fetch_button.pack(side="left", padx=int(5 * SCALING_FACTOR))
    widgets['button'].append(fetch_button)

    audio_only_var = tk.BooleanVar()
    audio_only_checkbox = tk.Checkbutton(url_frame, text="Audio Only", variable=audio_only_var)
    audio_only_checkbox.pack(side="left", padx=int(5 * SCALING_FACTOR))
    widgets['checkbox'].append(audio_only_checkbox)

    # Format Selection
    video_format_var = tk.StringVar(value='webm')
    video_format_frame = tk.Frame(control_frame)
    video_format_frame.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['frame'].append(video_format_frame)
    
    video_format_label = tk.Label(video_format_frame, text="Video Format:")
    video_format_label.pack(side="left")
    widgets['label'].append(video_format_label)
    
    webm_rb = tk.Radiobutton(video_format_frame, text="WebM", variable=video_format_var, value="webm")
    webm_rb.pack(side="left")
    widgets['radiobutton'].append(webm_rb)
    
    mp4_rb = tk.Radiobutton(video_format_frame, text="MP4", variable=video_format_var, value="mp4")
    mp4_rb.pack(side="left")
    widgets['radiobutton'].append(mp4_rb)

    audio_codec_var = tk.StringVar(value='opus')
    audio_codec_frame = tk.Frame(control_frame)
    audio_codec_frame.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['frame'].append(audio_codec_frame)
    
    audio_codec_label = tk.Label(audio_codec_frame, text="Audio Codec:")
    audio_codec_label.pack(side="left")
    widgets['label'].append(audio_codec_label)
    
    opus_rb = tk.Radiobutton(audio_codec_frame, text="Opus", variable=audio_codec_var, value="opus")
    opus_rb.pack(side="left")
    widgets['radiobutton'].append(opus_rb)
    
    aac_rb = tk.Radiobutton(audio_codec_frame, text="AAC", variable=audio_codec_var, value="aac")
    aac_rb.pack(side="left")
    widgets['radiobutton'].append(aac_rb)

    # Stream Selection with larger font
    video_combobox = ttk.Combobox(control_frame, width=15, state="readonly")
    video_combobox.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['combobox'].append(video_combobox)
    
    audio_combobox = ttk.Combobox(control_frame, width=15, state="readonly")
    audio_combobox.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['combobox'].append(audio_combobox)

    # Thumbnail and Title
    thumbnail_container = tk.Frame(control_frame)
    thumbnail_container.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['frame'].append(thumbnail_container)
    
    thumbnail_label = tk.Label(thumbnail_container)
    thumbnail_label.pack()
    widgets['thumbnail_label'].append(thumbnail_label)
    
    video_title_label = tk.Label(thumbnail_container, text="", wraplength=400)
    video_title_label.pack()
    widgets['label'].append(video_title_label)

    # Output Options with fixed width entry
    output_folder_frame = tk.Frame(control_frame)
    output_folder_frame.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['frame'].append(output_folder_frame)
    
    output_folder_label = tk.Label(output_folder_frame, text="Output Folder:")
    output_folder_label.pack(side="left")
    widgets['label'].append(output_folder_label)
    
    output_folder_entry = tk.Entry(output_folder_frame, width=20)  # Fixed width of 20 characters
    output_folder_entry.pack(side="left", padx=int(5 * SCALING_FACTOR), expand=True, fill=tk.X)
    output_folder_entry.insert(0, default_download_dir)
    widgets['entry'].append(output_folder_entry)
    
    browse_button = tk.Button(output_folder_frame, text="Browse", command=lambda: browse_folder(output_folder_entry))
    browse_button.pack(side="left")
    widgets['button'].append(browse_button)

    overwrite_var = tk.BooleanVar()
    overwrite_checkbox = tk.Checkbutton(control_frame, text="Overwrite existing files", variable=overwrite_var)
    overwrite_checkbox.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['checkbox'].append(overwrite_checkbox)

    # Download Controls
    download_buttons_frame = tk.Frame(control_frame)
    download_buttons_frame.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['frame'].append(download_buttons_frame)
    
    download_button = tk.Button(download_buttons_frame, text="Download", state="disabled")
    download_button.pack(side="left", padx=int(5 * SCALING_FACTOR))
    widgets['button'].append(download_button)
    
    convert_button = tk.Button(download_buttons_frame, text="Convert to MP3", state="disabled")
    convert_button.pack(side="left", padx=int(5 * SCALING_FACTOR))
    widgets['button'].append(convert_button)

    progressbar = ttk.Progressbar(control_frame, length=300, mode="determinate", maximum=100)
    progressbar.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['progressbar'].append(progressbar)

    status_label = tk.Label(control_frame, text="Status: Ready")
    status_label.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['label'].append(status_label)
    
    download_info_label = tk.Label(control_frame, text="")
    download_info_label.pack(fill=tk.X, pady=int(5 * SCALING_FACTOR))
    widgets['label'].append(download_info_label)

    # Download Queue UI
    queue_label = tk.Label(queue_frame, text="Download Queue", font=('TkDefaultFont', 10, 'bold'))
    queue_label.pack(fill=tk.X, pady=(0, 10))
    widgets['label'].append(queue_label)

    queue_controls = tk.Frame(queue_frame)
    queue_controls.pack(fill=tk.X, pady=(5, 0))
    widgets['frame'].append(queue_controls)

    pause_button = tk.Button(queue_controls, text="Pause", command=lambda: toggle_pause())
    pause_button.pack(side="left", padx=5)
    widgets['button'].append(pause_button)

    cancel_button = tk.Button(queue_controls, text="Cancel", command=lambda: cancel_current())
    cancel_button.pack(side="left", padx=5)
    widgets['button'].append(cancel_button)
    
    remove_button = tk.Button(queue_controls, text="Remove", command=lambda: remove_completed())
    remove_button.pack(side="left", padx=5)
    widgets['button'].append(remove_button)

    queue_listbox = tk.Listbox(queue_frame, width=30, height=20, font=('TkDefaultFont', 10))
    queue_listbox.pack(fill=tk.BOTH, expand=True)
    widgets['listbox'].append(queue_listbox)

    # Playlist handling variables
    current_playlist = []
    current_playlist_index = 0

    def toggle_pause():
        download_manager.paused = not download_manager.paused
        pause_button.config(text="Resume" if download_manager.paused else "Pause")

    def cancel_current():
        if download_manager.current_download:
            download_manager.current_download.cancelled = True
            update_queue_display()

    def remove_completed():
        messagebox.showinfo("Info", "This would remove completed downloads from the queue in a full implementation")
    
    def convert_current_to_mp3():
        if download_manager.current_download and download_manager.current_download.completed:
            if convert_to_mp3(download_manager.current_download.output_path):
                messagebox.showinfo("Success", "Conversion completed successfully!")
        else:
            messagebox.showwarning("Warning", "No completed download to convert")

    def update_queue_display():
        queue_listbox.delete(0, tk.END)
        if download_manager.current_download:
            status = download_manager.current_download.status
            name = os.path.basename(download_manager.current_download.output_path)
            if download_manager.current_download.playlist_info:
                queue_listbox.insert(tk.END, f"[Current {download_manager.current_download.playlist_index}/{download_manager.current_download.playlist_total}] {name} - {status}")
            else:
                queue_listbox.insert(tk.END, f"[Current] {name} - {status}")
        
        for item in list(download_manager.download_queue.queue):
            name = os.path.basename(item.output_path)
            if item.playlist_info:
                queue_listbox.insert(tk.END, f"[Queued {item.playlist_index}/{item.playlist_total}] {name}")
            else:
                queue_listbox.insert(tk.END, f"[Queued] {name}")

    def update_gui_for_current_download(download_item):
        status_label.config(text=f"Status: {download_item.status}")
        progressbar['value'] = download_item.progress
        
        if download_item.total_bytes > 0:
            downloaded = format_size(download_item.downloaded_bytes)
            total = format_size(download_item.total_bytes)
            media_type = "Audio" if download_item.audio_only else "Video"
            info_text = f"{media_type} downloading: {downloaded} / {total} @ {download_item.speed}"
            download_info_label.config(text=info_text)
        
        convert_button.config(state="normal" if download_item.completed else "disabled")
        
        root.update_idletasks()

    download_manager.set_gui_update_callback(update_gui_for_current_download)

    def update_queue_periodically():
        update_queue_display()
        root.after(1000, update_queue_periodically)

    # Callbacks
    scaling_dropdown.bind("<<ComboboxSelected>>", 
                        lambda e: update_scaling(scaling_var.get(), widgets))
    
    theme_dropdown.bind("<<ComboboxSelected>>", 
                       lambda e: apply_theme(theme_var.get(), widgets))
    
    root.bind('<Control-r>', lambda e: reset_scaling(widgets))
    root.bind('<Control-R>', lambda e: reset_scaling(widgets))

    # Fetch Button Logic
    def start_fetch():
        url = url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        if "youtube.com" not in url and "youtu.be" not in url:
            messagebox.showerror("Error", "Please enter a valid YouTube URL")
            return
        
        video_format = video_format_var.get()
        audio_codec = audio_codec_var.get()
        audio_only = audio_only_var.get()
        
        fetch_button.config(state="disabled", text="Fetching |")
        animate_spinner(fetch_button)
        
        def fetch_thread():
            info = get_streams_info(url)
            
            if info is None:
                root.after(0, lambda: fetch_button.config(state="normal", text="Fetch Streams"))
                return
                
            if isinstance(info, list):
                root.after(0, lambda: handle_playlist(info, video_format, audio_codec, audio_only))
            else:
                root.after(0, lambda: handle_single_video(info, video_format, audio_codec, audio_only, url))
            
            root.after(0, lambda: fetch_button.config(state="normal", text="Fetch Streams"))
        
        threading.Thread(target=fetch_thread, daemon=True).start()

    def handle_single_video(info, video_format, audio_codec, audio_only, url):
        streams = filter_streams(info, video_format, audio_codec, audio_only)
        
        if audio_only:
            video_combobox['values'] = []
            video_combobox.set('')
        else:
            video_combobox['values'] = [f"{s.get('width', '?')}x{s.get('height', '?')} - {format_size(s.get('filesize', s.get('filesize_approx')))}" for s in streams['video']]
        
        audio_combobox['values'] = [f"{s.get('acodec', '?')} - {format_size(s.get('filesize', s.get('filesize_approx')))}" for s in streams['audio']]

        thumbnail_url = info.get('thumbnail')
        if thumbnail_url:
            thumbnail_label.video_title = info.get('title', 'No title available')
            update_thumbnail(thumbnail_url, thumbnail_label, video_title_label, width_reference=400)
        else:
            thumbnail_label.config(image='')
            thumbnail_label.image = None
            video_title_label.config(text='')

        def download_button_action():
            selected_video = streams['video'][video_combobox.current()] if (not audio_only and video_combobox.current() != -1) else None
            selected_audio = streams['audio'][audio_combobox.current()] if audio_combobox.current() != -1 else None
            output_folder = output_folder_entry.get()
            overwrite = overwrite_var.get()
            
            if not output_folder:
                output_folder = os.getcwd()
                output_folder_entry.delete(0, tk.END)
                output_folder_entry.insert(0, output_folder)
            
            download_item = create_download_item(
                url, selected_video, selected_audio, output_folder, overwrite, audio_only, info
            )
            
            if download_item:
                download_manager.add_to_queue(download_item)
                messagebox.showinfo("Added to Queue", "The download has been added to the queue.")

        download_button.config(command=download_button_action, 
                            state="normal" if (audio_only or streams['video']) and streams['audio'] else "disabled")
        
        convert_button.config(command=convert_current_to_mp3, state="disabled")

    def handle_playlist(playlist_info, video_format, audio_codec, audio_only):
        nonlocal current_playlist, current_playlist_index
        
        if not playlist_info:
            messagebox.showwarning("Empty Playlist", "No videos found in this playlist or all are unavailable.")
            return
            
        current_playlist = playlist_info
        current_playlist_index = 0
        process_next_playlist_item(video_format, audio_codec, audio_only)

    def process_next_playlist_item(video_format, audio_codec, audio_only):
        nonlocal current_playlist, current_playlist_index
        
        if current_playlist_index >= len(current_playlist):
            messagebox.showinfo("Playlist Complete", "All videos in the playlist have been processed.")
            return
            
        video_info = current_playlist[current_playlist_index]
        if video_info is None:
            current_playlist_index += 1
            process_next_playlist_item(video_format, audio_codec, audio_only)
            return
            
        streams = filter_streams(video_info, video_format, audio_codec, audio_only)
        
        if audio_only:
            video_combobox['values'] = []
            video_combobox.set('')
        else:
            video_combobox['values'] = [f"{s.get('width', '?')}x{s.get('height', '?')} - {format_size(s.get('filesize', s.get('filesize_approx')))}" for s in streams['video']]
        
        audio_combobox['values'] = [f"{s.get('acodec', '?')} - {format_size(s.get('filesize', s.get('filesize_approx')))}" for s in streams['audio']]

        thumbnail_url = video_info.get('thumbnail')
        if thumbnail_url:
            thumbnail_label.video_title = video_info.get('title', 'No title available')
            update_thumbnail(thumbnail_url, thumbnail_label, video_title_label, width_reference=400)
        else:
            thumbnail_label.config(image='')
            thumbnail_label.image = None
            video_title_label.config(text='')

        def download_button_action():
            nonlocal current_playlist_index
            
            selected_video = streams['video'][video_combobox.current()] if (not audio_only and video_combobox.current() != -1) else None
            selected_audio = streams['audio'][audio_combobox.current()] if audio_combobox.current() != -1 else None
            output_folder = output_folder_entry.get()
            overwrite = overwrite_var.get()
            
            if not output_folder:
                output_folder = os.getcwd()
                output_folder_entry.delete(0, tk.END)
                output_folder_entry.insert(0, output_folder)
            
            download_item = create_download_item(
                video_info['webpage_url'], 
                selected_video, 
                selected_audio, 
                output_folder, 
                overwrite, 
                audio_only, 
                video_info,
                current_playlist,
                current_playlist_index + 1,
                len(current_playlist)
            )
            
            if download_item:
                download_manager.add_to_queue(download_item)
                current_playlist_index += 1
                process_next_playlist_item(video_format, audio_codec, audio_only)

        download_button.config(command=download_button_action, 
                            state="normal" if (audio_only or streams['video']) and streams['audio'] else "disabled")
        
        convert_button.config(command=convert_current_to_mp3, state="disabled")

    def browse_folder(entry_widget):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, folder_selected)

    fetch_button.config(command=start_fetch)
    convert_button.config(command=convert_current_to_mp3)

    # Initial setup
    update_scaling('1.0', widgets)
    apply_theme('light', widgets)
    
    # Start queue updater
    update_queue_periodically()

    root.mainloop()

if __name__ == "__main__":
    create_gui()