#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// AUDIO (WAV)
#include <AudioFileSourceHTTPStream.h>
#include <AudioGeneratorWAV.h>
#include <AudioOutputI2S.h>
             
const char* ssid = "";
const char* password = "";

// -------- Server --------
String serverURL = "https://smart-blind-stick-flask.onrender.com/upload";

// -------- Button --------
#define BUTTON_PIN 15   // button -> GND

// -------- Camera Pins (AI THINKER) --------
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// -------- WAV AUDIO OBJECTS --------
AudioGeneratorWAV *wav = nullptr;
AudioFileSourceHTTPStream *file = nullptr;
AudioOutputI2S *out = nullptr;

void stopAudio() {
  if (wav) { wav->stop(); delete wav; wav = nullptr; }
  if (file) { delete file; file = nullptr; }
  if (out)  { delete out;  out = nullptr; }
  delay(10);
}

// =====================================================
//            WAV PLAYBACK (WITH URL CHECK)
// =====================================================
void playWAV(String url) {
  Serial.println("\n🔊 PLAY WAV (checked):");
  Serial.println(url);

  WiFiClientSecure client;
  client.setInsecure();

  HTTPClient http;
  bool ok = false;
  int code = -1;

  Serial.println("Checking URL availability...");

  if (http.begin(client, url)) {
    code = http.GET();
    Serial.printf("HTTP code: %d\n", code);
    Serial.println("Content-Type: " + http.header("Content-Type"));
    Serial.println("Content-Length: " + http.header("Content-Length"));

    if (code == 200) ok = true;
    http.end();
  }

  // ❗ Optional HTTP fallback (if HTTPS fails)
  if (!ok) {
    Serial.println("HTTPS failed — trying HTTP fallback...");

    String httpUrl = url;
    if (httpUrl.startsWith("https://")) {
      httpUrl = "http://" + httpUrl.substring(8);
    }

    if (http.begin(httpUrl)) {
      int code2 = http.GET();
      Serial.printf("HTTP fallback code: %d\n", code2);

      if (code2 == 200) {
        ok = true;
        url = httpUrl;  // use HTTP version
      }
      http.end();
    }
  }

  if (!ok) {
    Serial.println("❌ URL check failed — cannot open stream.");
    return;
  }

  stopAudio();

  file = new AudioFileSourceHTTPStream(url.c_str());
  out  = new AudioOutputI2S();

  // YOUR I2S pinout:
  // DOUT = 13, BCLK = 14, LRC = 4
  out->SetPinout(13, 14, 4);

  wav = new AudioGeneratorWAV();
  if (!wav->begin(file, out)) {
    Serial.println("❌ WAV begin FAILED");
    stopAudio();
    return;
  }

  Serial.println("✅ WAV playback started");
}

void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // WiFi
  Serial.println("Connecting to WiFi...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    Serial.print(".");
    delay(300);
  }
  Serial.println("\n✅ WiFi Connected!");

  // Camera config
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;

  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;
  config.fb_count     = 1;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("❌ Camera init failed");
    while(true);
  }
  Serial.println("✅ Camera Ready!");
}

unsigned long lastLog = 0;

void loop() {
  // If audio is playing
  if (wav && wav->isRunning()) {
    if (!wav->loop()) {
      Serial.println("Audio finished.");
      stopAudio();
    } else {
      if (millis() - lastLog > 2000) {
        Serial.println("WAV playing...");
        lastLog = millis();
      }
    }
    return;
  }

  // Button press
  if (digitalRead(BUTTON_PIN) == LOW) {
    Serial.println("\n📸 Button Pressed! Capturing...");
    delay(200);

    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("❌ Camera capture failed!");
      return;
    }

    WiFiClientSecure client;
    client.setInsecure();

    HTTPClient http;
    http.begin(client, serverURL);
    http.addHeader("Content-Type", "application/octet-stream");

    int code = http.POST(fb->buf, fb->len);

    if (code == 200) {
      String resp = http.getString();
      Serial.println(resp);

      // Extract audio_url
      int s = resp.indexOf("audio_url") + 12;
      int e = resp.indexOf("\"", s);

      if (s > 11 && e > s) {
        String audioURL = resp.substring(s, e);
        playWAV(audioURL);
      } else {
        Serial.println("❌ audio_url not found");
      }
    } else {
      Serial.print("❌ Upload error: ");
      Serial.println(code);
    }

    http.end();
    esp_camera_fb_return(fb);
    delay(500);
  }
}
