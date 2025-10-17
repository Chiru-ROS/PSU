import numpy as np
import cv2
import os
import socket

########## KNN CODE ############
def distance(v1, v2):
    return np.sqrt(((v1 - v2) ** 2).sum())

def knn(train, test, k=5):
    dist = []
    for i in range(train.shape[0]):
        ix = train[i, :-1]
        iy = train[i, -1]
        d = distance(test, ix)
        dist.append([d, iy])
    dk = sorted(dist, key=lambda x: x[0])[:k]
    labels = np.array(dk)[:, -1]
    output = np.unique(labels, return_counts=True)
    index = np.argmax(output[1])
    min_dist = dk[0][0]
    return output[0][index], min_dist
################################

# ---- UDP SETUP ----
ESP32_IP = "10.222.213.105"  # <-- your ESP32 IP
ESP32_PORT = 4210
udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ---- CAMERA ----
cap = cv2.VideoCapture(0)  # iVCam or default webcam
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

face_cascade = cv2.CascadeClassifier("haarcascade_frontalface_alt.xml")

dataset_path = "./face_dataset/"
face_data = []
labels = []
class_id = 0
names = {}

# ---- LOAD TRAINED FACES ----
for fx in os.listdir(dataset_path):
    if fx.endswith('.npy'):
        names[class_id] = fx[:-4]
        data_item = np.load(os.path.join(dataset_path, fx))
        face_data.append(data_item)
        target = class_id * np.ones((data_item.shape[0],))
        class_id += 1
        labels.append(target)

face_dataset = np.concatenate(face_data, axis=0)
face_labels = np.concatenate(labels, axis=0).reshape((-1, 1))
trainset = np.concatenate((face_dataset, face_labels), axis=1)

font = cv2.FONT_HERSHEY_SIMPLEX

# ---- CENTER ----
frame_width = 640
frame_height = 480
center_x = frame_width // 2
center_y = frame_height // 2

# ---- SERVO INIT ----
pan_angle = 90
tilt_angle = 90
PAN_STEP = 2
TILT_STEP = 2
DEAD_ZONE = 20  # no movement if within 20px of center

# ---- MAIN LOOP ----
while True:
    ret, frame = cap.read()
    if not ret:
        continue

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)

    cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)  # center marker

    for face in faces:
        x, y, w, h = face
        offset = 5
        face_section = frame[y-offset:y+h+offset, x-offset:x+w+offset]
        face_section = cv2.resize(face_section, (100, 100))

        out, min_dist = knn(trainset, face_section.flatten())
        threshold = 7000
        if min_dist > threshold:
            name = "Unknown"
        else:
            name = names[int(out)]

        # Face center
        cx = x + w // 2
        cy = y + h // 2
        dx = cx - center_x
        dy = cy - center_y
        dist_from_center = int(np.sqrt(dx ** 2 + dy ** 2))

        # Draw annotations
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2)
        cv2.putText(frame, name, (x, y - 10), font, 1, (255, 0, 0), 2, cv2.LINE_AA)
        cv2.line(frame, (center_x, center_y), (cx, cy), (0, 255, 255), 2)
        cv2.circle(frame, (cx, cy), 5, (0, 255, 0), -1)
        info = f"({cx},{cy}) d={dist_from_center}"
        cv2.putText(frame, info, (x, y + h + 20), font, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

        # ---- PAN/TILT CONTROL with deadzone ----
        if abs(dx) > DEAD_ZONE:
            if cx < center_x:
                pan_angle += PAN_STEP
            elif cx > center_x:
                pan_angle -= PAN_STEP

        if abs(dy) > DEAD_ZONE:
            if cy < center_y:
                tilt_angle += TILT_STEP
            elif cy > center_y:
                tilt_angle -= TILT_STEP

        pan_angle = max(0, min(180, pan_angle))
        tilt_angle = max(0, min(180, tilt_angle))

        # ---- SEND UDP ----
        msg = f"{name},{cx},{cy},{pan_angle},{tilt_angle}"
        udp.sendto(msg.encode(), (ESP32_IP, ESP32_PORT))
        cv2.putText(frame, f"Sent: {msg}", (10, 460), font, 0.5, (0, 255, 255), 1)

    cv2.imshow("Face Tracking - Wireless", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
