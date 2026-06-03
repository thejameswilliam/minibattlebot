"""
ESP-NOW wrapper for MicroPython.

Provides three classes that make it easier to manage ESP-NOW communication:

  Peer        — a single remote ESP32 device, identified by MAC address
  PeerGroup   — a named collection of Peers you can send to as a batch
  Connection  — the local device; owns the ESP-NOW socket and all Peers/Groups

Quick start (sender):
    from glib import gspnow
    c = gspnow.Connection()
    robots = c.peerGroupAdd("Robots")
    robot = robots.peerAdd("AA:BB:CC:DD:EE:FF")
    robot.send({'x': 0, 'y': 50})

Quick start (receiver):
    from glib import gspnow
    c = gspnow.Connection()
    senders = c.peerGroupAdd("Controllers")
    senders.peerAdd("AA:BB:CC:DD:EE:FF")

    def on_data(sender_mac, data):
        print("Got:", data)

    c.onDataReceived = on_data
"""

import espnow
import network

from glib import pickle
from glib.glog import Logger

logger = Logger(level=2)


class Peer:
    """A single remote ESP32 device identified by its MAC address."""

    def __init__(self, mac_address, name="", connection=None):
        self._name = name.upper()
        self._mac_string = mac_address.upper()
        self._mac_bytes = self._encode()
        self._connection = connection

    def _encode(self):
        """Convert 'AA:BB:CC:DD:EE:FF' string to a bytearray."""
        return bytearray(int(part, 16) for part in self._mac_string.split(":"))

    def _decode(self):
        """Convert a bytearray MAC back to a colon-separated string."""
        return ':'.join('{:02x}'.format(b) for b in self._mac_bytes).upper()

    def getName(self):
        return self._name

    def setName(self, name):
        self._name = name.upper()

    def getMAC(self):
        return self._mac_string

    def getMACBytes(self):
        return self._mac_bytes

    def send(self, data):
        """Send data to this peer. data can be any serializable Python object."""
        payload = pickle.dumps(data)
        logger.debug(f"Sending to {self}: {data}")
        self._connection.send(self._mac_bytes, payload)

    def __repr__(self):
        if self._name:
            return f"Peer({self._mac_string} - {self._name})"
        return f"Peer({self._mac_string})"


class PeerGroup:
    """A named collection of Peers that can be addressed together."""

    def __init__(self, parent, name):
        self.name = name.upper()
        self.parent = parent
        self.peers = {}

    def peerAdd(self, mac_address, name=""):
        """Register a new Peer and add it to the ESP-NOW peer table."""
        mac_address = mac_address.upper()
        logger.info(f"Adding peer: {mac_address}")

        try:
            peer = Peer(mac_address, name, connection=self.parent._connection)
            self.parent._connection.add_peer(peer.getMACBytes())
        except Exception as e:
            logger.error(f"Could not add peer {mac_address}: {e}")
            return None

        self.peers[peer.getMAC()] = peer
        self.parent.peers[peer.getMAC()] = peer
        return peer

    def peerRemove(self, mac_address):
        """Remove a Peer from this group and from the ESP-NOW peer table."""
        mac_address = mac_address.upper()
        logger.info(f"Removing peer: {mac_address}")

        peer = self.peers.get(mac_address)
        if peer is None:
            logger.error(f"Peer not found: {mac_address}")
            return

        self.parent._connection.del_peer(peer.getMACBytes())
        del self.peers[mac_address]
        del self.parent.peers[mac_address]

    def peerFindByName(self, name):
        """Return the Peer with the given name, or None if not found."""
        name = name.upper()
        for peer in self.peers.values():
            if peer.getName() == name:
                return peer
        return None

    def peerFindByMAC(self, mac_address):
        """Return the Peer with the given MAC, or None if not found."""
        return self.peers.get(mac_address.upper())

    def send(self, data):
        """Send data to every Peer in this group."""
        if not self.peers:
            logger.error(f"No peers in group '{self.name}' — nothing sent.")
            return
        for peer in self.peers.values():
            peer.send(data)

    def __repr__(self):
        return f"PeerGroup({self.name}, {len(self.peers)} peer(s))"


class Connection(Peer):
    """
    Represents the local ESP32 device and owns the ESP-NOW connection.

    Inherits from Peer so it can be used as a source address and so that
    its MAC address can be read with getMAC().
    """

    def __init__(self):
        # Bring up the Wi-Fi interface — required by ESP-NOW even without a network
        self._wlan = network.WLAN(network.STA_IF)
        self._wlan.active(True)

        # Start ESP-NOW
        self._connection = espnow.ESPNow()
        self._connection.active(True)

        # Populate Peer's fields using this device's own MAC
        self._mac_bytes = self._wlan.config('mac')
        self._mac_string = self._decode()
        self._name = "SELF"

        self.peers = {}
        self.peer_groups = {}

        # Add the broadcast address so we can send to all devices at once
        broadcast_group = self.peerGroupAdd("BROADCAST")
        broadcast_peer = broadcast_group.peerAdd("FF:FF:FF:FF:FF:FF", "BROADCAST")
        # Keep it out of the main peers dict so broadcasts don't trigger onDataReceived
        del self.peers[broadcast_peer.getMAC()]

        # Register the low-level receive interrupt
        self._connection.irq(self._onReceiveIRQ)

        logger.info(f"ESP-NOW ready. This device MAC: {self.getMAC()}")

    def _onReceiveIRQ(self, event):
        """
        Low-level interrupt handler called by ESP-NOW on every incoming packet.
        Converts the raw sender bytearray to a MAC string, checks it against
        the known peer list, deserializes the payload, then calls onDataReceived.
        """
        sender, data = event.irecv(0)
        if not sender:
            return

        sender_mac = ':'.join('{:02x}'.format(b) for b in sender).upper()

        if sender_mac not in self.peers:
            logger.debug(f"Ignoring packet from unknown sender: {sender_mac}")
            return

        try:
            decoded = pickle.loads(data)
        except Exception as e:
            logger.error(f"Failed to decode packet from {sender_mac}: {e}")
            return

        self.onDataReceived(sender_mac, decoded)

    def onDataReceived(self, sender_mac, data):
        """
        Override this method to handle incoming data.

        Example:
            def my_handler(sender, data):
                print(sender, data)
            conn.onDataReceived = my_handler
        """
        logger.info(f"Received from {sender_mac}: {data}")

    def peerGroupAdd(self, name):
        """Create a new PeerGroup with the given name (or return it if it exists)."""
        name = name.upper()
        if name not in self.peer_groups:
            logger.info(f"Creating peer group: {name}")
            self.peer_groups[name] = PeerGroup(self, name)
        return self.peer_groups[name]

    def peerGroupFind(self, name):
        """Return the PeerGroup with the given name, or None."""
        return self.peer_groups.get(name.upper())

    def broadcast(self, data):
        """Send data to every ESP32 in range, regardless of pairing."""
        logger.info(f"Broadcasting: {data}")
        self.peer_groups['BROADCAST'].send(data)

    def send(self, data):
        """Send data to all configured PeerGroups (excluding BROADCAST)."""
        targets = {k: v for k, v in self.peer_groups.items() if k != "BROADCAST"}
        if not targets:
            logger.error("No peer groups to send to. Use .broadcast() or add a group first.")
            return
        for group in targets.values():
            group.send(data)

    def turnOff(self):
        self._wlan.active(False)

    def turnOn(self):
        self._wlan.active(True)
