#pragma once

#include <stddef.h>

int dm_identity_init(void);
int dm_identity_get(char *buffer, size_t capacity);
int dm_identity_get_provisioning_pop(char *buffer, size_t capacity);
