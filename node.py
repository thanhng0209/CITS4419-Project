class Node:
    # MAC frame types
    DATA = 1
    ACK = 2
    CONTROL = 3
    BROADCAST_MAC = "FF:FF:FF:FF"

    # IPv6 next-header values
    NH_ICMPV6 = 58
    NH_UDP = 17
    NH_NONE = 59

    # ICMPv6 RPL message fields
    RPL_TYPE = 155
    RPL_CODE_DIO = 1

    registry = {}
    server = None

    def __init__(self, name, mac_address, ipv6_address, neighbor_names=None):
        self.name = name
        self.mac_address = mac_address
        self.ipv6_address = ipv6_address
        self.neighbor_names = neighbor_names if neighbor_names else []
        self.neighbors = []
        self.mac_seq_num = 0
        self.rank = float('inf')
        self.preferred_parent = None
        self.coap_message_id = 1000
        self.coap_token_counter = 0

        Node.registry[ipv6_address] = self
        if self.name == "Server":
            Node.server = self

    @staticmethod
    def find_by_name(name):
        for node in Node.registry.values():
            if node.name == name:
                return node
        return None

    @staticmethod
    def find_by_ipv6(ipv6_address):
        return Node.registry.get(ipv6_address)

    def setup(self):
        print(f"[{self.name}][Init] Node Initialized - MAC: {self.mac_address}, IPv6: {self.ipv6_address}")

    def link_neighbors(self, network_nodes):
        for name in self.neighbor_names:
            if name in network_nodes:
                self.neighbors.append(network_nodes[name])

    def send_mac(self, dest_mac, frame_type, payload=""):
        if frame_type == self.ACK:
            seq_num = payload
            payload_data = ""
        else:
            seq_num = self.mac_seq_num
            self.mac_seq_num += 1
            payload_data = payload

        mac_frame = {
            "src_mac": self.mac_address,
            "dest_mac": dest_mac,
            "seq_num": seq_num,
            "frame_type": frame_type,
            "payload_length": len(str(payload_data)),
            "payload": payload_data,
        }

        type_str = {1: "DATA", 2: "ACK", 3: "CONTROL"}.get(frame_type, "UNKNOWN")
        print(f"[{self.name}][MAC] Creating {type_str} frame: Dest={dest_mac}, Seq={seq_num}")

        for neighbor in self.neighbors:
            if dest_mac == self.BROADCAST_MAC or dest_mac == neighbor.mac_address:
                print(f"[{self.name}][MAC] Transmitting frame to one-hop neighbor {neighbor.name}")
                neighbor.receive_mac(mac_frame)

    def receive_mac(self, mac_frame):
        src_mac = mac_frame["src_mac"]
        dest_mac = mac_frame["dest_mac"]
        seq_num = mac_frame["seq_num"]
        frame_type = mac_frame["frame_type"]
        payload = mac_frame["payload"]

        type_str = {1: "DATA", 2: "ACK", 3: "CONTROL"}.get(frame_type, "UNKNOWN")
        print(f"[{self.name}][MAC] Received {type_str} frame from MAC {src_mac}")
        print(f"[{self.name}][MAC] Parsing MAC header and decapsulating payload")

        if frame_type == self.DATA:
            if dest_mac != self.BROADCAST_MAC:
                print(f"[{self.name}][MAC] Unicast DATA received. Generating ACK for Seq={seq_num}")
                self.send_mac(dest_mac=src_mac, frame_type=self.ACK, payload=seq_num)
            self.receive_ipv6(payload)
        elif frame_type == self.ACK:
            print(f"[{self.name}][MAC] ACK received for Seq={seq_num}. Transmission successful.")
        elif frame_type == self.CONTROL:
            print(f"[{self.name}][MAC] Broadcast CONTROL frame received. No ACK required.")
            self.receive_ipv6(payload)

    def send_ipv6(self, dest_ipv6, next_header, payload, dest_mac):
        ipv6_packet = {
            "src_ip": self.ipv6_address,
            "dst_ip": dest_ipv6,
            "next_header": next_header,
            "payload_length": len(str(payload)),
            "payload": payload,
        }
        print(f"[{self.name}][IPv6] Encapsulating message: Next Header={next_header}")
        frame_type = self.CONTROL if dest_mac == self.BROADCAST_MAC else self.DATA
        self.send_mac(dest_mac, frame_type, ipv6_packet)

    def _next_hop_for_ipv6(self, dest_ipv6):
        if dest_ipv6 == self.ipv6_address:
            return None

        if dest_ipv6 == "2001:db8::1" and self.name == "A":
            return "wired_server"

        if self.preferred_parent:
            if dest_ipv6 == "2001:db8::1":
                parent = Node.find_by_name(self.preferred_parent)
                if parent is not None:
                    return parent
            target = Node.find_by_ipv6(dest_ipv6)
            if target is not None:
                current = target
                while current is not None and current.name != self.name:
                    if current.preferred_parent == self.name:
                        return current
                    if current.preferred_parent is None:
                        break
                    current = Node.find_by_name(current.preferred_parent)
            parent = Node.find_by_name(self.preferred_parent)
            if parent is not None:
                return parent

        target = Node.find_by_ipv6(dest_ipv6)
        if target is not None:
            current = target
            while current is not None and current.preferred_parent is not None and current.preferred_parent != self.name:
                current = Node.find_by_name(current.preferred_parent)
            if current is not None and current.preferred_parent == self.name:
                return current

        if self.name == "A":
            for neighbor in self.neighbors:
                if neighbor.preferred_parent == self.name:
                    return neighbor

        return None

    def forward_ipv6(self, ipv6_packet, next_hop):
        if next_hop == "wired_server":
            print(f"[{self.name}][IPv6] Forwarding packet to wired CoAP server")
            if Node.server is not None:
                Node.server.receive_ipv6(ipv6_packet)
            return

        if next_hop is None:
            print(f"[{self.name}][IPv6] No route for destination {ipv6_packet['dst_ip']}; dropping packet")
            return

        print(f"[{self.name}][IPv6] Forwarding IPv6 packet to next hop {next_hop.name} while keeping original IPv6 header")
        self.send_mac(dest_mac=next_hop.mac_address, frame_type=self.DATA, payload=ipv6_packet)

    def receive_ipv6(self, ipv6_packet):
        next_header = ipv6_packet["next_header"]
        src_ip = ipv6_packet["src_ip"]
        dst_ip = ipv6_packet["dst_ip"]
        payload = ipv6_packet["payload"]
        print(f"[{self.name}][IPv6] Parsing IPv6 packet: Next Header={next_header}")

        if next_header == self.NH_ICMPV6:
            print(f"[{self.name}][IPv6] Passing ICMPv6 payload to RPL")
            sender_node = Node.registry.get(src_ip)
            src_name = sender_node.name if sender_node else src_ip
            self.receive_rpl(payload, src_name)
            return

        if next_header == self.NH_UDP:
            print(f"[{self.name}][IPv6] Passing UDP payload to UDP layer")
            sender_node = Node.registry.get(src_ip)
            src_name = sender_node.name if sender_node else src_ip
            if dst_ip == self.ipv6_address:
                self.receive_udp(payload, src_ip, dst_ip, src_name)
            elif dst_ip == "2001:db8::1" and self.name == "A":
                print(f"[{self.name}][IPv6] Receiving packet for wired CoAP server; handing it off locally")
                if Node.server is not None:
                    Node.server.receive_ipv6({
                        "src_ip": src_ip,
                        "dst_ip": dst_ip,
                        "next_header": self.NH_UDP,
                        "payload": payload,
                    })
                else:
                    print(f"[{self.name}][IPv6] No server instance configured; dropping packet")
            else:
                next_hop = self._next_hop_for_ipv6(dst_ip)
                if next_hop is None:
                    print(f"[{self.name}][IPv6] No route to {dst_ip}; dropping packet")
                    return
                self.forward_ipv6(ipv6_packet, next_hop)
            return

        print(f"[{self.name}][IPv6] Unhandled Next Header={next_header}, dropping packet")

    def send_udp(self, dest_ipv6, source_port, dest_port, payload, next_hop):
        udp_packet = {
            "src_port": source_port,
            "dst_port": dest_port,
            "length": 8 + len(str(payload)),
            "checksum": "0x00",
            "payload": payload,
        }
        print(f"[{self.name}][UDP] Creating UDP datagram: SrcPort={source_port}, DstPort={dest_port}, DstIPv6={dest_ipv6}")
        if next_hop == "wired_server":
            print(f"[{self.name}][UDP] Delivering datagram directly to the wired CoAP server")
            if Node.server is not None:
                Node.server.receive_ipv6({
                    "src_ip": self.ipv6_address,
                    "dst_ip": dest_ipv6,
                    "next_header": self.NH_UDP,
                    "payload": udp_packet,
                })
            else:
                print(f"[{self.name}][UDP] CoAP server is unavailable; dropping packet")
            return

        if hasattr(next_hop, "mac_address"):
            self.send_ipv6(dest_ipv6=dest_ipv6, next_header=self.NH_UDP, payload=udp_packet, dest_mac=next_hop.mac_address)
        else:
            print(f"[{self.name}][UDP] Invalid next hop for destination {dest_ipv6}; dropping packet")

    def receive_udp(self, udp_packet, src_ip, dst_ip, src_name):
        print(f"[{self.name}][UDP] Received UDP packet from {src_name}: SrcPort={udp_packet['src_port']}, DstPort={udp_packet['dst_port']}, DstIPv6={dst_ip}")

        if dst_ip == self.ipv6_address:
            if udp_packet["dst_port"] == 5683 and self.name == "Server":
                print(f"[{self.name}][UDP] Port matches CoAP server, passing UDP payload to CoAP")
                self.receive_coap(udp_packet["payload"], src_name, src_ip, udp_packet["src_port"], udp_packet["dst_port"])
                return
            if udp_packet["dst_port"] == 50000 and self.name != "Server":
                print(f"[{self.name}][UDP] Port matches client request; passing UDP payload to CoAP")
                self.receive_coap(udp_packet["payload"], src_name, src_ip, udp_packet["src_port"], udp_packet["dst_port"])
                return
            print(f"[{self.name}][UDP] Destination port not recognized; dropping packet")
            return

        if self.name == "A" and dst_ip == "2001:db8::1":
            print(f"[{self.name}][UDP] Forwarding packet to the wired CoAP server")
            if Node.server is not None:
                Node.server.receive_ipv6({
                    "src_ip": src_ip,
                    "dst_ip": dst_ip,
                    "next_header": self.NH_UDP,
                    "payload": udp_packet,
                })
            return

        next_hop = self._next_hop_for_ipv6(dst_ip)
        if next_hop is None:
            print(f"[{self.name}][UDP] No route to {dst_ip}; dropping packet")
            return

        print(f"[{self.name}][UDP] Forwarding packet to next hop {next_hop.name} for destination {dst_ip}")
        self.forward_ipv6({
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "next_header": self.NH_UDP,
            "payload": udp_packet,
        }, next_hop)

    def _coap_type_name(self, message_type):
        return {0: "CON", 1: "NON", 2: "ACK", 3: "RST"}.get(message_type, "UNKNOWN")

    def send_coap(self, dest_ipv6, source_port, dest_port, uri_path, payload, message_type=0, code=2):
        token = f"{self.name.lower()}-{self.coap_token_counter:02d}"
        self.coap_token_counter += 1
        message_id = self.coap_message_id
        self.coap_message_id += 1
        coap_message = {
            "version": 1,
            "type": message_type,
            "token_length": len(token),
            "code": code,
            "message_id": message_id,
            "token": token,
            "options": [{"name": "Uri-Path", "value": uri_path}] if uri_path else [],
            "payload": payload,
        }
        next_hop = self._next_hop_for_ipv6(dest_ipv6)
        print(f"[{self.name}][CoAP] Creating {self._coap_type_name(message_type)} message to {dest_ipv6}: Code={code}, Token={token}, Message ID={message_id}")
        self.send_udp(dest_ipv6=dest_ipv6, source_port=source_port, dest_port=dest_port, payload=coap_message, next_hop=next_hop)

    def receive_coap(self, coap_message, src_name, src_ip, src_port, dst_port):
        print(f"[{self.name}][CoAP] Received message from {src_name}: Type={coap_message['type']}, Code={coap_message['code']}, Token={coap_message['token']}, Message ID={coap_message['message_id']}")

        if self.name == "Server" and dst_port == 5683 and coap_message.get("code") == 2:
            uri_path = None
            for option in coap_message.get("options", []):
                if option["name"] == "Uri-Path":
                    uri_path = option["value"]
            sensor_value = coap_message.get("payload")
            print(f"[{self.name}][CoAP] Processing POST /{uri_path}: {sensor_value}")
            ack_message = {
                "version": 1,
                "type": 2,
                "token_length": len(coap_message["token"]),
                "code": 69,
                "message_id": coap_message["message_id"],
                "token": coap_message["token"],
                "options": [],
                "payload": f"ACK: sensor value {sensor_value} accepted",
            }
            print(f"[{self.name}][CoAP] Sending piggybacked ACK response to {src_ip}")
            root = Node.find_by_name("A")
            if root is not None:
                root.receive_ipv6({
                    "src_ip": self.ipv6_address,
                    "dst_ip": src_ip,
                    "next_header": self.NH_UDP,
                    "payload": {
                        "src_port": 5683,
                        "dst_port": src_port,
                        "length": 8 + len(str(ack_message)),
                        "checksum": "0x00",
                        "payload": ack_message,
                    },
                })
            return

        if coap_message.get("type") == 2 and coap_message.get("code") == 69:
            print(f"[{self.name}][CoAP] Received ACK response: {coap_message['payload']}")
            return

        if coap_message.get("type") == 0 and coap_message.get("code") == 2:
            print(f"[{self.name}][CoAP] Unhandled CoAP request; dropping packet")

    def send_rpl_dio(self):
        dio = {"type": self.RPL_TYPE, "code": self.RPL_CODE_DIO, "rank": self.rank}
        print(f"[{self.name}][RPL] Creating DIO: Rank={self.rank}")
        self.send_ipv6(dest_ipv6="ff02::1a", next_header=self.NH_ICMPV6, payload=dio, dest_mac=self.BROADCAST_MAC)

    def receive_rpl(self, dio, src_name):
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
            self.send_rpl_dio()
        else:
            print(f"[{self.name}][RPL] Candidate Rank not better than current Rank={self.rank}; ignoring")