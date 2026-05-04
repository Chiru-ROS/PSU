# unified_robot_turret_fast_stable.py
import customtkinter as ctk
from customtkinter import CTkImage
from PIL import Image
import cv2
import threading
import time
import socket
import pickle
import serial
import mediapipe as mp
import face_recognition
import traceback

# ---------------- CONFIG ----------------
RX_IP = "10.55.209.167"   # <-- set RX ESP32 IP
UDP_PORT = 4210            # <-- single combined port

SERIAL_PORT = "COM12"      # <-- TX ESP32 serial port
BAUD = 115200              # safer for USB stability

CAM_WIDTH = 640
CAM_HEIGHT = 480

TILT_CONSTANT = 90
IDENTITY_THRESH = 0.50

# Camera / send tuning
SEND_INTERVAL = 0.025      # seconds (40 Hz)
SERIAL_POLL_SLEEP = 0.001

# load face encoding
with open("my_face.pkl", "rb") as f:
    MY_FACE = pickle.load(f)

# ---------------- APP ----------------
class TurretApp:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Unified Robot (Stable Fast Mode)")
        self.root.geometry("1100x720")

        # Networking
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Serial (TX ESP32)
        try:
            self.ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.05)
        except Exception as e:
            print("Serial open error:", e)
            raise

        # Latest values from TX
        self.roverCmd = 'S'
        self.a1 = 90; self.a2 = 90; self.a3 = 90
        self.b1 = 0; self.b2 = 0
        self.joyX_rover = 2048
        self.joyX_turret = 2048

        # Face detector
        self.mp_face = mp.solutions.face_detection.FaceDetection(0, 0.55)

        # Camera
        self.cap = cv2.VideoCapture(1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
        # small wait
        time.sleep(0.2)
        if not self.cap.isOpened():
            raise RuntimeError("Camera failed to open")

        self.W = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.H = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.CX = self.W // 2

        # Pan/Tilt
        self.pan_angle = 90.0
        self.target_pan = 90.0
        self.target_tilt = float(TILT_CONSTANT)

        # Identity & tracking memory
        self.last_face_box = None
        self.last_match_time = 0
        self.last_identity_check = 0
        self.MATCH_EXPIRY = 2.0
        self.IDENTITY_CHECK_INTERVAL = 1.0

        # GUI
        self.video_label = ctk.CTkLabel(self.root, text="")
        self.video_label.pack(padx=10, pady=6)

        self.mode_btn = ctk.CTkButton(self.root, text="AUTO MODE", command=self.toggle_mode, width=200, height=50)
        self.mode_btn.pack(pady=6)
        self.is_auto = True

        # Controls
        self.speed_slider = ctk.CTkSlider(self.root, from_=0.005, to=0.05, command=self.update_speed, width=300)
        self.speed_slider.set(0.015); self.speed_slider.pack(pady=4)
        self.speed_label = ctk.CTkLabel(self.root, text="Tracking Speed = 0.015"); self.speed_label.pack()

        self.smooth_slider = ctk.CTkSlider(self.root, from_=0.05, to=0.5, command=self.update_smoothing, width=300)
        self.smooth_slider.set(0.15); self.smooth_slider.pack(pady=4)
        self.smooth_label = ctk.CTkLabel(self.root, text="Smoothing Factor = 0.15"); self.smooth_label.pack()

        self.SPEED_FACTOR = 0.015
        self.SMOOTH = 0.15

        # Threads with exception reporting
        threading.Thread(target=self.safe_thread, args=(self.serial_loop,), daemon=True).start()
        threading.Thread(target=self.safe_thread, args=(self.video_loop,), daemon=True).start()
        threading.Thread(target=self.safe_thread, args=(self.send_loop,), daemon=True).start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.mainloop()

    def safe_thread(self, fn):
        try:
            fn()
        except Exception:
            print("Thread crashed:", fn.__name__)
            traceback.print_exc()

    def on_close(self):
        try:
            self.cap.release()
        except:
            pass
        try:
            self.ser.close()
        except:
            pass
        self.root.destroy()

    def update_speed(self, v):
        self.SPEED_FACTOR = float(v)
        self.speed_label.configure(text=f"Tracking Speed = {self.SPEED_FACTOR:.3f}")

    def update_smoothing(self, v):
        self.SMOOTH = float(v)
        self.smooth_label.configure(text=f"Smoothing Factor = {self.SMOOTH:.2f}")

    def toggle_mode(self):
        self.is_auto = not self.is_auto
        self.mode_btn.configure(text="AUTO MODE" if self.is_auto else "MANUAL MODE")

    # ---------------- SERIAL READER ----------------
    def serial_loop(self):
        while True:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if not line:
                    time.sleep(SERIAL_POLL_SLEEP); continue
                parts = line.split(",")
                # expect: roverCmd,a1,a2,a3,b1,b2,joyX_rover,joyX_turret
                if len(parts) == 8:
                    self.roverCmd = parts[0]
                    self.a1 = int(parts[1]); self.a2 = int(parts[2]); self.a3 = int(parts[3])
                    self.b1 = int(parts[4]); self.b2 = int(parts[5])
                    self.joyX_rover = int(parts[6]); self.joyX_turret = int(parts[7])
            except Exception:
                # nonfatal; continue reading
                traceback.print_exc()
            time.sleep(SERIAL_POLL_SLEEP)

    # ---------------- SEND (single combined packet) ----------------
    def send_loop(self):
        while True:
            try:
                # Build combined packet:
                # R,<roverCmd>,A,<a1>,<a2>,<a3>,<b1>,<b2>,T,<pan>,<tilt>
                pkt = f"R,{self.roverCmd},A,{self.a1},{self.a2},{self.a3},{self.b1},{self.b2},T,{self.target_pan:.2f},{self.target_tilt:.2f}"
                self.sock.sendto(pkt.encode(), (RX_IP, UDP_PORT))
            except Exception:
                traceback.print_exc()
            time.sleep(SEND_INTERVAL)

    # ---------------- VIDEO LOOP ----------------
    def video_loop(self):
        while True:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.01); continue

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            now = time.time()

            results = self.mp_face.process(rgb)
            mp_faces = []
            if results.detections:
                for det in results.detections:
                    box = det.location_data.relative_bounding_box
                    x = int(box.xmin * self.W)
                    y = int(box.ymin * self.H)
                    w = int(box.width * self.W)
                    h = int(box.height * self.H)
                    mp_faces.append((x, y, x + w, y + h))

            final_face = None

            # AUTO mode handling
            if self.is_auto:
                if now - self.last_identity_check >= self.IDENTITY_CHECK_INTERVAL and mp_faces:
                    self.last_identity_check = now
                    try:
                        dlib_faces = face_recognition.face_locations(rgb, model="hog")
                        for (top, right, bottom, left) in dlib_faces:
                            enc = face_recognition.face_encodings(rgb, [(top, right, bottom, left)])[0]
                            dist = face_recognition.face_distance([MY_FACE], enc)[0]
                            if dist < IDENTITY_THRESH:
                                d_center = (left + right) / 2
                                best = None; best_d = 1e9
                                for (lx, ly, rx, ry) in mp_faces:
                                    m_center = (lx + rx) / 2
                                    dd = (m_center - d_center) ** 2
                                    if dd < best_d:
                                        best_d = dd; best = (lx, ly, rx, ry)
                                self.last_face_box = best
                                self.last_match_time = now
                                break
                    except Exception:
                        traceback.print_exc()

                if self.last_face_box and (now - self.last_match_time <= self.MATCH_EXPIRY):
                    final_face = self.last_face_box

                if final_face:
                    lx, ly, rx, ry = final_face
                    face_x = lx + (rx - lx) // 2
                    err = self.CX - face_x
                    if abs(err) < 60: err = 0

                    pan_step = err * self.SPEED_FACTOR
                    pan_step = max(-4, min(4, pan_step))
                    new_pan = self.pan_angle - pan_step
                    new_pan = max(0, min(180, new_pan))

                    self.pan_angle = (1 - self.SMOOTH) * self.pan_angle + self.SMOOTH * new_pan
                    self.target_pan = self.pan_angle
                    self.target_tilt = float(TILT_CONSTANT)

                    cv2.rectangle(frame, (lx, ly), (rx, ry), (0,255,0), 2)
                    cv2.putText(frame, "YOU", (lx, ly-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

            else:
                # Manual turret from joystick #1
                pan = int((self.joyX_turret / 4095.0) * 180.0)
                self.target_pan = pan
                self.pan_angle = pan

            # update GUI using CTkImage (avoids CTk warning)
            pil_img = Image.fromarray(rgb)
            ctk_img = CTkImage(pil_img, size=(self.W, self.H))
            self.video_label.configure(image=ctk_img)
            self.video_label.image = ctk_img

# run
if __name__ == "__main__":
    TurretApp()
