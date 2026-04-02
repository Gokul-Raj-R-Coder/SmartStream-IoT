# SmartStream IoT Hub 🚀....

A universal, low-latency telemetry dashboard for remote industrial monitoring and medical imaging. 
Designed to run cross-platform on both Windows (Prototyping) and Embedded Linux (Edge Deployment).

## ⚡ Key Features
* **Ultra-Low Latency:** <300ms glass to glass streaming via WebRTC/RTSP.
* **Cross-Platform Engine:** Auto-detects OS to switch between Webcam (Windows) and MIPI CSI Sensors (Linux/Verdin).
* **Decoupled Architecture:** Separation of concerns between the GStreamer video pipeline and the Python control logic.
* **Digital Twin Dashboard:** Browser based interface for remote device control (GPIO simulation).

## 🛠️ Tech Stack
* **Language:** Python 3.10+
* **Backend:** FastAPI (Async)
* **Video Engine:** GStreamer + MediaMTX
* **Computer Vision:** OpenCV
* **Protocol:** RTSP -> WebRTC

## 🚀 How to Run
1.  Install dependencies: `pip install -r requirements.txt`
2.  Download the [MediaMTX binary](https://github.com/bluenviron/mediamtx/releases) for your OS.
3.  Run the hub: `python main.py`
4.  Open `http://localhost:8000` in your browser.
