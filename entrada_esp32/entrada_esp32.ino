// exemplo retirado de https://github.com/miguelbalboa/rfid

//  --- RFID ---
#include <SPI.h>
#include <MFRC522.h>
#define RST_PIN         22          // Configura pino RST
#define SS_PIN          21         // Configura pino SDA
MFRC522 mfrc522(SS_PIN, RST_PIN);   // Cria instância do o MFRC522 (leitor RFID)

// --- WIFI ---
#include <WiFi.h>
const char* ssid     = "SSID";
const char* password = "SENHA";
WiFiClient esp32Client;

// --- MQTT ---
#include <PubSubClient.h>
PubSubClient client(esp32Client);
const char* mqtt_Broker = "IP RASPBERRY";
const char* mqtt_topico_identidade = "TOPICO";
const char* mqtt_topico_entrada = "TOPICO";
const char* mqtt_ClientID = "esp32-01";

// --- Servo
#include <ESP32Servo.h>
Servo servo1;
int servo1Pin = 25;
ESP32PWM pwm;


// --- Inicialização ---
void setup() {
  servo1.attach(servo1Pin);
  pwm.attachPin(27, 10000);
  SPI.begin();
  mfrc522.PCD_Init();                 // Inicia o MFRC522

  conectaWifi();

  client.setServer(mqtt_Broker, 1883);
  client.setCallback(monitoraTopico);

  servo1.setPeriodHertz(50);
  }


// -- Funções Auxiliares ---

// --- Conecta no WIFI ---
void conectaWifi(){
    WiFi.begin(ssid, password);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }
}


// --- Conecta no Broker MQTT ---
void conectaMQTT() {
  while (!client.connected()) {
    client.connect(mqtt_ClientID);
    client.subscribe(mqtt_topico_entrada);
  }
}

// --- Monitora o tópico laboratorio/office/monitoracao ---
void monitoraTopico(char* mqtt_topico_entrada, byte* payload, unsigned int length) {
  if ((char)payload[0] == '1') {
    Abre();
  }
}

// --- Abrir a porta ---
void Abre(){
  servo1.write(0);
  delay(4000);
  servo1.write(180);
  delay(500);
}


// --- Publica no tópico Iluminacao (liga/desliga o dispositivo) ---
void publicaIdentidade(String identidade){
    client.publish(mqtt_topico_identidade, identidade.c_str());
  }


// --- Captura o código RFID e transforma para hexadecimal
void dump_byte_array(byte *buffer, byte bufferSize) {
  String x = "";
  for (byte i = 0; i < bufferSize; i++) {
    x += String(buffer[i] < 0x10 ? " 0": " ");
    x += String(buffer[i], HEX);
  }
  publicaIdentidade(x);
}


// --- Funçâo Principal ---
void loop() {
    if (!client.connected()) {
    conectaMQTT();
    }
    client.loop();
    // Esperando Cartões
    if (mfrc522.PICC_IsNewCardPresent() && mfrc522.PICC_ReadCardSerial()) {

      dump_byte_array(mfrc522.uid.uidByte, mfrc522.uid.size); // Recebe o código e publica

      MFRC522::PICC_Type piccType = mfrc522.PICC_GetType(mfrc522.uid.sak);
      mfrc522.PICC_HaltA();
      mfrc522.PCD_StopCrypto1();
    }

  }
