#pragma once

#include <stddef.h>

int dm_credentials_set_server(const char *server_url);
int dm_credentials_get_server(char *buffer, size_t capacity);
int dm_credentials_set_enrollment_token(const char *token);
int dm_credentials_get_enrollment_token(char *buffer, size_t capacity);
int dm_credentials_clear_enrollment_token(void);
int dm_credentials_set_agent_credential(const char *credential_id, const char *credential);
int dm_credentials_get_agent_credential(
    char *credential_id,
    size_t credential_id_capacity,
    char *credential,
    size_t credential_capacity
);
