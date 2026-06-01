#ifndef SGRAM_RAMULATOR2_C_API_H
#define SGRAM_RAMULATOR2_C_API_H

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*sgram_ramulator2_complete_cb)(
    void *user, void *payload, unsigned long long addr, int type,
    int source_id, long long arrive, long long depart);

void *sgram_ramulator2_create(const char *config_path);
void sgram_ramulator2_destroy(void *handle);
int sgram_ramulator2_send(void *handle, unsigned long long addr, int type,
                          int source_id, void *payload, void *user,
                          sgram_ramulator2_complete_cb callback);
void sgram_ramulator2_tick(void *handle);
void sgram_ramulator2_finalize(void *handle);
double sgram_ramulator2_tck_ns(void *handle);
unsigned long long sgram_ramulator2_ticks(void *handle);
unsigned long long sgram_ramulator2_outstanding_reads(void *handle);
unsigned long long sgram_ramulator2_callback_untracked_writes(void *handle);
unsigned long long sgram_ramulator2_accepted_reads(void *handle);
unsigned long long sgram_ramulator2_completed_reads(void *handle);
unsigned long long sgram_ramulator2_accepted_writes(void *handle);
unsigned long long sgram_ramulator2_completed_writes(void *handle);
unsigned long long sgram_ramulator2_read_latency_samples(void *handle);
unsigned long long sgram_ramulator2_read_latency_sum(void *handle);
unsigned long long sgram_ramulator2_read_latency_max(void *handle);
double sgram_ramulator2_read_latency_avg(void *handle);
unsigned long long sgram_ramulator2_read_latency_p50(void *handle);
unsigned long long sgram_ramulator2_read_latency_p90(void *handle);
unsigned long long sgram_ramulator2_read_latency_p95(void *handle);
unsigned long long sgram_ramulator2_read_latency_p99(void *handle);

#ifdef __cplusplus
}
#endif

#endif
