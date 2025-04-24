from picamera2 import Picamera2
from flask import Flask, Response, jsonify
import cv2
from ultralytics import YOLO
import threading
import time
import json

# Initialize Flask app
app = Flask(_name_)

# Initialize and configure the camera
camera = Picamera2()
camera.configure(camera.create_preview_configuration(main={"format": "RGB888", "size": (640, 480)}))
camera.start()

# Load the YOLOv8 model
model = YOLO("yolov8n.pt")

# Global variables
frame = None
person_detected = False
lock = threading.Lock()

def capture_frames():
    global frame, person_detected
    while True:
        with lock:
            raw_frame = camera.capture_array()
            frame_bgr = cv2.cvtColor(raw_frame, cv2.COLOR_RGB2BGR)
            
            # Run YOLO inference
            results = model.predict(source=frame_bgr, conf=0.5, stream=False, classes=[0])  # Class 0 is person in COCO dataset
            
            # Reset person detection flag
            person_detected = False
            
            # Draw bounding boxes and labels for detected persons
            for result in results[0].boxes:
                x1, y1, x2, y2 = map(int, result.xyxy[0])
                confidence = result.conf[0]
                
                person_detected = True
                # Draw red box for detected person
                cv2.rectangle(frame_bgr, (x1, y1), (x2, y2), (0, 0, 255), 2)
                cv2.putText(frame_bgr, f"Person {confidence:.2f}", (x1, y1 - 10),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            frame = frame_bgr
        time.sleep(0.01)

# Start the capture thread
capture_thread = threading.Thread(target=capture_frames, daemon=True)
capture_thread.start()

def generate_frames():
    while True:
        with lock:
            if frame is None:
                continue
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), 
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/check_person')
def check_person():
    """Endpoint to check if a person is detected."""
    global person_detected
    return jsonify({"person_detected": person_detected})

@app.route('/')
def index():
    return '''
    <html>
    <head>
        <title>Person Detection Camera</title>
        <script>
            let lastAlertTime = 0;
            const ALERT_COOLDOWN = 5000; // 5 seconds cooldown between alerts
            
            function checkForPerson() {
                fetch('/check_person')
                    .then(response => response.json())
                    .then(data => {
                        const currentTime = Date.now();
                        if (data.person_detected && 
                            (currentTime - lastAlertTime) > ALERT_COOLDOWN) {
                            #alert("âš ï¸ Person Detected! âš ï¸");
                            lastAlertTime = currentTime;
                        }
                    })
                    .catch(error => console.error('Error:', error));
            }
            
            // Check for person detection every second
            setInterval(checkForPerson, 1000);
        </script>
    </head>
    <body>
        <h1>Person Detection Camera</h1>
        <img src="/video_feed">
    </body>
    </html>
    '''

if _name_ == "_main_":
    app.run(host='0.0.0.0', port=5000, threaded=True)
