#include "security.h"

#include "esp_flash_encrypt.h"
#include "esp_log.h"
#include "esp_secure_boot.h"

static const char *TAG = "dm_security";

int dm_security_assert_runtime(void) {
#if CONFIG_DM_REQUIRE_HARDENING
    if (!esp_flash_encryption_enabled()) {
        ESP_LOGE(TAG, "Production hardening requires ESP32 flash encryption");
        return -1;
    }
    if (!esp_secure_boot_enabled()) {
        ESP_LOGE(TAG, "Production hardening requires ESP32 Secure Boot");
        return -1;
    }
    ESP_LOGI(TAG, "Secure Boot and flash encryption verified");
#endif
    return 0;
}
