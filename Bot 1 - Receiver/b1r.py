
# Bot One Receiver
# This Devices MAC address: b'\x08\xd1\xf9\xdd\x9d\xb0'
import network
import espnow

from machine import Pin
import time



# Initialize Wi-Fi in station mode
sta = network.WLAN(network.STA_IF)
sta.active(True)

print("MAC address:", sta.config('mac'))

# Initialize ESP-NOW
e = espnow.ESPNow()
e.active(True)

# Replace with the sender's MAC address
peer_mac = b'\x08\xd1\xf9\xddR|'  # Replace with the sender's MAC address
e.add_peer(peer_mac)

# Motor 1 setup
IN1 = Pin(25, Pin.OUT)
IN2 = Pin(26, Pin.OUT)

# Motor 2 setup
IN3 = Pin(33, Pin.OUT)
IN4 = Pin(32, Pin.OUT)

def motor1_forward():
    IN1.on()
    IN2.off()

def motor1_backward():
    IN1.off()
    IN2.on()

def motor1_stop():
    IN1.off()
    IN2.off()

def motor2_forward():
    IN3.on()
    IN4.off()

def motor2_backward():
    IN3.off()
    IN4.on()

def motor2_stop():
    IN3.off()
    IN4.off()

def process_command(command):
    print("Processing command:", command)
    if command == b'forward':
        motor1_forward()
        motor2_forward()
    elif command == b'backward':
        motor1_backward()
        motor2_backward()
    elif command == b'left':
        motor1_backward()
        motor2_forward()
    elif command == b'right':
        motor1_forward()
        motor2_backward()
    elif command == b'stop':
        motor1_stop()
        motor2_stop()
    else:
        motor1_stop()
        motor2_stop()

# Example usage
print("Waiting for commands...")

while True:
    host, msg = e.recv()
    if msg:
        print("Received command:", msg)
        process_command(msg)
    else :
        print("No message received")
        motor2_stop()
        motor1_stop()    
