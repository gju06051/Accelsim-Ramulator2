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

#ifdef __cplusplus
}
#endif

#endif
