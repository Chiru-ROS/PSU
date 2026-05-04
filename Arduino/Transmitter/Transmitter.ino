// ========================================================
//                TWO JOYSTICKS + POTS + BUTTONS
//
// Joystick 1 → Turret (X only) → pin 34
// Joystick 2 → Rover (X,Y) → pins 39,36
// ========================================================

// ---------------- JOYSTICKS ----------------
// Joystick 1 (TURRET)
#define TURRET_JOY_X 34    // NEW

// Joystick 2 (ROVER)
#define ROVER_JOY_X 39
#define ROVER_JOY_Y 36

// ---------------- POTS ----------------
#define POT1 32
#define POT2 33
#define POT3 35

// ---------------- BUTTONS ----------------
#define BTN1 25
#define BTN2 26

// ----------- Pot mapping ------------
const float ADC_MIN = 819.0;
const float ADC_MAX = 3276.0;
const float ADC_RANGE = (ADC_MAX - ADC_MIN);
const float DEG_PER_ADC = 180.0 / ADC_RANGE;

int smoothADC(int pin) {
  long s = 0;
  for (int i = 0; i < 3; i++) {  // 3 samples = fast + smooth
    s += analogRead(pin);
  }
  return s / 3;
}

float potToAngle(int adcVal) {
  adcVal = constrain(adcVal, ADC_MIN, ADC_MAX);
  return (adcVal - ADC_MIN) * DEG_PER_ADC;
}

void setup() {
  Serial.begin(115200);

  pinMode(BTN1, INPUT_PULLUP);
  pinMode(BTN2, INPUT_PULLUP);
}

void loop() {

  // =====================================================
  //                 ROVER JOYSTICK (#2)
  // =====================================================
  int joyX_rover = analogRead(ROVER_JOY_X);
  int joyY_rover = analogRead(ROVER_JOY_Y);

  char roverCmd = 'S';
  int dz = 400;

  if (joyY_rover > 2048 + dz) roverCmd = 'F';
  else if (joyY_rover < 2048 - dz) roverCmd = 'B';
  else if (joyX_rover > 2048 + dz) roverCmd = 'R';
  else if (joyX_rover < 2048 - dz) roverCmd = 'L';
  else roverCmd = 'S';

  // =====================================================
  //                 TURRET JOYSTICK (#1)
  // =====================================================
  int joyX_turret = analogRead(TURRET_JOY_X);   // <--- NEW

  // =====================================================
  //                     POTS
  // =====================================================
  int p1 = smoothADC(POT1);
  int p2 = smoothADC(POT2);
  int p3 = smoothADC(POT3);

  int a1 = (int)potToAngle(p1);
  int a2 = (int)potToAngle(p2);
  int a3 = (int)potToAngle(p3);

  a1 = 180 - a1;   // invert
  a2 = 180 - a2;   // invert

  // =====================================================
  //                    BUTTONS
  // =====================================================
  int b1 = (digitalRead(BTN1) == LOW) ? 1 : 0;
  int b2 = (digitalRead(BTN2) == LOW) ? 1 : 0;

  // =====================================================
  //          SERIAL FORMAT (8 FIELDS NOW):
  //
  // roverCmd,a1,a2,a3,b1,b2,joyX_rover,joyX_turret
  // =====================================================
  Serial.printf(
      "%c,%d,%d,%d,%d,%d,%d,%d\n",
      roverCmd, a1, a2, a3, b1, b2, joyX_rover, joyX_turret
  );

  vTaskDelay(1); // fast + non-blocking
}
