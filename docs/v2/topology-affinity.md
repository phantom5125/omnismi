# Topology and affinity discovery

Status: planned; topology collectors and recommendations are not implemented.

## User-facing contract

```text
omnismi topology
omnismi topology --input topology-snapshot.json
omnismi topology --recommend-affinity --device 0
```

Proposed Python: `discover_topology()` and `recommend_affinity(topology, devices,
allowed_cpus=None, allowed_nodes=None)`. Return a graph plus evidence, not just an
ASCII matrix. Discovery and recommendations never change process affinity.

## Graph and scope

Nodes: accelerator, PCI device/bridge, CPU NUMA node, NIC and RDMA interface.
Edges: PCIe ancestry, NVLink peer, NUMA locality and NIC-to-PCI identity. Stable IDs
use PCI BDF/UUID/sysfs identities; runtime ordinals are aliases with source/scope.
Every edge records collector, evidence and collection time. Unknown connectivity
is distinct from an observed absence. Advertised speed is not measured bandwidth.

Collect link generation/width/current state when available. Interpret vendor path
labels according to that tool's documented version, not an invented latency score.
Keep NVSwitch and NVLink peer connectivity distinct from general PCIe reachability.

NUMA node -1 means unknown. CPU recommendations intersect device locality with
process affinity and effective cgroup cpusets; memory recommendations intersect
allowed memory nodes. An empty intersection returns no usable recommendation.
Containers may expose incomplete sysfs or a topology different from the host.
Physical NIC locality does not prove RDMA, GPUDirect or P2P is enabled.

## Implementation sequence

1. `topology/models.py`: normalized graph, collector results and stable identity.
2. `topology/linux.py`: injectable read-only sysfs root for PCI/NUMA/network/RDMA
   relationships, sparse CPU-list parsing, process/cgroup restrictions.
3. `topology/nvidia.py`: optional documented NVIDIA topology output/API adapter,
   versioned fixtures, bounded command execution with argv and no shell.
4. `topology/affinity.py`: deterministic allowed-locality recommendations and
   explanations; unknown locality yields INCONCLUSIVE rather than arbitrary binding.
5. CLI offline/live modes; extend AMD and other vendor link collectors after
   verifying their official interfaces. Integrate as optional perf-doctor evidence.

## Acceptance

Fixture tests cover dual-socket/multi-GPU, NVLink and PCIe-only nodes, NIC locality,
MIG parent/child identity, missing permissions, NUMA -1, sparse CPU masks, restricted
cpusets, empty intersections and disappearing devices. Unknown tools/platforms
return partial reports. Hardware validation compares with official tool output;
no mutation commands or automatic job placement are permitted by discovery.
