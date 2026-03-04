import subprocess
import sys
import os
import signal
import socket
import uvicorn
import cv2
import time
import glob
import platform
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

# --- PROJECT CONFIGURATION ---
# A Universal Low-Latency Streaming Hub for IoT Devices
PROJECT_NAME = "SmartStream IoT Hub"
RTSP_PORT = "8554"
WEBRTC_PORT = "8889"
WEB_SERVER_PORT = 8000
CAPTURE_DIR = "captures"

# --- OS DETECTION & HARDWARE PROFILES ---
OS_TYPE = platform.system() # 'Windows' or 'Linux'

if OS_TYPE == "Windows":
    MEDIAMTX_BIN = "mediamtx.exe"
    # Windows Pipeline: Webcam Source + Time Overlay + Text Overlay
    GST_PIPELINE_TEMPLATE = (
        "gst-launch-1.0 mfvideosrc ! "
        "videoconvert ! "
        "timeoverlay valignment=bottom halignment=right font-desc='Consolas, 20' shaded-background=true ! "
        "textoverlay text='CAM-01 | LIVE' valignment=top halignment=left font-desc='Consolas, 20' shaded-background=true ! "
        "x264enc bitrate=4000 tune=zerolatency speed-preset=superfast key-int-max=15 bframes=0 ! "
        "h264parse config-interval=1 ! "
        "rtspclientsink location=rtsp://{ip}:{port}/live protocols=tcp"
    )
else:
    # Linux / Embedded Pipeline (e.g., Raspberry Pi / Jetson / Verdin)
    MEDIAMTX_BIN = "./mediamtx"
    GST_PIPELINE_TEMPLATE = (
        "gst-launch-1.0 v4l2src device=/dev/video0 ! "
        "video/x-raw,width=1920,height=1080 ! "
        "v4l2h264enc bitrate=5000000 ! "
        "h264parse config-interval=1 ! "
        "rtspclientsink location=rtsp://{ip}:{port}/live protocols=tcp"
    )

# --- SETUP STORAGE ---
if not os.path.exists(CAPTURE_DIR):
    os.makedirs(CAPTURE_DIR)
    print(f"[SYSTEM] Storage initialized: {CAPTURE_DIR}/")

# --- GLOBAL PROCESSES ---
processes = {}

def get_lan_ip():
    """Auto-detects the device's IP address on the local network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

LAN_IP = get_lan_ip()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n[SYSTEM] Starting {PROJECT_NAME} on {LAN_IP} ({OS_TYPE} Mode)...\n")

    # 1. Start RTSP Server
    if os.path.exists(MEDIAMTX_BIN):
        processes['mtx'] = subprocess.Popen(
            [MEDIAMTX_BIN], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    else:
        print(f"[ERROR] {MEDIAMTX_BIN} binary not found.")

    # 2. Start Video Pipeline
    final_cmd = GST_PIPELINE_TEMPLATE.format(ip=LAN_IP, port=RTSP_PORT)
    print(f"[PROCESS] Initializing GStreamer Pipeline...")
    processes['gst'] = subprocess.Popen(final_cmd, shell=True)
    
    yield
    
    # --- CLEANUP ---
    print("\n[SYSTEM] Shutting down services...")
    if 'gst' in processes: 
        if OS_TYPE == "Windows":
             subprocess.call(['taskkill', '/F', '/T', '/PID', str(processes['gst'].pid)])
        else:
             processes['gst'].kill()
    if 'mtx' in processes: 
        processes['mtx'].kill()

app = FastAPI(lifespan=lifespan)
app.mount("/captures", StaticFiles(directory=CAPTURE_DIR), name="captures")

# --- IOT DASHBOARD UI ---
html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{PROJECT_NAME}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{ --primary: #00f2ff; --bg: #0a0a0a; --panel: #141414; --text: #e0e0e0; }}
        body {{ font-family: 'Roboto Mono', monospace; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        
        /* HEADER */
        header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }}
        h1 {{ font-size: 18px; margin: 0; color: var(--primary); }}
        .status-badge {{ background: #1a3a1a; color: #4caf50; padding: 5px 10px; border-radius: 4px; font-size: 12px; }}

        /* TABS */
        .tabs {{ display: flex; gap: 2px; margin-bottom: 20px; background: #333; padding: 2px; border-radius: 6px; }}
        .tab-btn {{ 
            flex: 1; padding: 12px; background: var(--panel); border: none; 
            color: #666; font-family: inherit; font-weight: bold; cursor: pointer; transition: 0.2s;
        }}
        .tab-btn.active {{ background: var(--primary); color: black; }}
        .tab-btn:first-child {{ border-radius: 4px 0 0 4px; }}
        .tab-btn:last-child {{ border-radius: 0 4px 4px 0; }}
        
        /* VIEWS */
        .view {{ display: none; animation: fadeIn 0.3s; }}
        .view.active {{ display: block; }}
        @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}

        /* VIDEO FEED */
        .video-wrapper {{
            position: relative; width: 100%; padding-bottom: 56.25%;
            background: #000; border: 1px solid #333; border-radius: 8px; overflow: hidden;
            box-shadow: 0 0 20px rgba(0, 242, 255, 0.1);
        }}
        iframe {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: none; }}
        
        /* CONTROLS */
        .controls {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-top: 20px; }}
        .btn {{ 
            padding: 20px; font-family: inherit; font-size: 14px; font-weight: bold; 
            border: 1px solid #333; background: var(--panel); color: var(--text); 
            border-radius: 6px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 10px;
            transition: all 0.2s;
        }}
        .btn:hover {{ border-color: var(--primary); color: var(--primary); }}
        .btn:active {{ transform: scale(0.98); background: #222; }}
        .btn-snap {{ grid-column: span 2; background: #1a1a1a; border-color: var(--primary); color: var(--primary); }}

        /* GALLERY */
        .gallery-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }}
        .gallery-item {{ position: relative; border: 1px solid #333; border-radius: 4px; overflow: hidden; transition: 0.2s; }}
        .gallery-item:hover {{ border-color: var(--primary); transform: translateY(-2px); }}
        .gallery-item img {{ width: 100%; display: block; }}
        .gallery-item .timestamp {{
            position: absolute; bottom: 0; left: 0; width: 100%;
            background: rgba(0,0,0,0.8); color: var(--primary); font-size: 10px; padding: 5px;
        }}

        /* LOGS */
        .console {{ 
            margin-top: 20px; background: #000; padding: 10px; border-radius: 4px; 
            border-left: 3px solid var(--primary); font-size: 12px; color: #888; 
            height: 30px; line-height: 30px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{PROJECT_NAME}</h1>
            <span class="status-badge">SYSTEM ONLINE</span>
        </header>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('live')">TELEMETRY</button>
            <button class="tab-btn" onclick="switchTab('gallery')">DATA LOGS</button>
        </div>

        <div id="live" class="view active">
            <div class="video-wrapper">
                <iframe src="http://{LAN_IP}:{WEBRTC_PORT}/live" scrolling="no"></iframe>
            </div>
            <div class="controls">
                <button class="btn" onclick="sendCommand('/io/light')"><span>💡</span> TOGGLE SPOTLIGHT</button>
                <button class="btn" onclick="sendCommand('/io/ir')"><span>👁️</span> IR / NIGHT MODE</button>
                <button class="btn btn-snap" onclick="sendCommand('/capture')"><span>📸</span> CAPTURE SNAPSHOT</button>
            </div>
            <div id="log" class="console">Waiting for command...</div>
        </div>

        <div id="gallery" class="view">
            <div id="gallery-container" class="gallery-grid"></div>
        </div>
    </div>

    <script>
        function switchTab(tabName) {{
            document.querySelectorAll('.view').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            
            const buttons = document.querySelectorAll('.tab-btn');
            if(tabName === 'live') buttons[0].classList.add('active');
            if(tabName === 'gallery') {{
                buttons[1].classList.add('active');
                loadGallery();
            }}
        }}

        async function sendCommand(endpoint) {{
            const log = document.getElementById('log');
            log.innerText = "> Sending signal...";
            log.style.color = "#fff";
            try {{
                const response = await fetch(endpoint, {{ method: 'POST' }});
                const data = await response.json();
                log.innerText = "> ACK: " + data.status;
                log.style.color = "#00f2ff";
            }} catch (e) {{
                log.innerText = "> ERR: Device unreachable";
                log.style.color = "red";
            }}
        }}

        async function loadGallery() {{
            const container = document.getElementById('gallery-container');
            container.innerHTML = '<div style="color:#666; padding:20px;">Fetching logs...</div>';
            try {{
                const response = await fetch('/api/captures');
                const images = await response.json();
                container.innerHTML = ''; 
                if (images.length === 0) {{
                    container.innerHTML = '<div style="color:#444; padding:20px;">No Data Found</div>';
                    return;
                }}
                images.forEach(img => {{
                    const div = document.createElement('div');
                    div.className = 'gallery-item';
                    div.innerHTML = `<a href="/captures/${{img}}" target="_blank"><img src="/captures/${{img}}" loading="lazy"></a><div class="timestamp">${{img}}</div>`;
                    container.appendChild(div);
                }});
            }} catch (e) {{
                container.innerHTML = 'Error loading data.';
            }}
        }}
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return html_content

# --- API ENDPOINTS ---
@app.get("/api/captures")
async def get_images():
    files = glob.glob(f"{CAPTURE_DIR}/*.jpg")
    files.sort(key=os.path.getmtime, reverse=True)
    return [os.path.basename(f) for f in files]

@app.post("/io/light")
async def toggle_light():
    print("[IOT] GPIO: Light Toggled")
    return {"status": "SPOTLIGHT STATE CHANGED"}

@app.post("/io/ir")
async def toggle_ir():
    print("[IOT] GPIO: IR Filter Toggled")
    return {"status": "IR FILTER ACTUATED"}

@app.post("/capture")
async def take_snapshot():
    print("[IOT] Capturing Frame...")
    rtsp_url = f"rtsp://{LAN_IP}:{RTSP_PORT}/live"
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened(): return {"status": "ERROR: SENSOR OFFLINE"}
    
    # Flush buffer for latest frame
    for _ in range(5): cap.read()
    ret, frame = cap.read()
    cap.release()
    
    if ret:
        timestamp = int(time.time())
        filename = f"log_{timestamp}.jpg"
        cv2.imwrite(os.path.join(CAPTURE_DIR, filename), frame)
        return {"status": f"DATA SAVED: {filename}"}
    return {"status": "CAPTURE FAILED"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEB_SERVER_PORT)