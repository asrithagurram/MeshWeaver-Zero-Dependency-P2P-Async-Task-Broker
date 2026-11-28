\# MeshWeaver Architecture



\## Overview



MeshWeaver is a task queue with no central broker. Every node runs the same program and can submit, route and execute tasks. Nodes find each other with a Kademlia DHT, share their load by gossip, and send tasks to the least-loaded live node.



\## Diagram



&#x20;   Client (CLI or Python API)

&#x20;         |  TLS + Ed25519-signed request

&#x20;         v

&#x20;   Gateway node (any node; it coordinates the task)

&#x20;         |  picks the lowest-load live node and watches its heartbeat

&#x20;         v

&#x20;   Executor node --> worker subprocess (runs the function, with a timeout)



&#x20;   All nodes talk to each other over UDP (DHT + gossip, protected by HMAC).



\## Components



| File | Role |

|---|---|

| meshweaver/dht.py | Kademlia routing table, lookups, key/value storage |

| meshweaver/gossip.py | CPU, RAM and task-count sharing between nodes |

| meshweaver/node.py | Node lifecycle, routing, heartbeat, re-routing, TCP server |

| meshweaver/serializer.py, worker.py | cloudpickle packing and the worker process |

| meshweaver/security.py | TLS certificate, HMAC, Ed25519 signing |

| meshweaver/client.py | Client API for submitting tasks |

| meshweaver/dashboard.py | Live rich dashboard |



\## How a task flows



1\. The client packs the function with cloudpickle, signs the request and sends it to any node (the gateway) over TLS.

2\. The gateway checks the signature, the timestamp and that the request is not a replay.

3\. The gateway scores every live node (CPU % plus a penalty for pending tasks) and picks the lowest.

4\. The chosen node verifies the signature again and runs the function in a separate worker process.

5\. While the task runs, the executor sends a heartbeat every second.

6\. The result goes back to the client, and the task state is stored in the DHT.



\## When a node dies



If the connection breaks or no heartbeat arrives for 5 seconds, the gateway marks the task failed, removes that node from its routing table, and sends the task to the next best node. A task is tried at most 3 times.



\## Ports



Each node uses one port number. UDP carries the DHT and gossip. TCP carries tasks, with TLS.

