import os
import subprocess
import shutil
from pathlib import Path

import json
import time
import hashlib
import datetime
import urllib.request
import urllib.error

# Import tkinter for file dialogs
try:
    import tkinter as tk
    from tkinter import filedialog
    HAS_TKINTER = True
except ImportError:
    HAS_TKINTER = False
    print("Warning: tkinter not available. Using command line input instead.")


# =========================
# Simple License / Kill-Switch
# =========================
# Free approach: host a small JSON file somewhere you control (e.g., GitHub raw file).
# If you set "enabled": false, the script stops working for everyone on next online check.
#
# SECURITY NOTE:
# If you give someone the .py source, they can remove this check.
# For more control, share a packaged .exe (PyInstaller) instead of the source.

LICENSE_REGISTRY_URL = os.environ.get(
    "VIDEO_SPLITTER_LICENSE_URL",
    "https://github.com/AbdurrehmanM018/Videos_splitter/blob/main/video_splitter_license.json"  # <-- replace with your URL
)

GRACE_DAYS_OFFLINE = int(os.environ.get("VIDEO_SPLITTER_GRACE_DAYS", "3"))
CACHE_PATH = Path.home() / ".video_splitter_license_cache.json"

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_cache(data: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def _parse_yyyy_mm_dd(d: str):
    try:
        return datetime.datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        return None

def _fetch_registry(url: str, timeout: int = 6) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "video-splitter-license-check/1.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return json.loads(raw)

def verify_license_or_exit() -> None:
    # Provide license key via environment variable for convenience:
    #   set VIDEO_SPLITTER_KEY=YOUR_KEY   (Windows)
    #   export VIDEO_SPLITTER_KEY=YOUR_KEY (macOS/Linux)
    key = os.environ.get("VIDEO_SPLITTER_KEY")
    if not key:
        key = input("🔐 Enter license key: ").strip()
    key = (key or "").strip()
    if not key:
        print("❌ No license key provided.")
        raise SystemExit(1)

    key_hash = _sha256_hex(key)

    # Online validation (preferred)
    try:
        reg = _fetch_registry(LICENSE_REGISTRY_URL)
        if not reg.get("enabled", True):
            print("⛔ This script is currently disabled by the author.")
            raise SystemExit(1)

        keys = reg.get("keys", {})  # dict of sha256(key) -> info
        info = keys.get(key_hash)
        if not info:
            print("❌ Invalid license key.")
            raise SystemExit(1)

        exp = info.get("expires")
        if exp:
            exp_d = _parse_yyyy_mm_dd(exp)
            if exp_d and datetime.date.today() > exp_d:
                print("❌ License expired.")
                raise SystemExit(1)

        _save_cache({"key_hash": key_hash, "last_ok": time.time()})
        name = info.get("name") or "user"
        print(f"✅ License OK. Welcome, {name}!")
        return

    except Exception:
        # Offline fallback: allow short grace period
        cache = _load_cache()
        last_ok = float(cache.get("last_ok") or 0)
        cached_hash = cache.get("key_hash")

        max_age = GRACE_DAYS_OFFLINE * 86400
        if cached_hash == key_hash and (time.time() - last_ok) <= max_age:
            print("✅ License cached (offline grace mode).")
            return

        print("❌ Could not validate license online and no valid cache found.")
        print("   (Check internet OR ask the author to re-enable/renew your key.)")
        raise SystemExit(1)


def select_video_file():
    """Open file dialog to select video file"""
    if not HAS_TKINTER:
        return input("Enter the path to your video file: ").strip().strip('"')
    
    root = tk.Tk()
    root.withdraw()
    
    video_file = filedialog.askopenfilename(
        title="Select Video File",
        filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
            ("All files", "*.*")
        ]
    )
    
    root.destroy()
    return video_file

def select_destination_folder():
    """Open folder dialog to select destination"""
    if not HAS_TKINTER:
        folder = input("Enter destination folder path: ").strip().strip('"')
        return folder if folder else os.getcwd()
    
    root = tk.Tk()
    root.withdraw()
    
    destination_folder = filedialog.askdirectory(
        title="Select Destination Folder"
    )
    
    root.destroy()
    return destination_folder if destination_folder else os.getcwd()

def ask_skip_interval():
    """Ask user to choose skip interval"""
    print("\n⏱️  Choose interval between clips:")
    print("  1. 10 seconds (more clips, better coverage)")
    print("  2. 15 seconds (good balance)")
    print("  3. 20 seconds (moderate coverage)")
    print("  4. 30 seconds (fewer clips, faster processing)")
    
    intervals = {1: 10, 2: 15, 3: 20, 4: 30}
    
    while True:
        try:
            choice = int(input("Enter choice (1-4): ").strip())
            if choice in intervals:
                selected_interval = intervals[choice]
                print(f"✅ Selected: {selected_interval} second intervals")
                return selected_interval
            else:
                print("Please enter a number between 1 and 4")
        except ValueError:
            print("Please enter a valid number (1-4)")

def ask_motion_detection():
    """Ask user if they want to use motion detection"""
    while True:
        choice = input("\n🎬 Use motion detection to skip static scenes? (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            print("✅ Motion detection enabled - will skip completely static scenes only")
            print("📝 Note: Uses frame comparison (more reliable than scene detection)")
            return True
        elif choice in ['n', 'no']:
            print("✅ Motion detection disabled - will use regular intervals")
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no")

def ask_delete_temp_folder():
    """Ask user if they want to delete the temp folder"""
    while True:
        choice = input("\n🗑️  Delete temp folder after processing? (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        else:
            print("Please enter 'y' for yes or 'n' for no")

def check_ffmpeg():
    """Check if FFmpeg is installed"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_video_duration(video_path):
    """Get video duration in seconds"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-show_entries', 'format=duration', 
            '-of', 'csv=p=0', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except:
        return None

def get_motion_score(input_video, start_time, duration=2):
    """Get motion score for a video segment using simple frame difference analysis"""
    try:
        # Extract a few frames and check for differences
        # This is much more reliable than complex scene detection
        temp_frame1 = "temp_frame1.jpg"
        temp_frame2 = "temp_frame2.jpg"
        
        # Get frame at start
        cmd1 = [
            'ffmpeg', '-ss', str(start_time), '-i', input_video,
            '-frames:v', '1', '-q:v', '10', '-y', temp_frame1
        ]
        
        # Get frame 1 second later
        cmd2 = [
            'ffmpeg', '-ss', str(start_time + 1), '-i', input_video,
            '-frames:v', '1', '-q:v', '10', '-y', temp_frame2
        ]
        
        # Execute commands quietly
        subprocess.run(cmd1, capture_output=True, text=True, timeout=10)
        subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
        
        # Check if both frames exist and have different sizes (indicating motion)
        motion_score = 0
        if os.path.exists(temp_frame1) and os.path.exists(temp_frame2):
            size1 = os.path.getsize(temp_frame1)
            size2 = os.path.getsize(temp_frame2)
            
            # If file sizes differ significantly, there's likely motion
            size_diff = abs(size1 - size2) / max(size1, size2, 1)
            
            if size_diff > 0.1:  # 10% difference indicates motion
                motion_score = 2
            elif size_diff > 0.05:  # 5% difference indicates some motion
                motion_score = 1
            else:
                motion_score = 0
        
        # Cleanup temp files
        for temp_file in [temp_frame1, temp_frame2]:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
        
        return motion_score
        
    except:
        # If motion detection fails, assume there IS motion (safer default)
        return 1

def extract_keyframe_clips(input_video, temp_folder, skip_interval=30, use_motion_detection=False):
    """Extract ~2s keyframe clips with configurable intervals and optional motion detection"""
    
    # Get video duration
    total_duration = get_video_duration(input_video)
    if total_duration is None:
        print("❌ Could not get video duration")
        return False
    
    print(f"📹 Video duration: {total_duration:.1f} seconds")
    print(f"⚙️  Settings: ~2s keyframe clips, skip {skip_interval}s")
    if use_motion_detection:
        print(f"🎬 Motion detection: ON (will skip static scenes)")
        print(f"📝 Note: Using FFmpeg keyframes + motion filtering")
    else:
        print(f"📝 Note: Using FFmpeg keyframes (clips may be 2-4s each for speed)")
    
    # Calculate positions
    current_time = 0
    clip_number = 1
    
    print(f"🔄 Extracting clips every {skip_interval} seconds...")
    
    clip_files = []
    motion_threshold = 0 if use_motion_detection else -1  # Accept any motion (0+) when enabled
    
    while current_time < total_duration:
        
        # Check motion if enabled
        if use_motion_detection:
            motion_score = get_motion_score(input_video, current_time, duration=2)
            # Skip only if motion score is exactly 0 (completely static)
            if motion_score <= 0:
                print(f"  🚫 Clip {clip_number}: {current_time:.1f}s - Static scene (motion: {motion_score}) - Skipping")
                current_time += skip_interval
                clip_number += 1
                continue
        # Output file path
        output_file = os.path.join(temp_folder, f"clip_{clip_number:03d}.mp4")
        
        # FFmpeg command using FAST keyframe cutting
        # -ss before -i for fast seeking to keyframe
        # -t 2 requests 2 seconds, but FFmpeg will cut at next keyframe
        cmd = [
            'ffmpeg',
            '-ss', str(current_time),      # Seek to position (keyframe)
            '-i', input_video,
            '-t', '2',                     # Request ~2 seconds (will cut at keyframe)
            '-c', 'copy',                  # FAST: Copy streams (no re-encoding)
            '-avoid_negative_ts', 'make_zero',
            '-y',
            output_file
        ]
        
        try:
            if use_motion_detection:
                motion_score = get_motion_score(input_video, current_time, duration=2)
                print(f"  📄 Clip {clip_number}: {current_time:.1f}s (motion: {motion_score})", end="")
            else:
                print(f"  📄 Clip {clip_number}: Starting at {current_time:.1f}s", end="")
            
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # Verify clip was created
            if os.path.exists(output_file) and os.path.getsize(output_file) > 1000:
                # Get the actual duration of the created clip
                actual_duration = get_video_duration(output_file)
                if actual_duration:
                    clip_files.append(output_file)
                    print(f" ✅ (actual: {actual_duration:.1f}s)")
                    clip_number += 1
                else:
                    print(" ❌ Could not verify")
                    if os.path.exists(output_file):
                        os.remove(output_file)
            else:
                print(" ❌ Failed to create")
                
        except subprocess.CalledProcessError as e:
            print(f" ❌ Error: {e}")
            continue
        
        # Move to next position (skip interval)
        current_time += skip_interval
    
    print(f"\n📊 Created {len(clip_files)} clips in temp folder")
    
    # Calculate estimated total duration
    if clip_files:
        # Sample first few clips to estimate average duration
        sample_duration = 0
        sample_count = min(5, len(clip_files))
        
        for i in range(sample_count):
            duration = get_video_duration(clip_files[i])
            if duration:
                sample_duration += duration
        
        if sample_count > 0:
            avg_clip_duration = sample_duration / sample_count
            estimated_total = len(clip_files) * avg_clip_duration
            print(f"📊 Average clip duration: {avg_clip_duration:.1f}s")
            print(f"📊 Estimated final duration: {estimated_total:.0f}s ({estimated_total/60:.1f} minutes)")
    
    return len(clip_files) > 0

def combine_clips(temp_folder, output_video):
    """Combine clips under 3 seconds into final muted video (ignore clips over 3s)"""
    
    # Get all clip files
    clip_files = []
    for file in os.listdir(temp_folder):
        if file.endswith('.mp4') and file.startswith('clip_'):
            clip_files.append(os.path.join(temp_folder, file))
    
    if not clip_files:
        print("❌ No clips found to combine!")
        return False, [], []
    
    # Sort clips
    clip_files.sort()
    
    print(f"🔍 Filtering {len(clip_files)} clips (keeping only clips 3 seconds or less)...")
    
    # Filter clips by duration (keep only 3 seconds or less)
    valid_clips = []
    ignored_clips = []
    
    for i, clip_file in enumerate(clip_files):
        duration = get_video_duration(clip_file)
        if duration:
            if duration <= 3.0:
                valid_clips.append(clip_file)
                print(f"  ✅ Clip {i+1}: {duration:.1f}s (keeping)")
            else:
                ignored_clips.append(clip_file)
                print(f"  ❌ Clip {i+1}: {duration:.1f}s (ignoring - over 3s)")
        else:
            print(f"  ❓ Clip {i+1}: Could not get duration (ignoring)")
            ignored_clips.append(clip_file)
    
    if not valid_clips:
        print("❌ No clips 3 seconds or less found!")
        return False, [], ignored_clips
    
    print(f"\n📊 Summary:")
    print(f"  - Valid clips (3s or less): {len(valid_clips)}")
    print(f"  - Ignored clips (over 3s): {len(ignored_clips)}")
    
    # Calculate total duration of valid clips
    total_duration = 0
    for clip_file in valid_clips:
        duration = get_video_duration(clip_file)
        if duration:
            total_duration += duration
    
    print(f"  - Total final duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    
    print(f"\n🔗 Combining {len(valid_clips)} valid clips into final muted video...")
    
    # Create filelist with only valid clips
    filelist_path = os.path.join(temp_folder, "filelist.txt")
    
    try:
        with open(filelist_path, 'w') as f:
            for clip_file in valid_clips:
                relative_path = os.path.relpath(clip_file, temp_folder)
                f.write(f"file '{relative_path}'\n")
        
        print(f"📝 Created filelist with {len(valid_clips)} clips")
        
        # FFmpeg command to concatenate and mute (FAST - copy video)
        cmd = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', filelist_path,
            '-c:v', 'copy',  # FAST: Copy video streams (no re-encoding)
            '-an',           # Remove audio (mute)
            '-y',
            output_video
        ]
        
        print("🎬 Creating final video (FAST - no re-encoding)...")
        result = subprocess.run(cmd, check=True, capture_output=True, cwd=temp_folder)
        
        # Verify final video duration
        final_duration = get_video_duration(output_video)
        if final_duration:
            final_minutes = int(final_duration // 60)
            final_seconds = int(final_duration % 60)
            print(f"✅ Final video created! Duration: {final_minutes}m {final_seconds}s ({final_duration:.1f}s)")
            
            # Show filtering results
            if ignored_clips:
                print(f"📊 Filtered out {len(ignored_clips)} clips over 3 seconds")
                total_ignored_duration = 0
                for clip_file in ignored_clips:
                    duration = get_video_duration(clip_file)
                    if duration:
                        total_ignored_duration += duration
                if total_ignored_duration > 0:
                    print(f"📊 Ignored duration: {total_ignored_duration:.1f}s ({total_ignored_duration/60:.1f} minutes)")
        else:
            print("✅ Final muted video created successfully!")
        
        return True, valid_clips, ignored_clips
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error combining clips: {e}")
        return False, valid_clips, ignored_clips
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False, valid_clips, ignored_clips

def cleanup_temp_folder(temp_folder, delete_temp_folder, ignored_clips):
    """Handle temp folder cleanup based on user choice"""
    
    if delete_temp_folder:
        # Delete entire temp folder
        print("\n🗑️  Deleting temp folder...")
        try:
            shutil.rmtree(temp_folder)
            print("✅ Temp folder deleted completely")
        except Exception as e:
            print(f"⚠️  Could not delete temp folder: {e}")
    else:
        # Keep temp folder but delete ignored clips (over 3s) and filelist
        print(f"\n📁 Keeping temp folder: {temp_folder}")
        
        if ignored_clips:
            print(f"🗑️  Deleting {len(ignored_clips)} clips over 3 seconds...")
            deleted_count = 0
            
            for clip_file in ignored_clips:
                try:
                    if os.path.exists(clip_file):
                        os.remove(clip_file)
                        deleted_count += 1
                        print(f"  ✅ Deleted: {os.path.basename(clip_file)}")
                except Exception as e:
                    print(f"  ❌ Could not delete {os.path.basename(clip_file)}: {e}")
            
            print(f"✅ Deleted {deleted_count} clips over 3 seconds")
        
        # Delete filelist.txt if exists
        filelist_path = os.path.join(temp_folder, "filelist.txt")
        if os.path.exists(filelist_path):
            try:
                os.remove(filelist_path)
                print("✅ Deleted filelist.txt")
            except Exception as e:
                print(f"⚠️  Could not delete filelist.txt: {e}")
        
        # Count remaining valid clips
        remaining_clips = []
        for file in os.listdir(temp_folder):
            if file.endswith('.mp4') and file.startswith('clip_'):
                remaining_clips.append(file)
        
        if remaining_clips:
            print(f"📁 Temp folder contains {len(remaining_clips)} clips (3s or less)")
            print(f"📂 Location: {temp_folder}")
        else:
            print("📁 Temp folder is empty (no valid clips)")

def main():
    print("=" * 60)
    print("    KEYFRAME-BASED VIDEO CLIP PROCESSOR")
    print("  ~2s keyframe clips, skip 30s, muted output")
    print("     (FAST - uses natural keyframe cutting)")
    print("=" * 60)
    
    # Check FFmpeg
    if not check_ffmpeg():
        print("\n❌ FFmpeg not found!")
        print("Install FFmpeg from https://ffmpeg.org/download.html")
        input("Press Enter to exit...")
        return

    # License check (authentication / kill-switch)
    verify_license_or_exit()
    
    # Get video file
    print("\n📂 Select video file...")
    input_video = select_video_file()
    
    if not input_video:
        print("❌ No video file selected!")
        input("Press Enter to exit...")
        return
    
    if not os.path.exists(input_video):
        print(f"❌ Video file not found: {input_video}")
        input("Press Enter to exit...")
        return
    
    print(f"✅ Selected: {os.path.basename(input_video)}")
    
    # Get destination folder
    print("\n📁 Select destination folder...")
    destination = select_destination_folder()
    
    if not destination:
        destination = os.getcwd()
    
    print(f"✅ Destination: {destination}")
    
    # Get user preferences
    skip_interval = ask_skip_interval()
    use_motion_detection = ask_motion_detection()
    delete_temp = ask_delete_temp_folder()
    
    # Show video info
    duration = get_video_duration(input_video)
    if duration:
        minutes = int(duration // 60)
        seconds = int(duration % 60)
        print(f"\n📹 Video length: {minutes}m {seconds}s")
        
        # Estimate clips with new interval
        estimated_clips = int(duration // skip_interval) + (1 if duration % skip_interval > 0 else 0)
        print(f"📊 Estimated clips: ~{estimated_clips} (every {skip_interval}s)")
        
        if use_motion_detection:
            print(f"📊 Expected clips: ~{int(estimated_clips * 0.6)}-{int(estimated_clips * 0.8)} (after filtering static scenes)")
        
        print(f"📊 Each clip: ~2-4s (depends on keyframes)")
        print(f"📊 Total estimated duration: ~{estimated_clips * 3:.0f}s ({estimated_clips * 3 / 60:.1f} minutes) MAX")
    
    # Create temp folder
    video_name = Path(input_video).stem
    temp_folder = os.path.join(destination, "temp_clips")
    final_video = os.path.join(destination, f"{video_name}_keyframe_highlights.mp4")
    
    # Clean temp folder if exists
    if os.path.exists(temp_folder):
        try:
            shutil.rmtree(temp_folder)
        except:
            pass
    
    try:
        # Create temp folder
        os.makedirs(temp_folder, exist_ok=True)
        print(f"\n📂 Created temp folder: {temp_folder}")
        
        print("\n" + "=" * 50)
        if use_motion_detection:
            print("PROCESSING (KEYFRAME + MOTION DETECTION - SMART)...")
        else:
            print("PROCESSING (KEYFRAME MODE - FAST)...")
        print("=" * 50)
        
        # Step 1: Extract keyframe clips
        if extract_keyframe_clips(input_video, temp_folder, skip_interval, use_motion_detection):
            
            # Step 2: Combine clips
            success, valid_clips, ignored_clips = combine_clips(temp_folder, final_video)
            
            if success:
                # Step 3: Handle temp folder cleanup
                cleanup_temp_folder(temp_folder, delete_temp, ignored_clips)
                
                # Show results
                print("\n" + "=" * 60)
                print("🎉 SUCCESS!")
                print(f"📹 Final video: {os.path.basename(final_video)}")
                print(f"📁 Location: {destination}")
                
                # Show file info
                try:
                    size_mb = os.path.getsize(final_video) / (1024*1024)
                    print(f"📊 File size: {size_mb:.1f} MB")
                    
                    final_duration = get_video_duration(final_video)
                    if final_duration and duration:
                        compression = (final_duration / duration) * 100
                        print(f"📊 Compression: {compression:.1f}% of original")
                        time_saved = duration - final_duration
                        saved_minutes = int(time_saved // 60)
                        saved_seconds = int(time_saved % 60)
                        print(f"📊 Time saved: {saved_minutes}m {saved_seconds}s")
                except:
                    pass
                
                print("🔇 Audio: Muted")
                print("⚙️  Method: Keyframe-based (FAST)")
                if use_motion_detection:
                    print("🎬 Motion detection: Used to skip static scenes")
                print("📝 Note: Clips are natural keyframe lengths (~2-4s each)")
                print("⚖️  Copyright: All clips ≤3 seconds for fair use")
                
                if not delete_temp and os.path.exists(temp_folder):
                    print(f"📁 Temp folder preserved with valid clips only")
                
            else:
                print("\n❌ Failed to combine clips!")
        else:
            print("\n❌ Failed to extract clips!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    finally:
        # Emergency cleanup if something went wrong and user chose to delete
        if delete_temp and os.path.exists(temp_folder):
            try:
                shutil.rmtree(temp_folder)
                print("🗑️  Emergency cleanup: Temp folder deleted")
            except:
                print("⚠️  Could not perform emergency cleanup")
    
    input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
