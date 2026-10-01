class Node:
    # Frame Types constants
    DATA = 1
    ACK = 2
    CONTROL = 3
    BROADCAST_MAC = "FF:FF:FF:FF"

    def __init__(self, name, mac_address, ipv6_address, neighbor_names=None):
        self.name = name
        self.mac_address = mac_address
        self.ipv6_address = ipv6_address
        # List of neighbor names (strings) provided during initialization
        self.neighbor_names = neighbor_names if neighbor_names else []
        # List of actual Node object references for simulation
        self.neighbors = []
        # MAC sequence number starts at 0
        self.mac_seq_num = 0

    def setup(self):
        """Initializes the node and prints the setup configuration."""
        print(f"[{self.name}][Init] Node Initialized - MAC: {self.mac_address}, IPv6: {self.ipv6_address}")

    def link_neighbors(self, network_nodes):
        """Links string neighbor names to actual Node objects in the simulation."""
        for name in self.neighbor_names:
            if name in network_nodes:
                self.neighbors.append(network_nodes[name])

    def send_mac(self, dest_mac, frame_type, payload=""):
        """
        Constructs a MAC frame, encapsulates the payload, and transmits it 
        to the appropriate one-hop neighbors.
        """
        # Determine Sequence Number
        if frame_type == self.ACK:
            # ACKs use the sequence number of the frame being acknowledged
            seq_num = payload 
            payload_data = ""
        else:
            # For new DATA or CONTROL frames, use the current seq num and increment
            seq_num = self.mac_seq_num
            self.mac_seq_num += 1
            payload_data = payload

        # Create the simplified MAC frame
        mac_frame = {
            "src_mac": self.mac_address,
            "dest_mac": dest_mac,
            "seq_num": seq_num,
            "frame_type": frame_type,
            "payload_length": len(str(payload_data)),
            "payload": payload_data
        }

        # Logging the creation operation
        type_str = {1: "DATA", 2: "ACK", 3: "CONTROL"}.get(frame_type, "UNKNOWN")
        print(f"[{self.name}][MAC] Creating {type_str} frame: Dest={dest_mac}, Seq={seq_num}")

        # Simulate wireless transmission to one-hop neighbors
        for neighbor in self.neighbors:
            # Deliver if it's a broadcast OR if the destination MAC matches the neighbor's MAC
            if dest_mac == self.BROADCAST_MAC or dest_mac == neighbor.mac_address:
                print(f"[{self.name}][MAC] Transmitting frame to one-hop neighbor {neighbor.name}")
                neighbor.receive_mac(mac_frame)

    def receive_mac(self, mac_frame):
        """
        Receives a MAC frame from the lower layer, parses the header, 
        and processes it based on the frame type.
        """
        src_mac = mac_frame["src_mac"]
        dest_mac = mac_frame["dest_mac"]
        seq_num = mac_frame["seq_num"]
        frame_type = mac_frame["frame_type"]
        payload = mac_frame["payload"]
        
        type_str = {1: "DATA", 2: "ACK", 3: "CONTROL"}.get(frame_type, "UNKNOWN")
        print(f"[{self.name}][MAC] Received {type_str} frame from MAC {src_mac}")
        print(f"[{self.name}][MAC] Parsing MAC header and decapsulating payload")

        # Process based on frame type
        if frame_type == self.DATA:
            if dest_mac != self.BROADCAST_MAC:
                print(f"[{self.name}][MAC] Unicast DATA received. Generating ACK for Seq={seq_num}")
                # Return MAC ACK containing the same sequence number
                self.send_mac(dest_mac=src_mac, frame_type=self.ACK, payload=seq_num)
            
            # Note: In Part B and C, 'payload' will be passed up to receive_ipv6() here.
            
        elif frame_type == self.ACK:
            print(f"[{self.name}][MAC] ACK received for Seq={seq_num}. Transmission successful.")
            
        elif frame_type == self.CONTROL:
            # Broadcast frames (like RPL DIO) do not require a MAC ACK
            print(f"[{self.name}][MAC] Broadcast CONTROL frame received. No ACK required.")
            # Note: In Part B, 'payload' will be passed up to receive_ipv6() here.


# ==========================================
# SIMULATION SETUP & EXECUTION
# ==========================================
if __name__ == "__main__":
    # 1. Create the five IoT nodes with their preconfigured addresses and topology
    nodes = {
        "A": Node("A", "00:00:00:01", "fd00::1", ["B", "C"]),
        "B": Node("B", "00:00:00:02", "fd00::2", ["A", "D"]),
        "C": Node("C", "00:00:00:03", "fd00::3", ["A", "E"]),
        "D": Node("D", "00:00:00:04", "fd00::4", ["B"]),
        "E": Node("E", "00:00:00:05", "fd00::5", ["C"])
    }

    # 2. Link the neighbors and call setup()
    print("--- INITIALIZING IOT NETWORK ---")
    for node in nodes.values():
        node.link_neighbors(nodes)
        node.setup()

    print("\n--- TEST 1: Node D sends a unicast DATA frame to Node B ---")
    # Expected behavior: Node D transmits, Node B receives and sends an ACK back to D
    nodes["D"].send_mac(dest_mac=nodes["B"].mac_address, frame_type=Node.DATA, payload="DummySensorData")

    print("\n--- TEST 2: Node A sends a broadcast CONTROL frame ---")
    # Expected behavior: Node A broadcasts, Nodes B and C receive it, NO ACKs are generated
    nodes["A"].send_mac(dest_mac=Node.BROADCAST_MAC, frame_type=Node.CONTROL, payload="DummyRplMessage")