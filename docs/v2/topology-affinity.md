# Topology and affinity discovery

Status: initial Linux filesystem discovery, constrained affinity recommendations
and offline NVIDIA matrix import implemented; fixture-tested, not hardware-validated.

## Available now

```bash
omnismi topology
omnismi topology --input topology.json --recommend-affinity --device pci:0000:41:00.0
omnismi topology --nvidia-matrix saved-nvidia-topo.txt
```

Python APIs in `omnismi.topology`: `discover_topology`, `recommend_affinity`,
`parse_nvidia_matrix`, `parse_cpu_list`. The CLI emits JSON with exit 0 PASS,
1 WARN, 3 INCONCLUSIVE, 64 invalid input. Discovery status describes collection,
not hardware health. `--device` requires the stable graph ID, not a GPU ordinal.

The collector reads Linux sysfs PCI identities, ancestry, link speed/width,
NUMA locality, NIC and RDMA-interface attachment. PCI display/processing class
is labeled an accelerator *candidate*, not a confirmed supported compute device.
Process CPU and memory masks come from `/proc/self/status`, including effective
cpuset restrictions. Suggestions intersect local CPUs and allowed memory nodes;
missing masks/NUMA or an empty intersection never yield an arbitrary binding.
No affinity, hardware configuration or scheduler state is changed.

Linux-only live discovery returns explicit INCONCLUSIVE on other platforms.
Python callers can inject filesystem roots to replay fixtures. Directory entry
and file-size bounds avoid unlimited enumeration; missing data remains null or
an explicit limitation. CPU/node masks are bounded to identifiers 0..65535.

NVIDIA import accepts a complete symmetric `nvidia-smi topo -m` matrix, preserving
path labels and NVLink bond count. It does not invoke the tool or join its GPU/NIC
ordinals to PCI identities. Matrix CPU-affinity columns are not used as process
permission evidence. Unknown layouts fail explicitly. NVLink bond count is not
measured bandwidth, direct-link proof or confirmation that P2P/RDMA is enabled.

Remaining: vendor API live collectors and identity joins, MIG/partition modeling,
AMD/PPU/Cambricon interconnects, cgroup-change/race handling and hardware validation.
The graph is a point-in-time visible-filesystem view, not a complete cluster graph.
Official references: Linux PCI sysfs and proc documentation (embedded in reports),
and NVIDIA's topology command reference (embedded in imported matrices).

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
