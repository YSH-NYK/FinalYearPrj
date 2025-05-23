import os
import cv2
import numpy as np
import pandas as pd
from datetime import datetime
from flask import Flask,Response, jsonify
from flask_cors import CORS
import csv
from deepface import DeepFace
import pytesseract
import re
import time

app = Flask(__name__)
CORS(app) 

# Directory paths
faces_directory = "static/faces"
attendance_directory = "Attendance"
if not os.path.exists(faces_directory):
    os.makedirs(faces_directory)
if not os.path.exists(attendance_directory):
    os.makedirs(attendance_directory)

def get_date_today():
    return datetime.now().strftime("%Y-%m-%d")

# Helper function to save attendance
def save_attendance(name, roll):
    filename = f"{attendance_directory}/Attendance-{get_date_today()}.csv"
    if not os.path.isfile(filename):
        df = pd.DataFrame(columns=["Name", "Roll", "Time"])
    else:
        df = pd.read_csv(filename)
    if roll not in df["Roll"].values:
        now = datetime.now().strftime("%H:%M:%S")
        df = pd.concat([df, pd.DataFrame([[name, roll, now]], columns=["Name", "Roll", "Time"])])
        df.to_csv(filename, index=False)

def resize_and_crop_face(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    for (x, y, w, h) in faces:
        face = img[y:y+h, x:x+w]
        return cv2.resize(face, (160, 160))
    return None

class LocalOCRScanner:
    def __init__(self, tesseract_path, tessdata_path):
        """Initialize scanner with local Tesseract paths."""
        self.tesseract_path = tesseract_path
        self.tessdata_path = tessdata_path
        
        # Configure Tesseract path
        pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        
        # Verify Tesseract installation
        self._verify_installation()
    
    def _verify_installation(self):
        """Verify Tesseract installation and data files."""
        if not os.path.exists(self.tesseract_path):
            raise FileNotFoundError(f"Tesseract executable not found at: {self.tesseract_path}")
        
        if not os.path.exists(self.tessdata_path):
            raise FileNotFoundError(f"Tessdata directory not found at: {self.tessdata_path}")
            
        eng_data = os.path.join(self.tessdata_path, 'eng.traineddata')
        if not os.path.exists(eng_data):
            raise FileNotFoundError(f"English language data not found at: {eng_data}")

    def preprocess_image(self, frame):
        """Preprocess image for better OCR results."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        threshold = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        
        # Apply denoising
        denoised = cv2.fastNlMeansDenoising(threshold)
        
        return denoised

    def extract_uid(self, card_type, text):
        """Extract UID and formatted name based on card type."""
        match = None
        if card_type == 1:  # Student ID
            match = re.search(r'\b\d{9}\b', text)
        elif card_type == 2:  # Aadhar
            match = re.search(r'\b\d{4}\s?\d{4}\s?\d{4}\b', text)
        elif card_type == 3:  # PAN Card
            match = re.search(r'\b[A-Z]{5}\d{4}[A-Z]\b', text)
        elif card_type == 4:  # Driving License
            match = re.search(r'\b[A-Z]{2}\d{2}\s?\d{11}\b', text)

        return match.group(0) if match else None


@app.route('/api/register-face', methods=['POST'])
def register_face():
    tesseract_path = r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    tessdata_path = r"C:\\Program Files\\Tesseract-OCR\\tessdata"

    try:
        scanner = LocalOCRScanner(tesseract_path, tessdata_path)
    except FileNotFoundError as e:
        print(f"Setup Error: {str(e)}")
        print("\nPlease ensure:")
        print("Tesseract is installed from https://github.com/UB-Mannheim/tesseract/wiki")
        return 
    
    # Initialize video capture
    cap = cv2.VideoCapture(1)

    print("Choose the type of ID card:")
    print("1. Student ID")
    print("2. Aadhar")
    print("3. PAN Card")
    print("4. Driving License")
    
   
    card_type = int(input("Enter your choice (1-4): "))
    if card_type not in [1, 2, 3, 4]:
         print("Invalid choice. Please select a valid option.")

    
    last_ocr_time = time.time()
    ocr_interval = 1.0  # Perform OCR every 1 second
    last_result = None
    font = cv2.FONT_HERSHEY_SIMPLEX
    
    # Configure Tesseract parameters
    custom_config = r'--oem 3 --psm 6'
    
    print("\nControls:")
    print("Press 'q' to quit")
    print("Press 'r' to reset last detected ID")
    print("\nScanning for ID cards...")

    while True:
        frame = cap.read()
        
        # Create a copy for display
        display_frame = frame.copy()

        # Perform OCR at intervals
        current_time = time.time()
        if current_time - last_ocr_time >= ocr_interval:
            try:
                # Preprocess the frame
                processed_frame = scanner.preprocess_image(frame)
                
                # Perform OCR
                text = pytesseract.image_to_string(processed_frame, config=custom_config)
                name=''
                print(text)
                # Extract UID
                result = scanner.extract_uid(card_type, text)
                if result:
                    if result != last_result:
                        print(f"Found new ID: {result}")
                    last_result = result
            except Exception as e:
                print(f"OCR Error: {str(e)}")
            
            last_ocr_time = current_time

        # Display results
        if last_result:
            cv2.putText(display_frame, f"ID: {last_result}", (10, 30), font, 1, (0, 255, 0), 2)
        else:
            cv2.putText(display_frame, "Scanning...", (10, 30), font, 1, (0, 0, 255), 2)

        # Add guide rectangle
        h, w = display_frame.shape[:2]
        cv2.rectangle(display_frame, (w//4, h//4), (3*w//4, 3*h//4), (0, 255, 0), 2)
        
        # Display the frame
        cv2.imshow("ID Scanner", display_frame)

        # Handle key presses
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            print("Exiting...")
            break
        elif key == ord('r'):
            last_result = None
            print("Reset - scanning for new ID...")

    cap.release()
    cv2.destroyAllWindows()
    new_username = "Yash"
    new_userid = last_result
    
    if new_username and new_userid:
        img_count =0
        user_folder = os.path.join(faces_directory, f"{new_username}_{new_userid}")
        if not os.path.exists(user_folder):
            os.makedirs(user_folder)
        
        # Start capturing images
        cap = cv2.VideoCapture(0)
        count = 0
        captured_images = []
        
        while count < 5:  # Capture 5 images
            ret, frame = cap.read()
            if ret:
                face = resize_and_crop_face(frame)
                if face is not None:
                    image_path = os.path.join(user_folder, f"{new_username}_{img_count}.jpg")
                    cv2.imwrite(image_path, face)
                    captured_images.append(image_path)
                    count += 1
                    img_count+=1
                cv2.imshow("Capturing Faces", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        
        # Train model on captured images
        if captured_images:
            DeepFace.find(img_path=captured_images[0], db_path=faces_directory)
        
        return jsonify({
            'success': True,
            'userName': new_username,
            'userImages': len(captured_images)
        })
    
    return jsonify({'success': False, 'message': 'Registration failed'})

@app.route("/api/Authenticate", methods=["POST"])
def authenticate():
    try:
        cap = cv2.VideoCapture(0)
        recognized = False
        
        while not recognized:
            ret, frame = cap.read()
            if ret:
                face = resize_and_crop_face(frame)
                if face is not None:
                    temp_face_path = "temp_face.jpg"
                    cv2.imwrite(temp_face_path, face)
                    
                    try:
                        results = DeepFace.find(
                            img_path=temp_face_path, 
                            db_path=faces_directory, 
                            enforce_detection=False
                        )
                        
                        if len(results) > 0 and not results[0].empty:
                            identity = results[0].iloc[0]["identity"]
                            folder_name = os.path.basename(os.path.dirname(identity))
                            name, roll = folder_name.split("_")
                            
                            save_attendance(name, roll)
                            recognized = True
                            
                            return jsonify({
                                "success": True,
                                "status": "Face recognized", 
                                "name": name, 
                                "roll": roll
                            })
                    except Exception as e:
                        print(f"Recognition error: {e}")
        
        
        cap.release()
        cv2.destroyAllWindows()
        
        return jsonify({
            "success": False,
            "status": "No face recognized"
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "status": f"Authentication failed: {str(e)}"
        })

@app.route("/api/todayattendance", methods=["GET"])
def get_todays_attendance():
    try:
        # attendance_dir = "Attendance"
        attendance_file = f"{attendance_directory}/Attendance-{get_date_today()}.csv"
        if not os.path.exists(attendance_file):
            return jsonify({
                "success": False,
                "message": "No attendance records for today"
            })
        
        attendance_data = []
        with open(attendance_file, mode='r') as file:
            reader = csv.reader(file)
            next(reader)
            attendance_data = [row for row in reader]
        print(attendance_data)
        return jsonify({
            "success": True,
            "attendance": attendance_data
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": "error"
        })


