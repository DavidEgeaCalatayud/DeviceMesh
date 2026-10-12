#include "sensors.h"

#include <time.h>

#include "esp_heap_caps.h"
#include "esp_timer.h"
#include "wifi.h"

#if CONFIG_DM_BME280_ENABLED
#include "bme280.h"
#include "driver/i2c.h"
#include "i2c_bus.h"

static i2c_bus_handle_t s_i2c_bus;
static bme280_handle_t s_bme280;
static bool s_bme280_initialized;

static void try_init_bme280(void) {
    if (s_bme280_initialized) return;
    i2c_config_t config = {
        .mode = I2C_MODE_MASTER,
        .sda_io_num = CONFIG_DM_BME280_SDA_GPIO,
        .sda_pullup_en = GPIO_PULLUP_ENABLE,
        .scl_io_num = CONFIG_DM_BME280_SCL_GPIO,
        .scl_pullup_en = GPIO_PULLUP_ENABLE,
        .master.clk_speed = 100000,
    };
    s_i2c_bus = i2c_bus_create(I2C_NUM_0, &config);
    if (!s_i2c_bus) return;
    s_bme280 = bme280_create(s_i2c_bus, BME280_I2C_ADDRESS_DEFAULT);
    if (!s_bme280) return;
    if (bme280_default_init(s_bme280) != ESP_OK) return;
    s_bme280_initialized = true;
}
#endif

int dm_read_sensors(dm_telemetry_t *out) {
    if (!out) return -1;
    out->wifi_rssi = dm_wifi_rssi();
    out->free_heap_bytes = esp_get_free_heap_size();
    out->uptime_seconds = (uint64_t)(esp_timer_get_time() / 1000000ULL);
    out->sampled_at_unix = (int64_t)time(NULL);
    out->environment_sensor_valid = false;

#if CONFIG_DM_BME280_ENABLED
    try_init_bme280();
    if (s_bme280_initialized) {
        float temperature = 0.0f;
        float humidity = 0.0f;
        float pressure_pa = 0.0f;
        if (
            bme280_read_temperature(s_bme280, &temperature) == ESP_OK &&
            bme280_read_humidity(s_bme280, &humidity) == ESP_OK &&
            bme280_read_pressure(s_bme280, &pressure_pa) == ESP_OK
        ) {
            out->environment_sensor_valid = true;
            out->temperature_celsius = temperature;
            out->humidity_percent = humidity;
            out->pressure_hpa = pressure_pa / 100.0f;
        }
    }
#endif
    return 0;
}
