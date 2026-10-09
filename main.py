"""
Simulation entry point.

Builds the 5-node wireless network defined by the project spec, links neighbors,
runs setup(), then constructs the RPL topology from node A. It also creates the
wired CoAP server instance and demonstrates the Part C UDP/CoAP packet flow from
node D to the server at 2001:db8::1.
"""
from node import Node

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
        "E": Node("E", "00:00:00:05", "fd00::5", ["C"]),
        "Server": Node("Server", "00:00:01:02", "2001:db8::1", [])
    }

    # 2. Link the neighbors and call setup()
    print("--- INITIALIZING IOT NETWORK ---")
    for node in nodes.values():
        node.link_neighbors(nodes)
        node.setup()

    nodes["A"].rank = 0
    nodes["A"].send_rpl_dio()

    print("\n--- RPL TOPOLOGY CONVERGED ---")
    for n in nodes.values():
        print(f"{n.name}: Rank={n.rank}, Parent={n.preferred_parent}")

    print("\n--- PART C: NODE D -> SERVER COAP POST ---")
    nodes["D"].send_coap(
        dest_ipv6="2001:db8::1",
        source_port=50000,
        dest_port=5683,
        uri_path="temperature",
        payload="27.5",
        message_type=0,
        code=2,
    )

