#!/usr/bin/env python3
import yt_dlp
from collections import defaultdict

def format_size(bytes):
    """Convert bytes to human-readable format"""
    if bytes is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024.0:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024.0
    return f"{bytes:.1f}TB"

def get_streams_info(url):
    """Get available streams with complete info"""
    ydl_opts = {'quiet': True, 'no_warnings': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

def filter_streams(info, video_format, audio_codec):
    """Filter streams based on user preferences"""
    streams = {
        'video': [],
        'audio': []
    }
    
    for f in info['formats']:
        if not f.get('format_id'):
            continue
            
        # Video streams
        if (f.get('vcodec') != 'none' and 
            f.get('acodec') == 'none'):
            if video_format.lower() == 'webm' and f['ext'] == 'webm':
                streams['video'].append(f)
            elif video_format.lower() == 'mp4' and f['ext'] == 'mp4':
                streams['video'].append(f)
                
        # Audio streams
        elif (f.get('acodec') != 'none' and 
              f.get('vcodec') == 'none'):
            if audio_codec.lower() in str(f.get('acodec', '')).lower():
                streams['audio'].append(f)
    
    return streams

def display_stream_table(streams, stream_type):
    """Display formatted table of streams"""
    print(f"\nAvailable {stream_type} streams:")
    print(f"{'ID':<6} {'EXT':<5} {'RESOLUTION':<12} {'FPS':<5} {'SIZE':<10} {'CODEC':<15} {'VBR/ABR':<10}")
    print("-" * 70)
    
    # Fixed sorting lambda with proper parentheses
    for s in sorted(streams, key=lambda x: (
        x.get('width', 0), 
        x.get('height', 0), 
        x.get('fps', 0)
    )):
        size = format_size(s.get('filesize', s.get('filesize_approx')))
        if stream_type == 'video':
            res = f"{s.get('width', '?')}x{s.get('height', '?')}"
            print(f"{s['format_id']:<6} {s['ext']:<5} {res:<12} {s.get('fps', '?'):<5} {size:<10} {s.get('vcodec', '?'):<15} {s.get('vbr', '?'):<10}")
        else:
            print(f"{s['format_id']:<6} {s['ext']:<5} {'audio':<12} {'-':<5} {size:<10} {s.get('acodec', '?'):<15} {s.get('abr', '?'):<10}")

def choose_stream(streams, stream_type):
    """Let user select a stream from available options"""
    print(f"\nSelect {stream_type} stream by ID:")
    options = []
    for s in streams:
        options.append(s['format_id'])
    while True:
        choice = input(f"Enter {stream_type} ID (or 'q' to quit): ")
        if choice == 'q':
            return None
        if choice in options:
            return choice
        print("Invalid ID, try again.")

def main():
    url = input("Enter YouTube URL: ")
    
    # Step 1: Choose container format
    print("\nChoose video format:")
    print("1. WebM (VP9, usually smaller)")
    print("2. MP4 (H.264, wider compatibility)")
    video_choice = input("Enter choice (1-2): ")
    video_format = "webm" if video_choice == "1" else "mp4"
    
    # Step 2: Choose audio codec
    print("\nChoose audio codec:")
    print("1. Opus (better for WebM, more efficient)")
    print("2. AAC (better compatibility)")
    audio_choice = input("Enter choice (1-2): ")
    audio_codec = "opus" if audio_choice == "1" else "aac"
    
    # Get and filter streams
    info = get_streams_info(url)
    streams = filter_streams(info, video_format, audio_codec)
    
    # Display results
    print(f"\n=== Filtered Results (Video: {video_format.upper()}, Audio: {audio_codec.upper()}) ===")
    display_stream_table(streams['video'], 'video')
    display_stream_table(streams['audio'], 'audio')
    
    # Step 3: Choose video and audio streams
    video_id = choose_stream(streams['video'], 'video')
    if not video_id:
        print("Exiting... No video selected.")
        return
    
    audio_id = choose_stream(streams['audio'], 'audio')
    if not audio_id:
        print("Exiting... No audio selected.")
        return

    # Download the chosen video and audio streams
    print(f"\nDownloading video {video_id} and audio {audio_id}...")
    ydl_opts = {
        'format': f'{video_id}+{audio_id}',
        'outtmpl': '%(title)s.%(ext)s',
        'progress_hooks': [lambda d: print(d)]
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

if __name__ == "__main__":
    main()
