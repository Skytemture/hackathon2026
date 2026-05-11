import cv2
from pyzbar.pyzbar import decode
from gpiozero import Servo, OutputDevice
from gpiozero.pins.pigpio import PiGPIOFactory
from time import sleep
from pymongo import MongoClient
from datetime import datetime

# ---------------- MONGODB ----------------
MONGO_URI = "mongodb+srv://hackathon0509_user:1eYLNz7Og9UYlaLl@cluster0.jedeu7j.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client["hackathon"]
containers_col = db["containers"]

def upload_return(qr_code):
    qr_code = qr_code.strip().upper()
    result = containers_col.update_one(
        {"qr_code": qr_code},
        {"$set": {
            "status":     "C01",
            "user_id":    None,
            "updated_at": datetime.now().isoformat()
        }}
    )
    if result.matched_count:
        print(f"[DB] {qr_code} → C01 ✅")
    else:
        print(f"[DB] {qr_code} not found ⚠️")

# ---------------- SERVO ----------------
factory = PiGPIOFactory()
servo = Servo(18, pin_factory=factory)

def angle_to_value(angle):
    return (angle - 90) / 90

def servo_move(angle):
    print(f"Servo → {angle}°")
    servo.value = angle_to_value(angle)
    sleep(0.8)

# ---------------- STEPPER ----------------
IN1 = OutputDevice(27)
IN2 = OutputDevice(22)
IN3 = OutputDevice(23)
IN4 = OutputDevice(24)
pins = [IN1, IN2, IN3, IN4]

sequence = [
    [1,0,0,0],
    [1,1,0,0],
    [0,1,0,0],
    [0,1,1,0],
    [0,0,1,0],
    [0,0,1,1],
    [0,0,0,1],
    [1,0,0,1]
]

def set_pins(state):
    for pin, val in zip(pins, state):
        pin.value = val

def step_motor(steps, delay=0.002, direction=1):
    print(f"Stepper → {steps} steps {'fwd' if direction==1 else 'rev'}")
    seq = sequence if direction == 1 else list(reversed(sequence))
    for _ in range(steps):
        for step in seq:
            set_pins(step)
            sleep(delay)

def motor_back(steps):
    step_motor(steps, direction=-1)

def release_motor():
    for p in pins:
        p.off()

# ---------------- PARSE ----------------
def parse_item(qr):
    qr = qr.strip().upper()
    print("RAW:", qr)
    if qr.startswith("PLATE"):
        return "PLATE"
    elif qr.startswith("LID"):
        return "LID"
    elif qr.startswith("CUP"):
        return "CUP"
    return None

# ---------------- PROCESS ----------------
def process_item(qr_code, item):
    if item == "PLATE":
        steps = 140
        servo_angle = 130
    elif item == "LID":
        steps = 280
        servo_angle = 130
    elif item == "CUP":
        steps = 280
        servo_angle = 40
    else:
        print(f"[SKIP] unknown item: {item}")
        return

    print(f"[HW] START → {item}")

    # MOVE FORWARD
    step_motor(steps)
    servo_move(servo_angle)
    sleep(1)

    # RETURN
    servo_move(90)
    motor_back(steps)
    release_motor()

    print(f"[HW] DONE → {item}")

    # ✅ 硬體復位完成後更新 DB
    upload_return(qr_code)

# ---------------- CAMERA ----------------
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("❌ Cannot open camera")
    exit()

print("✅ System Ready — scanning...")
last_qr = None

while True:
    ret, frame = cap.read()
    if not ret:
        continue

    codes = decode(frame)
    if codes:
        qr = codes[0].data.decode("utf-8").strip()
        if qr != last_qr:
            print(f"\nDETECTED: {qr}")
            last_qr = qr
            item = parse_item(qr)
            if item:
                print(f"Processing: {item}")
                process_item(qr, item)
                print("✅ Done. Waiting for next scan...\n")
                sleep(2)
            else:
                print(f"[SKIP] not a container QR: {qr}")

    cv2.imshow("Scanner", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("System stopped.")
