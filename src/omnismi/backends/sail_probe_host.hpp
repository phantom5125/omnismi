// Host control for sail_probe.hg. The including translation unit supplies
// hggc_runtime.h and the three sail_* launch functions.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

static std::string quote(const std::string &value) {
    std::ostringstream out;
    out << '"';
    for (unsigned char ch : value) {
        if (ch == '"' || ch == '\\') out << '\\' << ch;
        else if (ch < 32) out << "\\u" << std::hex << std::setw(4)
                              << std::setfill('0') << int(ch) << std::dec;
        else out << ch;
    }
    out << '"';
    return out.str();
}

static void checked(hggcError_t code) {
    if (code != hggcSuccess)
        throw std::runtime_error(hggcGetErrorString(code));
}

struct Buffer {
    float *data = nullptr;
    explicit Buffer(size_t bytes) {
        checked(hggcMalloc(reinterpret_cast<void **>(&data), bytes));
    }
    ~Buffer() { if (data) hggcFree(data); }
    Buffer(const Buffer &) = delete;
    Buffer &operator=(const Buffer &) = delete;
};

static int integer(const char *raw, int minimum, int maximum) {
    std::string text(raw);
    if (text.empty() || text.find_first_not_of("0123456789") != std::string::npos)
        throw std::invalid_argument("Invalid integer argument");
    size_t end = 0;
    long value = std::stol(text, &end);
    if (end != text.size() || value < minimum || value > maximum)
        throw std::invalid_argument("Argument outside resource bounds");
    return static_cast<int>(value);
}

static void execute_probe(const std::string &mode, int device, int memory_mib,
                          int repeats, const std::string &pattern) {
    int devices = 0, runtime_version = 0, driver_version = 0;
    checked(hggcGetDeviceCount(&devices));
    if (device >= devices) throw std::runtime_error("SAIL runtime device unavailable");
    checked(hggcSetDevice(device));
    hggcDeviceProp props{};
    checked(hggcGetDeviceProperties(&props, device));
    checked(hggcRuntimeGetVersion(&runtime_version));
    checked(hggcDriverGetVersion(&driver_version));
    size_t budget = size_t(memory_mib) * 1024 * 1024;
    int n = 64;
    while (n < 2048 && size_t(n * 2) * (n * 2) * 12 <= budget) n *= 2;
    const bool compute = mode == "compute";
    const size_t count = compute ? size_t(n) * n : budget / 12;
    const size_t bytes = count * sizeof(float);
    Buffer a(bytes), b(bytes), c(bytes);
    std::vector<float> input(count), output(count);
    std::vector<std::string> checks;
    bool passed = true;
    auto verify = [&](const char *name, bool ok) {
        checks.push_back("{\"name\":" + quote(name) + ",\"passed\":"
                         + (ok ? "true}" : "false}"));
        passed = passed && ok;
    };
    auto synchronize = [&]() {
        checked(hggcGetLastError());
        checked(hggcDeviceSynchronize());
    };
    auto upload = [&](float *to) {
        checked(hggcMemcpy(to, input.data(), bytes, hggcMemcpyHostToDevice));
    };
    auto download = [&]() {
        synchronize();
        checked(hggcMemcpy(output.data(), c.data, bytes, hggcMemcpyDeviceToHost));
    };
    // Position-dependent, exactly representable patterns catch addressing errors
    // that constant-only fills cannot detect. Four seeds cover sign and scale.
    for (float seed : {0.0f, 1.0f, -1.0f, 65536.0f}) {
        for (size_t i = 0; i < count; ++i) input[i] = seed + float(i % 257);
        upload(a.data);
        upload(b.data);
        sail_copy(a.data, c.data, count);
        download();
        verify("memory_copy", input == output);
        sail_add(a.data, b.data, c.data, count);
        download();
        for (float &value : input) value *= 2;
        verify("vector_add", input == output);
    }
    std::vector<double> seconds;
    if (passed && mode == "self-test") {
        // Reuse the allocated buffers; this operation needs only a 64x64 prefix.
        const int small = 64;
        std::fill(input.begin(), input.end(), 1.0f);
        upload(a.data);
        upload(b.data);
        sail_matmul(a.data, b.data, c.data, small);
        download();
        verify("matrix_multiply", std::all_of(output.begin(), output.begin() + small * small,
                                              [](float value) { return value == 64.0f; }));
    } else if (passed) {
        std::fill(input.begin(), input.end(), 1.0f);
        upload(a.data);
        std::fill(input.begin(), input.end(), 2.0f);
        upload(b.data);
        auto operation = [&]() {
            if (compute) sail_matmul(a.data, b.data, c.data, n);
            else if (pattern == "copy") sail_copy(a.data, c.data, count);
            else sail_add(a.data, b.data, c.data, count);
        };
        for (int warmup = 0; warmup < 5; ++warmup) operation();
        synchronize();
        for (int sample = 0; sample < repeats; ++sample) {
            auto start = std::chrono::steady_clock::now();
            for (int iteration = 0; iteration < 20; ++iteration) operation();
            synchronize();
            double elapsed = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - start).count();
            if (!std::isfinite(elapsed) || elapsed <= 0)
                throw std::runtime_error("Invalid measurement interval");
            seconds.push_back(elapsed);
        }
        download();
        float expected = compute ? float(2 * n) : (pattern == "copy" ? 1.0f : 3.0f);
        verify("timed_result", std::all_of(output.begin(), output.end(),
                                           [=](float value) { return value == expected; }));
    }
    std::cout << std::setprecision(17)
              << "{\"schema_version\":1,\"collector\":\"omnismi-sail-probe\","
              << "\"probe_version\":\"hggc-tiled16-v1\",\"status\":"
              << quote(passed ? "PASS" : "FAIL")
              << ",\"mode\":" << quote(mode) << ",\"pattern\":" << quote(pattern)
              << ",\"identity\":{\"vendor\":\"alibaba\",\"name\":" << quote(props.name)
              << ",\"runtime_device_index\":" << device
              << ",\"runtime_version\":" << runtime_version
              << ",\"driver_version\":" << driver_version
              // The documented property has no function number. Do not invent a BDF.
              << ",\"pci_location\":{\"domain\":" << props.pciDomainID
              << ",\"bus\":" << props.pciBusID << ",\"device\":" << props.pciDeviceID
              << "}},\"buffer_bytes\":" << bytes
              << ",\"matrix_dimension\":" << (compute ? n : 64)
              << ",\"iterations\":20,\"checks\":[";
    for (size_t i = 0; i < checks.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << checks[i];
    }
    std::cout << "],\"seconds\":[";
    for (size_t i = 0; i < seconds.size(); ++i) {
        if (i) std::cout << ',';
        std::cout << seconds[i];
    }
    std::cout << "]}" << std::endl;
}

int main(int argc, char **argv) {
    try {
        if (argc != 7 || std::string(argv[1]) != "--run")
            throw std::invalid_argument("Expected --run MODE DEVICE MEMORY_MIB REPEATS PATTERN");
        std::string mode(argv[2]), pattern(argv[6]);
        if ((mode != "self-test" && mode != "bandwidth" && mode != "compute") ||
            (pattern != "copy" && pattern != "triad"))
            throw std::invalid_argument("Unsupported mode or pattern");
        int device = integer(argv[3], 0, 4095);
        int memory_mib = integer(argv[4], 1, 4096);
        int repeats = integer(argv[5], 2, 100);
        execute_probe(mode, device, memory_mib, repeats, pattern);
    } catch (const std::exception &error) {
        std::cout << "{\"schema_version\":1,\"collector\":\"omnismi-sail-probe\","
                  << "\"probe_version\":\"hggc-tiled16-v1\",\"status\":\"INCONCLUSIVE\","
                  << "\"reason\":\"SAIL_runtime_error\",\"detail\":"
                  << quote(error.what()) << "}" << std::endl;
    }
    return 0;
}
