# Add this at the VERY START of your script (first lines)
import os
if os.name == 'nt':  # Windows
    import ctypes
    # This makes the taskbar icon work properly
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('PengGrab.1.0')

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

def format_size(bytes):
    if bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}TB"

def get_streams_info(url):
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            print(f"Attempting to fetch info for URL: {url}")  # Debug line
            info = ydl.extract_info(url, download=False)
            print("Successfully fetched stream info")  # Debug line
            return info
        except Exception as e:
            print(f"Error in get_streams_info: {str(e)}")  # Debug line
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

def update_thumbnail(thumbnail_url, thumbnail_label, width_reference):
    try:
        response = requests.get(thumbnail_url)
        img_data = BytesIO(response.content)
        image = Image.open(img_data)

        new_width = width_reference
        aspect_ratio = image.width / image.height
        new_height = int(new_width / aspect_ratio)

        image = image.resize((new_width, new_height))
        thumbnail_image = ImageTk.PhotoImage(image)

        thumbnail_label.config(image=thumbnail_image)
        thumbnail_label.image = thumbnail_image
    except Exception as e:
        print(f"Error fetching thumbnail: {e}")

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def get_unique_filename(output_path, overwrite):
    """Handle file naming conflicts"""
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

def start_download(url, video_stream, audio_stream, progressbar, status_label, output_folder, overwrite, audio_only):
    def update_progress(data):
        if data.get('status') == 'downloading...':
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 1
            downloaded = data.get('downloaded_bytes', 0)
            progress = (data['downloaded_bytes'] / data['total_bytes']) * 100
            progressbar['value'] = progress
            root.update_idletasks()

    # Get video info for title
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = sanitize_filename(info.get('title', 'video'))
    
    # Create appropriate filename
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
    
    # Handle existing files
    final_path = get_unique_filename(output_path, overwrite)
    if not final_path:
        status_label.config(text="Download aborted")
        return

    # Set download format
    if audio_only:
        format_str = audio_stream['format_id']
    else:
        format_str = f"{video_stream['format_id']}+{audio_stream['format_id']}"

    ydl_opts = {
        'format': format_str,
        'outtmpl': final_path,
        'progress_hooks': [update_progress],
        'quiet': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            status_label.config(text="Downloading...")
            ydl.download([url])
            status_label.config(text=f"Saved to: {os.path.basename(final_path)}")
            messagebox.showinfo("Success", f"Download completed!\nSaved to: {final_path}")
        except Exception as e:
            status_label.config(text="Download failed")
            messagebox.showerror("Error", f"An error occurred: {e}")
        finally:
            progressbar['value'] = 0

def animate_spinner(label, spinner_chars=["|", "/", "-", "\\"]):
    def update():
        current = label.cget("text")
        if "Fetching" in current:
            idx = spinner_chars.index(current[-1]) if current[-1] in spinner_chars else 0
            next_char = spinner_chars[(idx + 1) % len(spinner_chars)]
            label.config(text=f"Fetching {next_char}")
            label.after(100, update)
    update()

def on_select_stream(url, video_format, audio_codec, video_combobox, audio_combobox, progressbar, 
                    status_label, thumbnail_label, download_button, output_folder_entry, 
                    overwrite_var, audio_only_var, fetch_button):
    
    info = None  # Initialize 'info' in the appropriate scope
    
    def fetch_complete():
        fetch_button.config(state="normal", text="Fetch Streams")
        if not info:
            return

        streams = filter_streams(info, video_format, audio_codec, audio_only_var.get())

        if audio_only_var.get():
            video_combobox['values'] = []
            video_combobox.set('')
        else:
            video_combobox['values'] = [f"{s.get('width', '?')}x{s.get('height', '?')} - {format_size(s.get('filesize', s.get('filesize_approx')))}" for s in streams['video']]
        
        audio_combobox['values'] = [f"{s.get('acodec', '?')} - {format_size(s.get('filesize', s.get('filesize_approx')))}" for s in streams['audio']]

        thumbnail_url = info.get('thumbnail')
        if thumbnail_url and not audio_only_var.get():
            update_thumbnail(thumbnail_url, thumbnail_label, width_reference=500)
        else:
            thumbnail_label.config(image='')
            thumbnail_label.image = None

        def download_button_action():
            selected_video = streams['video'][video_combobox.current()] if (not audio_only_var.get() and video_combobox.current() != -1) else None
            selected_audio = streams['audio'][audio_combobox.current()] if audio_combobox.current() != -1 else None
            output_folder = output_folder_entry.get()
            overwrite = overwrite_var.get()
            
            if not output_folder:
                output_folder = os.getcwd()
                output_folder_entry.delete(0, tk.END)
                output_folder_entry.insert(0, output_folder)
                
            start_download(url, selected_video, selected_audio, progressbar, status_label, output_folder, overwrite, audio_only_var.get())

        download_button.config(command=download_button_action, 
                            state="normal" if (audio_only_var.get() or streams['video']) and streams['audio'] else "disabled")

    # Start spinner animation
    fetch_button.config(state="disabled", text="Fetching |")
    animate_spinner(fetch_button)
    
    # Run the fetch in a separate thread
    def fetch_thread():
        nonlocal info
        try:
            print("Thread started")  # Debug line
            info = get_streams_info(url)
            print("Thread completed")  # Debug line
            root.after(0, fetch_complete)
        except Exception as e:
            print(f"Thread error: {e}")  # Debug line
            root.after(0, lambda: messagebox.showerror("Thread Error", str(e)))
    
    threading.Thread(target=fetch_thread, daemon=True).start()
    print("Thread created")


def browse_folder(output_folder_entry):
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        output_folder_entry.delete(0, tk.END)
        output_folder_entry.insert(0, folder_selected)

def create_gui():
    global root
    root = tk.Tk()

     # Windows-specific DPI awareness
    if os.name == 'nt':
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Enable high DPI scaling

    root.title("YT-DLP GUI Downloader")

    # Set default download directory to user's Downloads folder
    default_download_dir = str(Path.home() / "Downloads")

    container = tk.Frame(root, padx=10, pady=10)
    container.pack()

    center_frame = tk.Frame(container)
    center_frame.pack()

    # URL Entry
    url_frame = tk.Frame(center_frame)
    url_frame.pack(pady=2)
    tk.Label(url_frame, text="YouTube URL:").pack(side="left")
    url_entry = tk.Entry(url_frame, width=45)
    url_entry.pack(side="left", padx=5)

    fetch_button = tk.Button(url_frame, text="Fetch Streams")
    fetch_button.pack(side="left", padx=5)

    # Audio only checkbox
    audio_only_var = tk.BooleanVar()
    audio_only_checkbox = tk.Checkbutton(url_frame, text="Audio Only", variable=audio_only_var)
    audio_only_checkbox.pack(side="left", padx=5)

    # Format Selection
    video_format_var = tk.StringVar(value='webm')
    video_format_frame = tk.Frame(center_frame)
    video_format_frame.pack(pady=2)
    tk.Label(video_format_frame, text="Video Format:").pack(side="left")
    tk.Radiobutton(video_format_frame, text="WebM", variable=video_format_var, value="webm").pack(side="left")
    tk.Radiobutton(video_format_frame, text="MP4", variable=video_format_var, value="mp4").pack(side="left")

    audio_codec_var = tk.StringVar(value='opus')
    audio_codec_frame = tk.Frame(center_frame)
    audio_codec_frame.pack(pady=2)
    tk.Label(audio_codec_frame, text="Audio Codec:").pack(side="left")
    tk.Radiobutton(audio_codec_frame, text="Opus", variable=audio_codec_var, value="opus").pack(side="left")
    tk.Radiobutton(audio_codec_frame, text="AAC", variable=audio_codec_var, value="aac").pack(side="left")

    # Stream Selection
    video_combobox = ttk.Combobox(center_frame, width=60, state="readonly")
    video_combobox.pack(pady=2)
    audio_combobox = ttk.Combobox(center_frame, width=60, state="readonly")
    audio_combobox.pack(pady=2)

    # Thumbnail
    thumbnail_label = tk.Label(center_frame)
    thumbnail_label.pack(pady=5)

    # Output Options
    output_folder_frame = tk.Frame(center_frame)
    output_folder_frame.pack(pady=5)
    tk.Label(output_folder_frame, text="Output Folder:").pack(side="left")
    output_folder_entry = tk.Entry(output_folder_frame, width=35)
    output_folder_entry.pack(side="left", padx=5)
    output_folder_entry.insert(0, default_download_dir)
    browse_button = tk.Button(output_folder_frame, text="Browse", command=lambda: browse_folder(output_folder_entry))
    browse_button.pack(side="left")

    overwrite_var = tk.BooleanVar()
    overwrite_checkbox = tk.Checkbutton(center_frame, text="Overwrite existing files", variable=overwrite_var)
    overwrite_checkbox.pack(pady=5)

    # Download Controls
    download_button = tk.Button(center_frame, text="Download", state="disabled")
    download_button.pack(pady=2)

    progressbar = ttk.Progressbar(center_frame, length=500, mode="determinate", maximum=100)
    progressbar.pack(pady=2)

    status_label = tk.Label(center_frame, text="Status: Ready")
    status_label.pack(pady=2)

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
        on_select_stream(url, video_format, audio_codec, video_combobox, audio_combobox, 
                       progressbar, status_label, thumbnail_label, download_button, 
                       output_folder_entry, overwrite_var, audio_only_var, fetch_button)

    fetch_button.config(command=start_fetch)

    root.mainloop()

if __name__ == "__main__":
    create_gui()