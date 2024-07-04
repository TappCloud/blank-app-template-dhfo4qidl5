import streamlit as st
import subprocess
import signal
import socket
import re

# Global variable to store the FFmpeg process
ffmpeg_process = None

# Function to resolve the hostname to an IP address
def resolve_hostname(url):
    if url.startswith('rtmp://') or url.startswith('rtmps://'):
        protocol, rest = url.split('://', 1)
        hostname = rest.split('/')[0]
        try:
            ip = socket.gethostbyname(hostname)
            resolved_url = url.replace(hostname, ip)
            return resolved_url, None
        except socket.gaierror:
            return None, f"Failed to resolve hostname: {hostname}"
    return url, None

# Function to build the FFmpeg command based on user inputs
def build_ffmpeg_command(video_url, logo_url, overlay_settings, enable_logo, resolution, rtmp_url, fps, audio_option):
    # Convert resolution label to resolution string
    resolution_map = {
        "720p": "1280x720",
        "480p": "854x480",
        "360p": "640x360",
        "180p": "320x180",
        "1080p": "1920x1080",
        "4K": "3840x2160"
    }
    res_str = resolution_map.get(resolution, "1280x720")  # Default to 1280x720 if not found
    
    command = [
        "ffmpeg",
        "-re",
        "-y",
        "-i", video_url,
    ]

    if enable_logo:
        # Constructing filter_complex when logo is enabled
        filter_complex = f"[1]scale=iw*0.6:-1[wm];[0][wm]{overlay_settings}"
        command.extend([
            "-i", logo_url,
            "-filter_complex", filter_complex,
        ])
    
    # Add resolution change if specified
    command.extend(["-s", res_str])

    # Add FPS setting if specified
    if fps:
        command.extend(["-r", str(fps)])

    # Audio settings based on the selected audio option
    if audio_option == "Copy Audio from File":
        command.extend(["-c:a", "copy"])
    else:
        audio_channels, audio_bitrate = audio_option.split('|')
        command.extend([
            "-ac", audio_channels,
            "-b:a", audio_bitrate
        ])

    command.extend([
        "-ar", "44100",        # Audio sample rate
        "-pix_fmt", "yuv420p", # Pixel format
        "-tune", "zerolatency",# Tuning for live streaming
        "-maxrate", "2000k",   # Maximum bitrate
        "-preset", "veryfast", # Encoding preset
        "-vcodec", "libx264",  # Video codec
        "-ab", "128k",         # Audio bitrate (default)
        "-vb", "660k",         # Video bitrate
        "-f", "flv",           # Format
        rtmp_url                # Output RTMP URL
    ])

    # Return the command as a string for the Textarea field
    return command, ' '.join(command)

# Function to start the FFmpeg process
def start_ffmpeg(video_url, logo_url, overlay_settings, enable_logo, resolution, rtmp_url, fps, audio_option):
    global ffmpeg_process
    resolved_rtmp_url, error = resolve_hostname(rtmp_url)
    if error:
        return error, "", ""

    command, command_str = build_ffmpeg_command(video_url, logo_url, overlay_settings, enable_logo, resolution, resolved_rtmp_url, fps, audio_option)
    
    try:
        if ffmpeg_process and ffmpeg_process.poll() is None:
            return "A stream is already running. Please stop the current stream before starting a new one.", "", command_str

        # Start a new FFmpeg process
        ffmpeg_process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = "Command executed successfully."

        # Capture and display FFmpeg logs
        logs = []
        for line in iter(ffmpeg_process.stderr.readline, ''):
            if line:
                logs.append(line.strip())
            if not line:  # Check if the stream has ended
                break
        
        if ffmpeg_process.poll() is None:
            output += "\nStreaming in progress..."
        return output, "\n".join(logs), command_str
        
    except Exception as e:
        return f"An error occurred: {e}", "", command_str

# Function to stop the FFmpeg process
def stop_ffmpeg():
    global ffmpeg_process
    if ffmpeg_process:
        try:
            # Send SIGINT to the FFmpeg process to stop it gracefully
            ffmpeg_process.send_signal(signal.SIGINT)
            # Wait for the process to exit
            ffmpeg_process.wait(timeout=10)
            output = "Stream stopped."
        except subprocess.TimeoutExpired:
            output = "Stopping the stream took too long. Forcing termination."
            ffmpeg_process.kill()  # Forcefully terminate the process
            ffmpeg_process.wait()  # Ensure the process exits
        except Exception as e:
            output = f"An error occurred while stopping the stream: {e}"
        finally:
            ffmpeg_process = None
    else:
        output = "No stream is running."
    
    return output

# Function to check FFmpeg protocols
def check_ffmpeg_protocols():
    try:
        result = subprocess.run(['ffmpeg', '-protocols'], stdout=subprocess.PIPE, text=True)
        if 'rtmps' in result.stdout:
            return "RTMPS is supported by this FFmpeg build."
        else:
            return "RTMPS is not supported by this FFmpeg build."
    except Exception as e:
        return f"An error occurred while checking FFmpeg protocols: {e}"

# Streamlit Interface
st.title("FFmpeg Command Control Dashboard")

st.markdown("### Input Fields")
video_url = st.text_input("Video URL", "https://kbsworld-ott.akamaized.net/hls/live/2002341/kbsworld/master.m3u8")
rtmp_url = st.text_input("RTMP Output URL", "rtmps://stream.livepush.io/live/rtmp_8a7a6cd917914f46ba816a72ecdb2454")

st.markdown("### Settings")
resolution = st.selectbox("Select Stream Resolution", ["4K", "1080p", "720p", "480p", "360p", "180p"], index=2)
fps = st.selectbox("Select Video FPS", [24, 30, 60], index=1)
audio_option = st.selectbox("Audio Options", ["Copy Audio from File", "1|128k", "2|128k", "2|256k"], index=0)

st.markdown("### Logo Settings")
logo_url = st.text_input("Logo URL", "https://i.ibb.co/YcPZxsn/logo.png")
overlay_settings = st.text_input("Overlay Settings", "overlay=W-w-45:37", placeholder="Set the overlay settings for the logo")
enable_logo = st.checkbox("Enable Logo", value=True)

st.markdown("### Actions")
if st.button("Run Command"):
    output, logs, ffmpeg_command = start_ffmpeg(video_url, logo_url, overlay_settings, enable_logo, resolution, rtmp_url, fps, audio_option)
    st.text_area("Command Output", output, height=100)
    st.text_area("FFmpeg Logs", logs, height=200)
    st.text_area("Generated FFmpeg Command", ffmpeg_command, height=50)

if st.button("Stop Stream"):
    output = stop_ffmpeg()
    st.text_area("Command Output", output, height=100)

if st.button("Check FFmpeg Protocols"):
    protocol_check = check_ffmpeg_protocols()
    st.text_area("FFmpeg Protocol Support", protocol_check, height=50)
