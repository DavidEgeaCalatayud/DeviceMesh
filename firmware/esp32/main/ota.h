#pragma once

int dm_ota_apply(const char *url, const char *expected_sha256);
int dm_ota_confirm_running_image(void);
int dm_ota_cancel_pending_update(void);
