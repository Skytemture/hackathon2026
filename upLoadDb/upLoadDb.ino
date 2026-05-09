#include <WiFi.h>

const char* ssid = "esp32test";
const char* password = "12345678";

void setup()
{
    Serial.begin(115200);
    delay(2000);

    Serial.println("ESP32-S3 Boot");

    // 🔥 超重要：完整重置 Wi-Fi
    WiFi.mode(WIFI_STA);
    WiFi.disconnect(true, true);
    delay(1000);

    Serial.println("Connecting...");

    WiFi.begin(ssid, password);

    int retry = 0;

    while (WiFi.status() != WL_CONNECTED)
    {
        delay(1000);

        Serial.print(".");
        Serial.print(" status=");
        Serial.println(WiFi.status());

        retry++;

        if (retry > 30)
        {
            Serial.println("WiFi FAIL");
            return;
        }
    }

    Serial.println("\nWiFi CONNECTED");
    Serial.println(WiFi.localIP());
}

void loop() {}