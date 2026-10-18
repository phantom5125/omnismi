/* Omnismi's read-only CNDEV process boundary. Compile against the installed SDK.
 * API usage: Cambricon/mlu-exporter, revision 648a19c7d781ada2ea693e46edc562aa57f79be4.
 * All vendor structure layouts/prototypes come from cndev.h, never Python guesses.
 */
#include <cndev.h>
#include <stdio.h>
#include <string.h>

static void string_value(const char *s, size_t capacity) {
    putchar('"');
    if (s) for (size_t i = 0; i < capacity && s[i]; ++i) {
        unsigned char c = (unsigned char)s[i];
        if (c == '"' || c == '\\') { putchar('\\'); putchar(c); }
        else if (c < 32 || c >= 127) printf("\\u%04x", (unsigned)c);
        else putchar(c);
    }
    putchar('"');
}

static void number_value(cndevRet_t ret, long double value) {
    if (ret == CNDEV_SUCCESS) printf("%.6Lf", value);
    else fputs("null", stdout);
}

int main(int argc, char **argv) {
    if (argc != 2 || strcmp(argv[1], "--snapshot")) {
        fputs("Use --snapshot\n", stderr);
        return 64;
    }
    cndevRet_t ret = cndevInit(0);
    if (ret != CNDEV_SUCCESS) { fprintf(stderr, "CNDEV init: %d\n", (int)ret); return 1; }
    cndevCardInfo_t cards = {0};
    cards.version = CNDEV_VERSION_6;
    ret = cndevGetDeviceCount(&cards);
    if (ret != CNDEV_SUCCESS || cards.number > 4096) {
        fprintf(stderr, "CNDEV inventory: %d\n", (int)ret);
        cndevRelease(); return 1;
    }
    fputs("{\"schema_version\":1,\"collector\":\"omnismi-cndev\",\"sdk_api\":6,\"devices\":[", stdout);
    for (unsigned i = 0; i < (unsigned)cards.number; ++i) {
        cndevDevice_t handle;
        ret = cndevGetDeviceHandleByIndex((int)i, &handle);
        if (ret != CNDEV_SUCCESS) { cndevRelease(); return 1; }
        cndevUUID_t uuid = {0};
        uuid.version = CNDEV_VERSION_6;
        ret = cndevGetUUID(&uuid, handle);
        if (ret != CNDEV_SUCCESS) { cndevRelease(); return 1; }
        const char *name = cndevGetCardNameStringByDevId(handle);
        cndevVersionInfo_t version = {0};
        version.version = CNDEV_VERSION_6;
        cndevRet_t vr = cndevGetVersionInfo(&version, handle);
        cndevMemoryInfoV2_t memory = {0};
        cndevRet_t mr = cndevGetMemoryUsageV2(&memory, handle);
        cndevDevicePowerInfo_t power = {0};
        cndevRet_t pr = cndevGetDevicePowerInfo(&power, handle);
        cndevFrequencyInfo_t frequency = {0};
        frequency.version = CNDEV_VERSION_6;
        cndevRet_t fr = cndevGetFrequencyInfo(&frequency, handle);
        cndevTemperatureInfo_t temperature = {0};
        temperature.version = CNDEV_VERSION_6;
        cndevRet_t tr = cndevGetTemperatureInfo(&temperature, handle);
        cndevUtilizationInfo_t utilization = {0};
        utilization.version = CNDEV_VERSION_6;
        cndevRet_t ur = cndevGetDeviceUtilizationInfo(&utilization, handle);
        if (i) putchar(',');
        printf("{\"index\":%u,\"uuid\":", i);
        string_value((const char *)&uuid.uuid, sizeof(uuid.uuid));
        fputs(",\"name\":", stdout); string_value(name, 256);
        fputs(",\"driver\":", stdout);
        if (vr == CNDEV_SUCCESS) printf("\"%u.%u.%u\"", (unsigned)version.driverMajorVersion, (unsigned)version.driverMinorVersion, (unsigned)version.driverBuildVersion);
        else fputs("null", stdout);
        fputs(",\"memory_total_mib\":", stdout); number_value(mr, memory.globalMemory);
        fputs(",\"memory_used_mib\":", stdout); number_value(mr, memory.physicalMemoryUsed);
        fputs(",\"power_w\":", stdout); number_value(pr, power.usage);
        fputs(",\"core_clock_mhz\":", stdout); number_value(fr, frequency.boardFreq);
        fputs(",\"memory_clock_mhz\":", stdout); number_value(fr, frequency.ddrFreq);
        fputs(",\"temperature_c\":", stdout); number_value(tr, temperature.board);
        fputs(",\"utilization_percent\":", stdout); number_value(ur, utilization.averageCoreUtilization);
        printf(",\"return_codes\":{\"memory\":%d,\"power\":%d,\"clock\":%d,\"temperature\":%d,\"utilization\":%d}}", (int)mr, (int)pr, (int)fr, (int)tr, (int)ur);
    }
    fputs("]}\n", stdout);
    ret = cndevRelease();
    return ret == CNDEV_SUCCESS ? 0 : 1;
}
