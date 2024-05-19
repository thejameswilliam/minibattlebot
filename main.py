import sys
import network


# Function to get the unique device ID (MAC address) of the ESP32

def get_unique_id():
    # Initialize the Wi-Fi interface in station mode
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    
    # Get the MAC address of the ESP32
    mac = wlan.config('mac')
    
    # Convert the MAC address to a readable format
    unique_id = ':'.join(['{:02x}'.format(b) for b in mac])
    return unique_id

# Print the unique device ID (MAC address)
print("Unique device ID (MAC address):", get_unique_id())

# The MAC address is used to identify the ESP32 devices and include the corresponding Python files
if get_unique_id() == '08:d1:f9:dd:9d:b0' :
    sys.path.append('/Bot 1 - Receiver')
    import b1r

if get_unique_id() == '08:d1:f9:dd:52:7c':
    sys.path.append('/Bot 1 - Sender')
    import b1s



if get_unique_id() == '' :  #TODO: Add the MAC address
    sys.path.append('/Bot 2 - Receiver')
    import b2r

if get_unique_id() == '' : #TODO: Add the MAC address
    sys.path.append('/Bot 2 - Sender')
    import b2s

