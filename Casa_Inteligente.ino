#include <WiFi.h>
#include <DHT.h>
#include <ESP32Servo.h>

// ================== DHT11 ==================
#define DHTPIN 4
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

// ================== SERVO ==================
Servo servo;
int servoPin = 27;
bool puertaAbierta = false;

// ================== LEDS ==================
int ledSala   = 16;
int ledCocina = 17;
int ledBano   = 18;
int ledCuarto = 19;

// estados lógicos
bool estadoSala   = false;
bool estadoCocina = false;
bool estadoBano   = false;
bool estadoCuarto = false;

// ================== BUZZER ==================
int buzzer = 15;
bool buzzerActivo = false;

// ================== WIFI ==================
const char* ssid     = "IZZI-14FF";
const char* password = "YJMZDZ5YTNHJ";
const char* host     = "3.149.222.108";   // servidor de tu profe
const int   port     = 4017;
WiFiClient client;

// ================== CONTROL ==================
unsigned long lastSend = 0;

// ================== SETUP ==================
void setup() {
  Serial.begin(115200);

  pinMode(ledSala, OUTPUT);
  pinMode(ledCocina, OUTPUT);
  pinMode(ledBano, OUTPUT);
  pinMode(ledCuarto, OUTPUT);
  pinMode(buzzer, OUTPUT);

  digitalWrite(buzzer, LOW);

  servo.attach(servoPin);
  servo.write(90);            // puerta cerrada al inicio
  puertaAbierta = false;

  dht.begin();

  conectarWiFi();
  conectarServidor();
}

// ================== LOOP ==================
void loop() {

  if (WiFi.status() != WL_CONNECTED) {
    conectarWiFi();
  }

  if (!client.connected()) {
    conectarServidor();
    return;
  }

  // ================== TEMPERATURA ==================
  unsigned long now = millis();
  if (now - lastSend > 2000) {
    lastSend = now;
    float t = dht.readTemperature();

    if (!isnan(t)) {
      client.print(String("<esp><temp>") + t + "\n");

      if (t > 27 && !buzzerActivo) {
        buzzerActivo = true;
        digitalWrite(buzzer, HIGH);
        client.print("<esp><alarm>TEMP\n");
      }
    }
  }

  // ================== COMANDOS ==================
  if (client.available()) {
    String cmd = client.readStringUntil('\n');
    cmd.trim();
    Serial.println("CMD: " + cmd);

    // -------- BUZZER --------
    if (cmd == "BUZZER_FORZADO") {
      buzzerActivo = true;
      digitalWrite(buzzer, HIGH);
    }

    if (cmd == "BUZZER_OFF") {
      buzzerActivo = false;
      digitalWrite(buzzer, LOW);
    }

// -------- PUERTA --------
if (cmd == "PUERTA_ABRIR" && !puertaAbierta) {
  for (int i = 90; i >= 0; i -= 2) { 
    servo.write(i);
    delay(10);
  }
  puertaAbierta = true;
}

if (cmd == "PUERTA_CERRAR" && puertaAbierta) {
  for (int i = 0; i <= 90; i += 2) { 
    servo.write(i);
    delay(10);
  }
  puertaAbierta = false;
}
    // -------- FOCOS INDIVIDUALES --------
    if (cmd == "FOCO_SALA_ON")   estadoSala = true;
    if (cmd == "FOCO_SALA_OFF")  estadoSala = false;

    if (cmd == "FOCO_COCINA_ON") estadoCocina = true;
    if (cmd == "FOCO_COCINA_OFF")estadoCocina = false;

    if (cmd == "FOCO_BANO_ON")   estadoBano = true;
    if (cmd == "FOCO_BANO_OFF")  estadoBano = false;

    if (cmd == "FOCO_CUARTO_ON") estadoCuarto = true;
    if (cmd == "FOCO_CUARTO_OFF")estadoCuarto = false;

    // -------- TODOS --------
    if (cmd == "FOCOS_TODOS_ON") {
      estadoSala = estadoCocina = estadoBano = estadoCuarto = true;
    }

    if (cmd == "FOCOS_TODOS_OFF") {
      estadoSala = estadoCocina = estadoBano = estadoCuarto = false;
    }

    // -------- APLICAR ESTADOS --------
    digitalWrite(ledSala,   estadoSala   ? HIGH : LOW);
    digitalWrite(ledCocina, estadoCocina ? HIGH : LOW);
    digitalWrite(ledBano,   estadoBano   ? HIGH : LOW);
    digitalWrite(ledCuarto, estadoCuarto ? HIGH : LOW);
  }
}

// ================== FUNCIONES ==================
void conectarWiFi() {
  Serial.print("Conectando WiFi");
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("\nWiFi conectado");
}

void conectarServidor() {
  Serial.println("Conectando servidor...");
  if (client.connect(host, port)) {
    client.print("<tipo>ESP32\n");
    Serial.println("Servidor conectado");
  } else {
    Serial.println("Fallo conexión servidor");
    delay(2000);
  }
}
