class Node:
    #MAC Frame Types
    DATA = 1
    ACK = 2
    CONTROL = 3
    BROADCAST_MAC = "FF:FF:FF:FF"

    #IPv6 Next Header values
    NH_ICMPV6 = 58   # IPv6 payload contains an ICMPv6 RPL control message
    NH_NONE = 59     # nothing follows the IPv6 header

    #ICMPv6 RPL control message fields
    RPL_TYPE = 155    # identifies an RPL control message
    RPL_CODE_DIO = 1  # Code = 1 means this is a DIO

    registry = {}

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

        #RPL state
        # Root (A) starts at Rank 0; every other node starts at "infinity"
        # until it hears a DIO and can compute a real rank.
        self.rank = float('inf')
        self.preferred_parent = None

        # Self-register so other nodes can resolve this node by IPv6 address
        Node.registry[ipv6_address] = self

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

            # Hand the decapsulated payload UP to IPv6 (Part B)
            self.receive_ipv6(payload)

        elif frame_type == self.ACK:
            print(f"[{self.name}][MAC] ACK received for Seq={seq_num}. Transmission successful.")

        elif frame_type == self.CONTROL:
            # Broadcast frames (like RPL DIO) do not require a MAC ACK
            print(f"[{self.name}][MAC] Broadcast CONTROL frame received. No ACK required.")

            # Hand the decapsulated payload UP to IPv6
            self.receive_ipv6(payload)

    def send_ipv6(self, dest_ipv6, next_header, payload, dest_mac):
        """
        Builds a simplified IPv6 header around 'payload', then hands the
        resulting packet down to send_mac(). The caller decides dest_mac
        (which one-hop neighbor to actually transmit to) and dest_ipv6
        (the true end-to-end IPv6 destination) separately, since on a
        multi-hop path these are often different nodes.
        """
        ipv6_packet = {
            "src_ip": self.ipv6_address,
            "dst_ip": dest_ipv6,
            "next_header": next_header,
            "payload_length": len(str(payload)),
            "payload": payload,
        }

        print(f"[{self.name}][IPv6] Encapsulating message: Next Header={next_header}")

        # Broadcast IPv6 traffic (e.g. an RPL DIO) travels inside a MAC
        # CONTROL frame; anything else is a normal unicast DATA frame.
        frame_type = self.CONTROL if dest_mac == self.BROADCAST_MAC else self.DATA
        self.send_mac(dest_mac, frame_type, ipv6_packet)

    def receive_ipv6(self, ipv6_packet):
        """
        Parses the IPv6 header and dispatches the payload to whichever
        upper-layer protocol the Next Header field identifies.
        """
        next_header = ipv6_packet["next_header"]
        print(f"[{self.name}][IPv6] Parsing IPv6 packet: Next Header={next_header}")

        if next_header == self.NH_ICMPV6:
            print(f"[{self.name}][IPv6] Passing ICMPv6 payload to RPL")
            # Resolve the sender's IPv6 address back to a Node object (and
            # fall back to the raw address if it's not a known node, e.g.
            # an address we haven't registered yet).
            sender_node = Node.registry.get(ipv6_packet["src_ip"])
            src_name = sender_node.name if sender_node else ipv6_packet["src_ip"]
            self.receive_rpl(ipv6_packet["payload"], src_name)
        else:
            # Parts C/D will add branches here for Next Header = 17 (UDP)
            # and Next Header = 50 (ESP).
            print(f"[{self.name}][IPv6] Unhandled Next Header={next_header}, dropping packet")

    def send_rpl_dio(self):
        """
        Creates a DIO advertising this node's current rank and broadcasts
        it to all one-hop neighbors via IPv6 + MAC.
        """
        dio = {
            "type": self.RPL_TYPE,
            "code": self.RPL_CODE_DIO,
            "rank": self.rank,
        }
        print(f"[{self.name}][RPL] Creating DIO: Rank={self.rank}")

        # RPL DIOs are link-local multicast in real 6LoWPAN; here we just
        # use the simplified MAC broadcast address to reach every neighbor.
        self.send_ipv6(
            dest_ipv6="ff02::1a",
            next_header=self.NH_ICMPV6,
            payload=dio,
            dest_mac=self.BROADCAST_MAC,
        )

    def receive_rpl(self, dio, src_name):
        """
        Processes a received DIO: computes a candidate rank (sender's rank
        + 1 hop), and if that's better than our current rank, adopts the
        sender as our preferred parent and re-broadcasts our own DIO so
        the improvement propagates further down the tree.
        """
        advertised_rank = dio["rank"]
        print(f"[{self.name}][RPL] Received DIO from {src_name}: Advertised Rank={advertised_rank}")

        candidate_rank = advertised_rank + 1
        print(f"[{self.name}][RPL] Candidate Rank={candidate_rank}")

        if candidate_rank < self.rank:
            old_rank = self.rank
            self.rank = candidate_rank
            self.preferred_parent = src_name
            print(f"[{self.name}][RPL] Updating Rank from {old_rank} to {self.rank}")
            print(f"[{self.name}][RPL] Setting Preferred Parent={src_name}")
            # Propagate our improved rank onward to our own neighbors
            self.send_rpl_dio()
        else:
            print(f"[{self.name}][RPL] Candidate Rank not better than current Rank={self.rank}; ignoring")