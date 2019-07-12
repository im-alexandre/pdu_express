// exemplo retirado de https://github.com/miguelbalboa/rfid

//  --- RFID ---
#include <SPI.h>
#include <MFRC522.h>
#define RST_PIN         0          // Configura pino RST
#define SS_PIN          2         // Configura pino SDA
MFRC522 mfrc522(SS_PIN, RST_PIN);   // Cria instância do o MFRC522 (leitor RFID)

// --- WIFI ---
#include <ESP8266WiFi.h>
const char* ssid     = "SSID";
const char* password = "SENHA";
WiFiClient esp8266Client;

// --- MQTT ---
#include <PubSubClient.h>
PubSubClient client(esp8266Client);
const char* mqtt_Broker = "IP RASPBERRY";
const char* mqtt_topico_identidade = "TOPICO";
const char* mqtt_topico_saida = "TOPICO";
const char* mqtt_ClientID = "esp8266";

// --- Servo
#include <Servo.h>
Servo servo1;
int servo1Pin = 15;


// --- Inicialização ---
void setup() {
  SPI.begin();
  mfrc522.PCD_Init();                 // Inicia o MFRC522

  conectaWifi();

  client.setServer(mqtt_Broker, 1883);
  client.setCallback(monitoraTopico);

  servo1.attach(servo1Pin);
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
    client.subscribe(mqtt_topico_saida);
  }
}

// --- Monitora o tópico laboratorio/office/monitoracao ---
void monitoraTopico(char* mqtt_topico_saida, byte* payload, unsigned int length) {
  if ((char)payload[0] == '1') {
   AutorizaSaida();
  }
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

// --- Abrir a porta ---
void AutorizaSaida(){

  for (int pos = 0; pos <= 180; pos += 1) { 

    servo1.write(pos);
    delay(15);
  }
  delay(2000);
  for (int pos = 180; pos >= 0; pos -= 1) {
    servo1.write(pos);
    delay(15);
  }
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
