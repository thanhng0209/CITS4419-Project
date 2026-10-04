"""
Simulation entry point.
 
Builds the 5-node network defined by the project spec, links neighbors,
runs setup(), then kicks off RPL topology construction from node A (the
root). Part C will extend this with the interactive "select part / select
source node" prompts, once UDP/CoAP are added to node.py.
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
        "E": Node("E", "00:00:00:05", "fd00::5", ["C"])
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

