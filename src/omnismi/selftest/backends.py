"""Framework execution only; all reference calculations live on the host."""

from __future__ import annotations


class UnsupportedCaseError(RuntimeError):
    """A requested execution path is unavailable, not a numerical failure."""


class TorchBackend:
    def __init__(self, vendor, device_index):
        import torch

        self.torch = torch
        if vendor == "cambricon":
            import torch_mlu  # noqa: F401

            self.runtime, kind = torch.mlu, "mlu"
        else:
            self.runtime, kind = torch.cuda, "cuda"
            if bool(torch.version.hip) != (vendor == "amd"):
                raise UnsupportedCaseError(
                    "PyTorch CUDA/ROCm build does not match vendor"
                )
        if (
            not self.runtime.is_available()
            or device_index >= self.runtime.device_count()
        ):
            raise UnsupportedCaseError("requested accelerator is unavailable")
        self.runtime.set_device(device_index)
        self.device = torch.device(f"{kind}:{device_index}")
        props = self.runtime.get_device_properties(device_index)
        self.identity = {
            "vendor": vendor,
            "runtime_device_index": device_index,
            "name": str(props.name),
            "uuid": str(getattr(props, "uuid", "")) or None,
            "framework": "pytorch",
            "framework_version": str(torch.__version__),
            "runtime_version": str(torch.version.hip or torch.version.cuda),
            "multiprocessor_count": getattr(props, "multi_processor_count", None),
            "execution_device": str(self.device),
        }
        # These settings are confined to the subprocess. Never alter clocks,
        # power caps, persistence mode, or the caller's framework defaults.
        if kind == "cuda":
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cuda.matmul.allow_fp16_reduced_precision_reduction = False
            torch.backends.cuda.matmul.allow_bf16_reduced_precision_reduction = False

    @classmethod
    def _for_cpu_tests(cls):
        """Internal adapter tests only. There is deliberately no CPU CLI backend."""
        import torch

        obj = cls.__new__(cls)
        obj.torch, obj.device, obj.runtime = torch, torch.device("cpu"), None
        obj.identity = {"vendor": "test", "execution_device": "cpu", "uuid": None}
        return obj

    def execute(self, case, a, b):
        torch = self.torch
        dtype = getattr(torch, case.dtype)

        def upload(value, selected_dtype):
            tensor = torch.tensor(
                value.copy(), dtype=selected_dtype, device=self.device
            )
            if case.layout == "strided":
                padded = torch.empty(
                    (tensor.shape[0], tensor.shape[1] * 2),
                    dtype=selected_dtype,
                    device=self.device,
                )
                padded[:, ::2] = tensor
                tensor = padded[:, ::2]
            return tensor

        x = upload(a, dtype)
        op = case.operator
        indices = None
        if op == "topk":
            value, indices = torch.topk(
                x, case.k, dim=-1, largest=case.largest, sorted=case.sorted
            )
        elif op == "sort":
            value, indices = torch.sort(x, dim=-1)
        elif op == "copy":
            value = x.clone()
        elif op == "sum":
            value = x.sum(dim=-1, dtype=torch.float32)
        else:
            y = upload(b, torch.int64 if op == "gather" else dtype)
            if op == "add":
                value = x + y
            elif op == "mul":
                value = x * y
            elif op == "gather":
                value = torch.gather(x, -1, y)
            elif op == "matmul":
                value = torch.matmul(x, y)
            else:
                raise UnsupportedCaseError(op)
        if self.runtime is not None:
            self.runtime.synchronize()

        def host(tensor):
            tensor = tensor.detach().cpu()
            return (
                tensor.float() if tensor.dtype == torch.bfloat16 else tensor
            ).numpy()

        return host(value), None if indices is None else host(indices)


class JaxBackend:
    def __init__(self, device_index):
        import jax

        devices = jax.devices("tpu")
        if device_index >= len(devices) or devices[device_index].platform != "tpu":
            raise UnsupportedCaseError("requested TPU is unavailable")
        self.jax, self.device = jax, devices[device_index]
        self.identity = {
            "vendor": "google",
            "runtime_device_index": device_index,
            "name": str(self.device.device_kind),
            "uuid": None,
            "framework": "jax",
            "framework_version": str(jax.__version__),
            "execution_device": str(self.device),
            "multiprocessor_count": None,
        }

    @classmethod
    def _for_cpu_tests(cls):
        import jax

        obj = cls.__new__(cls)
        obj.jax, obj.device = jax, jax.devices("cpu")[0]
        obj.identity = {"vendor": "test", "execution_device": "cpu", "uuid": None}
        return obj

    def execute(self, case, a, b):
        import jax.numpy as jnp
        import numpy as np

        if case.layout != "contiguous":
            raise UnsupportedCaseError(
                "XLA does not expose physical strided tensor storage"
            )
        jax = self.jax
        # default_device also constrains constants and intermediate allocations.
        with jax.default_device(self.device):
            x = jax.device_put(
                jnp.asarray(a, dtype=getattr(jnp, case.dtype)), self.device
            )
            op = case.operator
            indices = None
            if op == "topk":
                # Exact top_k, not approximate top-k. XLA always sorts output;
                # this is legal for sorted=False but is not an unsorted kernel.
                value, indices = jax.lax.top_k(x if case.largest else -x, case.k)
                value = value if case.largest else -value
            elif op == "sort":
                indices = jnp.argsort(x, axis=-1)
                value = jnp.take_along_axis(x, indices, axis=-1)
            elif op == "copy":
                value = jnp.copy(x)
            elif op == "sum":
                value = jnp.sum(x, axis=-1, dtype=jnp.float32)
            else:
                y = jax.device_put(
                    jnp.asarray(b, dtype=jnp.int32 if op == "gather" else x.dtype),
                    self.device,
                )
                if op == "add":
                    value = x + y
                elif op == "mul":
                    value = x * y
                elif op == "gather":
                    value = jnp.take_along_axis(x, y, axis=-1)
                elif op == "matmul":
                    value = jnp.matmul(x, y, precision=jax.lax.Precision.HIGHEST)
                else:
                    raise UnsupportedCaseError(op)
            value.block_until_ready()
            return np.asarray(
                value, dtype=np.float32 if case.dtype == "bfloat16" else None
            ), (None if indices is None else np.asarray(indices.block_until_ready()))


def connect(config):
    if config.vendor == "alibaba":
        raise UnsupportedCaseError(
            "The 2.1 SDC operator worker for SAIL is pending; "
            "the 2.0 SAIL copy/add/matmul probe "
            "does not implement this coverage protocol. No CPU fallback was used."
        )
    if config.vendor == "google":
        return JaxBackend(config.device)
    return TorchBackend(config.vendor, config.device)
