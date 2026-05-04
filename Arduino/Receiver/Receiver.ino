/* rx_combined_fast_final.ino
   Single-UDP-packet ultra-fast RX (final).
   Packet format:
   R,<roverCmd>,A,<a1>,<a2>,<a3>,<b1>,<b2>,T,<pan>,<tilt>
*/

#include <Wire.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Adafruit_PWMServoDriver.h>

const char* ssid = "CMF";
const char* password = "chiru2005";

WiFiUDP Udp;
const int UDP_PORT = 4210;
char udpBuf[256];

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver(0x40);
#define SERVOMIN 120
#define SERVOMAX 600
int angleToPulse(int ang){ return map(ang,0,180,SERVOMIN,SERVOMAX); }

// Arm remap
int currentA1=90,currentA2=90,currentA3=90;
int targetA1=90,targetA2=90,targetA3=90;
int currentA4=150,targetA4=150;

const int SERVO2_MIN=130,SERVO2_MAX=70;
const int SERVO3_MIN=30,SERVO3_MAX=130;
const int SERVO1_MIN=20,SERVO1_MAX=140;
const int SERVO4_MIN=70,SERVO4_MAX=140;

int clampServo(int s,int a){
  if(s==1) return constrain(a,SERVO1_MIN,SERVO1_MAX);
  if(s==2) return constrain(a,SERVO2_MIN,SERVO2_MAX);
  if(s==3) return constrain(a,SERVO3_MIN,SERVO3_MAX);
  if(s==4) return constrain(a,SERVO4_MIN,SERVO4_MAX);
  return a;
}

#define IN1 26
#define IN2 27
#define IN3 13
#define IN4 12
void roverForward(){ digitalWrite(IN1,HIGH); digitalWrite(IN2,LOW); digitalWrite(IN3,HIGH); digitalWrite(IN4,LOW); }
void roverBackward(){ digitalWrite(IN1,LOW); digitalWrite(IN2,HIGH); digitalWrite(IN3,LOW); digitalWrite(IN4,HIGH); }
void roverLeft(){ digitalWrite(IN1,LOW); digitalWrite(IN2,HIGH); digitalWrite(IN3,HIGH); digitalWrite(IN4,LOW); }
void roverRight(){ digitalWrite(IN1,HIGH); digitalWrite(IN2,LOW); digitalWrite(IN3,LOW); digitalWrite(IN4,HIGH); }
void roverStop(){ digitalWrite(IN1,LOW); digitalWrite(IN2,LOW); digitalWrite(IN3,LOW); digitalWrite(IN4,LOW); }

#define NEW_IN1 5
void newMotorOn(){ digitalWrite(NEW_IN1,HIGH); }
void newMotorOff(){ digitalWrite(NEW_IN1,LOW); }

#define PAN_CHANNEL 5
#define TILT_CHANNEL 6
float currentPan=90.0,currentTilt=90.0;
float targetPan=90.0,targetTilt=90.0;
const float TURRET_LERP = 0.60;

const int ARM_STEP = 1;
const int DEAD_BAND = 1;

void setup(){
  Serial.begin(115200);
  pinMode(IN1,OUTPUT); pinMode(IN2,OUTPUT); pinMode(IN3,OUTPUT); pinMode(IN4,OUTPUT); roverStop();
  pinMode(NEW_IN1,OUTPUT); newMotorOff();
  Wire.begin(21,22);
  pwm.begin(); pwm.setPWMFreq(50);
  WiFi.setSleep(false);
  WiFi.begin(ssid,password);
  while(WiFi.status()!=WL_CONNECTED){ delay(1); }
  Udp.begin(UDP_PORT);

  pwm.setPWM(0,0,angleToPulse(90)); pwm.setPWM(1,0,angleToPulse(90)); pwm.setPWM(2,0,angleToPulse(90));
  pwm.setPWM(3,0,angleToPulse(70));
  pwm.setPWM(PAN_CHANNEL,0,angleToPulse(90)); pwm.setPWM(TILT_CHANNEL,0,angleToPulse(90));
}

void loop(){
  int packetSize = Udp.parsePacket();
  if(packetSize>0){
    int len = Udp.read(udpBuf, sizeof(udpBuf)-1);
    if(len>0){
      udpBuf[len]='\0';
      String s = String(udpBuf);

      // split by commas
      const int MAX_TOK = 20;
      String tok[MAX_TOK];
      int tcount=0; int start=0;
      for(int i=0;i<=s.length() && tcount<MAX_TOK;i++){
        if(i==s.length() || s[i]==','){
          tok[tcount++]=s.substring(start,i);
          start=i+1;
        }
      }

      if(tcount>=11 && tok[0]=="R" && tok[2]=="A" && tok[8]=="T"){
        // rover
        char rc = tok[1].charAt(0);
        if(rc=='F') roverForward();
        else if(rc=='B') roverBackward();
        else if(rc=='L') roverLeft();
        else if(rc=='R') roverRight();
        else roverStop();

        int a1 = tok[3].toInt();
        int a2 = tok[4].toInt();
        int a3 = tok[5].toInt();
        int b1 = tok[6].toInt();
        int b2 = tok[7].toInt();

        targetA1 = clampServo(2,a1);
        targetA2 = clampServo(3,a2);
        targetA3 = clampServo(1,a3);

        if(b1==1) newMotorOn(); else newMotorOff();
        targetA4 = (b2==1)?70:140;

        float pan = tok[9].toFloat();
        float tilt = tok[10].toFloat();
        targetPan = constrain(pan,0.0,180.0);
        targetTilt = constrain(tilt,0.0,180.0);
      }
    }
  }

  // arm smoothing
  if(abs(currentA1-targetA1)>DEAD_BAND) currentA1 += (currentA1<targetA1?ARM_STEP:-ARM_STEP);
  if(abs(currentA2-targetA2)>DEAD_BAND) currentA2 += (currentA2<targetA2?ARM_STEP:-ARM_STEP);
  if(abs(currentA3-targetA3)>DEAD_BAND) currentA3 += (currentA3<targetA3?ARM_STEP:-ARM_STEP);

  currentA4 = targetA4; // instant trigger

  pwm.setPWM(0,0,angleToPulse(currentA3));
  pwm.setPWM(1,0,angleToPulse(currentA1));
  pwm.setPWM(2,0,angleToPulse(currentA2));
  pwm.setPWM(3,0,angleToPulse(currentA4));

  // turret lerp
  currentPan += (targetPan - currentPan) * TURRET_LERP;
  currentTilt += (targetTilt - currentTilt) * TURRET_LERP;

  pwm.setPWM(PAN_CHANNEL,0,angleToPulse((int)round(currentPan)));
  pwm.setPWM(TILT_CHANNEL,0,angleToPulse((int)round(currentTilt)));

  delay(1);
}
