#pragma once
#include <stdbool.h>
#include <stddef.h>

#define DM_URL_MAX 256
#define DM_TOKEN_MAX 192
#define DM_SSID_MAX 33
#define DM_PASSWORD_MAX 65
#define DM_AGENT_ID_MAX 40

typedef struct {
    char ssid[DM_SSID_MAX];
    char password[DM_PASSWORD_MAX];
    char server_url[DM_URL_MAX];
    char enrollment_token[DM_TOKEN_MAX];
    char agent_credential[DM_TOKEN_MAX];
    char probe_host[64];
} dm_config_t;

int dm_storage_init(void);
int dm_storage_load(dm_config_t *out);
int dm_storage_save_provisioning(const dm_config_t *config);
int dm_storage_save_credential(const char *credential);
int dm_storage_clear_credential(void);
int dm_identity(char *buffer, size_t capacity);
bool dm_config_is_provisioned(const dm_config_t *config);
