
# Bot One Sender
# This Devices MAC address: b'\x08\xd1\xf9\xddR|'
import network
import espnow
import machine
import time

# Initialize Wi-Fi in station mode
sta = network.WLAN(network.STA_IF)
sta.active(True)

print("MAC address:", sta.config('mac'))

# Initialize ESP-NOW
e = espnow.ESPNow()
e.active(True)

# Replace with the receiver's MAC address
receiver_mac = b'\x08\xd1\xf9\xee_p'  # Ensure this is correctly formatted
e.add_peer(receiver_mac)

# Joystick switches setup
forward_switch = machine.Pin(12, machine.Pin.IN, machine.Pin.PULL_UP)
backward_switch = machine.Pin(13, machine.Pin.IN, machine.Pin.PULL_UP)
left_switch = machine.Pin(14, machine.Pin.IN, machine.Pin.PULL_UP)
right_switch = machine.Pin(27, machine.Pin.IN, machine.Pin.PULL_UP)

def send_command(command):
    e.send(receiver_mac, command)
    print("Sent command:", command)

try:
    while True:
        if not forward_switch.value():
            print("Forward")
            send_command(b'forward')
        elif not backward_switch.value():
            print("Backward")
            send_command(b'backward')
        elif not left_switch.value():
            print("Left")
            send_command(b'left')
        elif not right_switch.value():
            print("Right")
            send_command(b'right')
        else :
            print("Stop")
            send_command(b'stop')    
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Joystick control stopped")