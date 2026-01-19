import socket
import os
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QTimer, Signal, QThread
from PySide6.QtGui import QPixmap

from CASAINTELIGENTE_ui import Ui_MainWindow
from dialog_focos import DialogFocos

SERVER_IP = "3.149.222.108"
SERVER_PORT = 4017


# ================= RECEIVER THREAD =================
class ReceiverThread(QThread):
    received = Signal(str)

    def __init__(self, sock):
        super().__init__()
        self.sock = sock
        self.running = True

    def run(self):
        buffer = b""
        while self.running:
            try:
                data = self.sock.recv(4096)
                if not data:
                    break

                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    msg = line.decode(errors="ignore").strip()
                    if msg:
                        self.received.emit(msg)

            except socket.timeout:
                continue
            except:
                break

    def stop(self):
        self.running = False
        self.quit()
        self.wait()


# ================= MAIN WINDOW =================
class SmartHome(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # ===== ESTADOS =====
        self.sock = None
        self.receiver = None

        self.modo_seguro = False
        self.puerta_abierta = False
        self.animando = False
        self.progress_value = 0

        # ===== ESTILOS =====
        self.ui.Display.setStyleSheet(
            "color:white; background-color:black; font-weight:bold;"
        )
        self.ui.Temperatura_medida.setStyleSheet(
            "color:white; font-size:20px; font-weight:bold;"
        )

        self.ui.groupBox_4.hide()
        self.cargar_imagenes()

        # ===== TIMERS =====
        self.tempTimer = QTimer()
        self.tempTimer.timeout.connect(self.solicitar_temperatura)
        self.tempTimer.start(2000)

        self.alertTimer = QTimer()
        self.alertTimer.timeout.connect(self.parpadear_alarma)
        self._blink = False

        self.progressTimer = QTimer()
        self.progressTimer.timeout.connect(self.animar_puerta)

        # ===== BOTONES =====
        self.ui.Encender_Foco.clicked.connect(self.encender_foco)
        self.ui.Apagar_Foco.clicked.connect(self.apagar_foco)

        self.ui.Abrir_puerta.clicked.connect(self.abrir_puerta)
        self.ui.Cerrar_puerta.clicked.connect(self.cerrar_puerta)

        self.ui.Activar_moso_seguro.clicked.connect(self.activar_modo_seguro)
        self.ui.Desactivar_modo_seguro.clicked.connect(self.desactivar_modo_seguro)

        self.ui.Desactivar_alarma.clicked.connect(self.desactivar_alarma)

        self.ui.Progreso_puerta.setValue(0)

        self.conectar_servidor()

    # ================= IMÁGENES =================
    def cargar_imagenes(self):
        base = os.path.dirname(os.path.abspath(__file__))
        self.ui.label.setPixmap(QPixmap(os.path.join(base, "C1.jpg")))
        self.ui.label_2.setPixmap(QPixmap(os.path.join(base, "s1.jpg")))

    # ================= CONEXIÓN =================
    def conectar_servidor(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(0.5)
        self.sock.connect((SERVER_IP, SERVER_PORT))
        self.sock.send(b"<tipo>PC\n")

        self.receiver = ReceiverThread(self.sock)
        self.receiver.received.connect(self.procesar_mensaje)
        self.receiver.start()

    # ================= MENSAJES =================
    def procesar_mensaje(self, msg):
        if msg.startswith("<esp><temp>"):
            try:
                t = float(msg.replace("<esp><temp>", ""))
                self.ui.Temperatura_medida.setText(f"{t:.1f} °C")

                if t >= 27:
                    self.mostrar_alarma("Temperatura mayor a 27°C")
                    self.enviar("BUZZER_FORZADO")
            except:
                pass

    # ================= ENVÍO =================
    def enviar(self, cmd):
        try:
            self.sock.send((cmd + "\n").encode())
        except:
            pass

    # ================= FOCOS =================
    def encender_foco(self):
        dlg = DialogFocos("ENCENDER")
        if dlg.exec():
            foco = dlg.foco.upper()
            cmd = "FOCOS_TODOS_ON" if foco == "TODOS" else f"FOCO_{foco}_ON"
            self.enviar(cmd)

    def apagar_foco(self):
        dlg = DialogFocos("APAGAR")
        if dlg.exec():
            foco = dlg.foco.upper()
            cmd = "FOCOS_TODOS_OFF" if foco == "TODOS" else f"FOCO_{foco}_OFF"
            self.enviar(cmd)

    # ================= PUERTA =================
    def abrir_puerta(self):
        if self.modo_seguro:
            self.mostrar_alarma("Modo seguro activo: acceso denegado")
            self.enviar("BUZZER_FORZADO")
            return

        if self.puerta_abierta or self.animando:
            return

        self.animando = True
        self.progress_value = 0
        self.ui.Display.setText("Abriendo puerta...")
        self.enviar("PUERTA_ABRIR")
        self.progressTimer.start(30)

    def cerrar_puerta(self):
        if not self.puerta_abierta or self.animando:
            return

        self.animando = True
        self.progress_value = 100
        self.ui.Display.setText("Cerrando puerta...")
        self.enviar("PUERTA_CERRAR")
        self.progressTimer.start(30)

    def animar_puerta(self):
        paso = 100 / 50

        if self.ui.Display.text().startswith("Abriendo"):
            self.progress_value += paso
            if self.progress_value >= 100:
                self.progress_value = 100
                self.puerta_abierta = True
                self.animando = False
                self.progressTimer.stop()
        else:
            self.progress_value -= paso
            if self.progress_value <= 0:
                self.progress_value = 0
                self.puerta_abierta = False
                self.animando = False
                self.progressTimer.stop()

        self.ui.Progreso_puerta.setValue(int(self.progress_value))

    # ================= MODO SEGURO =================
    def activar_modo_seguro(self):
        self.modo_seguro = True

        # cerrar puerta si estaba abierta
        if self.puerta_abierta and not self.animando:
            self.animando = True
            self.progress_value = 100
            self.ui.Display.setText("errando puerta por modo seguro...")
            self.enviar("PUERTA_CERRAR")
            self.progressTimer.start(30)
        else:
            self.ui.Display.setText(" Modo seguro ACTIVADO")

    def desactivar_modo_seguro(self):
        self.modo_seguro = False
        self.ui.Display.setText("Modo seguro DESACTIVADO")

    # ================= ALARMA =================
    def mostrar_alarma(self, texto):
        self.ui.Display.setText(texto)
        self.ui.groupBox_4.show()
        self.alertTimer.start(300)

    def parpadear_alarma(self):
        self._blink = not self._blink
        color = "rgb(200,0,0)" if self._blink else "rgb(120,0,0)"
        self.ui.groupBox_4.setStyleSheet(f"background-color:{color}")

    def desactivar_alarma(self):
        self.alertTimer.stop()
        self.ui.groupBox_4.hide()
        self.enviar("BUZZER_OFF")

    # ================= TEMPERATURA =================
    def solicitar_temperatura(self):
        self.enviar("GET_TEMP")

    # ================= CERRAR APP =================
    def closeEvent(self, event):
        try:
            self.tempTimer.stop()
            self.alertTimer.stop()
            self.progressTimer.stop()
        except:
            pass

        if self.receiver:
            self.receiver.running = False
            self.receiver.wait(1000)

        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.sock.close()

        event.accept()


# ================= MAIN =================
if __name__ == "__main__":
    app = QApplication([])
    win = SmartHome()
    win.show()
    app.exec()
