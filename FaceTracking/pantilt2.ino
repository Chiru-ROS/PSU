#include <ESP32Servo.h>  // instead of Servo.h

Servo servoX;
Servo servoY;

int posX = 90;
int posY = 90;

void setup() {
  Serial.begin(115200);

  servoX.attach(18);  // GPIO18 for X axis
  servoY.attach(19);  // GPIO19 for Y axis

  servoX.write(posX);
  servoY.write(posY);

  Serial.println("Ready to receive servo positions...");
}

void loop() {
  if (Serial.available()) {
    String data = Serial.readStringUntil('\n');  // Expect "X,Y"
    int commaIndex = data.indexOf(',');
    if (commaIndex > 0) {
      posX = data.substring(0, commaIndex).toInt();
      posY = data.substring(commaIndex + 1).toInt();

      // Clamp angles between 0-180
      posX = constrain(posX, 0, 180);
      posY = constrain(posY, 0, 180);

      servoX.write(posX);
      servoY.write(posY);

      Serial.printf("Moved to X=%d Y=%d\n", posX, posY);
    }
  }
}
