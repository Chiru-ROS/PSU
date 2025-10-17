import cv2
from cvzone.FaceDetectionModule import FaceDetector
import numpy as np
import serial
import time

# Open serial connection with ESP32 (check COM port!)
esp32 = serial.Serial('COM12', 115200, timeout=1)
time.sleep(2)  # wait for ESP32 reset

cap = cv2.VideoCapture(0)
ws, hs = 1280, 720
cap.set(3, ws)
cap.set(4, hs)

detector = FaceDetector()
servoPos = [90, 90]

while True:
    success, img = cap.read()
    img, bboxs = detector.findFaces(img, draw=False)

    if bboxs:
        fx, fy = bboxs[0]["center"]

        # Reverse X-axis here 👇
        servoX = np.interp(fx, [0, ws], [180, 0])  # reversed
        servoY = np.interp(fy, [0, hs], [0, 180])

        servoPos = [int(servoX), int(servoY)]

        # Send servo command to ESP32
        command = f"{servoPos[0]},{servoPos[1]}\n"
        esp32.write(command.encode())
        time.sleep(0.05)  # avoid flooding serial

        cv2.putText(img, "TARGET LOCKED", (850, 50),
                    cv2.FONT_HERSHEY_PLAIN, 3, (255, 0, 255), 3)
    else:
        cv2.putText(img, "NO TARGET", (850, 50),
                    cv2.FONT_HERSHEY_PLAIN, 3, (0, 0, 255), 3)

    cv2.putText(img, f"Servo X: {servoPos[0]} deg",
                (50, 50), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 2)
    cv2.putText(img, f"Servo Y: {servoPos[1]} deg",
                (50, 100), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 0), 2)

    cv2.imshow("Image", img)

    # ✅ Press Q to quit
    if cv2.waitKey(1) & 0xFF in [ord('q'), ord('Q')]:
        break

# Cleanup
cap.release()
cv2.destroyAllWindows()
esp32.close()
