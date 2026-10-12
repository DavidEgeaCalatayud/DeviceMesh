#include "recovery.h"

#include "credentials.h"
#include "driver/gpio.h"
#include "esp_log.h"
#include "esp_wifi.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "offline_queue.h"

#ifndef CONFIG_DM_RECOVERY_GPIO
#define CONFIG_DM_RECOVERY_GPIO 0
#endif

static const char *TAG = "dm_recovery";

int dm_recovery_requested(void) {
    gpio_config_t config = {
        .pin_bit_mask = 1ULL << CONFIG_DM_RECOVERY_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    if (gpio_config(&config) != ESP_OK) return 0;
    if (gpio_get_level(CONFIG_DM_RECOVERY_GPIO) != 0) return 0;

    ESP_LOGW(TAG, "Recovery button held; confirm for 3 seconds");
    vTaskDelay(pdMS_TO_TICKS(3000));
    return gpio_get_level(CONFIG_DM_RECOVERY_GPIO) == 0 ? 1 : 0;
}

int dm_recovery_execute(void) {
    int result = 0;
    if (dm_credentials_clear_all() != 0) result = -1;
    if (dm_offline_queue_clear() != 0) result = -1;
    if (esp_wifi_restore() != ESP_OK) result = -1;
    ESP_LOGW(TAG, "Provisioning state reset; persistent device identity retained");
    return result;
}
