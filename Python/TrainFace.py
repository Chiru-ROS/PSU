# train_face.py
# Clean, fast, error-proof training using face_recognition only
import cv2
import face_recognition
import pickle
import time

OUTPUT_FILE = "my_face.pkl"

print("Starting in 2 seconds...")
time.sleep(2)

cap = cv2.VideoCapture(0)
face_encodings = []

print("Move your head slowly. Press Q to save and exit.")

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Use dlib-based face detector (stable)
    boxes = face_recognition.face_locations(rgb, model="hog")

    if len(boxes) > 0:
        top, right, bottom, left = boxes[0]      # take first face
        enc = face_recognition.face_encodings(rgb, [boxes[0]])[0]

        face_encodings.append(enc)
        cv2.rectangle(frame, (left, top), (right, bottom), (0,255,0), 2)
        cv2.putText(frame, "Captured", (left, top-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)

    cv2.imshow("Training", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

if len(face_encodings) == 0:
    print("ERROR: No face captured.")
else:
    # average encoding
    avg = sum(face_encodings) / len(face_encodings)
    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(avg, f)
    print(f"Saved {len(face_encodings)} samples to {OUTPUT_FILE}")
