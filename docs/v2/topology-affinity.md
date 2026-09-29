# Topology discovery and affinity

```bash
omnismi topology
omnismi topology --collect-vendor nvidia --timeout 15
omnismi topology --collect-vendor alibaba --timeout 15
omnismi topology --nvidia-matrix saved-nvidia-topo.txt
omnismi topology --input topology.json --recommend-affinity --device pci:0000:41:00.0
```

The Linux collector reads PCI identity/ancestry/link properties, NUMA nodes,
NIC/RDMA attachments and the effective CPU/memory masks in `/proc/self/status`.
An unverified PCI accelerator class is a candidate, not a confirmed compute device.
Missing sysfs, permissions and NUMA node -1 remain explicit. Other platforms return
INCONCLUSIVE. All file enumeration and reads have finite limits.

`--collect-vendor` executes bounded read-only management queries. NVIDIA and SAIL
PPU collectors query index/UUID/PCI before and after `topo -m`; changed identities
reject the join. A complete symmetric matrix preserves NVLink or ICN bond counts
and PCI path labels. A bond count is not measured bandwidth, guaranteed direct
connection, or proof of peer access. Unknown formats fail explicitly.

The resulting graph joins GPU/PPU aliases to canonical PCI nodes and NIC legends
to discovered RDMA interfaces. Unresolved aliases/edges remain in collection
metadata. Device ordinals are not joined across tools by assumption. Snapshot
bracketing detects changes but is not an atomic driver transaction.

NVIDIA `-L` supplies MIG UUID/parent/profile records. MIG children link to their
physical PCI parent; they are not treated as independent physical fabric endpoints.
A failed partition query leaves physical results with a partial-collection reason.
Saved topology cannot be joined to live vendor identities implicitly.

`recommend_affinity(report, device_id)` intersects device-local CPUs and memory
nodes with effective process permissions. Unknown locality/masks or an empty
intersection never produces arbitrary bindings. Recommendations do not change
process affinity. Matrix CPU columns are not substituted for process permissions.
Use stable PCI IDs; for a partition, select its physical parent's PCI ID when
requesting a locality recommendation.

Python entry points: `discover_topology`, `recommend_affinity`, `parse_cpu_list`,
`parse_nvidia_matrix`, `parse_vendor_matrix` in `omnismi.topology`, and
`collect_vendor_topology` in `omnismi.topology_live`. CLI returns 0 PASS, 1 WARN,
3 INCONCLUSIVE or 64 invalid input. Status describes collection completeness,
not hardware health. Containers may expose only part of the host graph.

References: [Linux PCI](https://docs.kernel.org/PCI/sysfs-pci.html),
[effective process masks](https://docs.kernel.org/filesystems/proc.html),
[NVIDIA management topology](https://docs.nvidia.com/deploy/nvidia-smi/index.html#topology),
[SAIL PPU-SMI section 9](https://developer.t-head.cn/docs_center/doc_detail/index.html?projectId=39&chapterId=221).
AMD/Cambricon proprietary fabric collectors and runtime visibility still require
separate SDK/hardware evidence; generic PCI/NUMA/NIC discovery works independently.
