import requests
import sys
import threading
import io, base64
import uuid
import queue, zmq
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget
from PyQt6.QtGui import QImage, QPixmap
from PIL import Image
from PIL.ImageQt import ImageQt
                       
class zmq_thread(threading.Thread):
    def __init__(self, message_queue):
        super().__init__()
        self.message_queue = message_queue
    def run(self):
        context = zmq.Context()
        consumer_receiver = context.socket(zmq.PULL)
        consumer_receiver.connect("tcp://127.0.0.1:5557")
        while True:
            buff = consumer_receiver.recv()
            print(buff)
            self.message_queue.put(buff)

# GUI Thread
class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.initResources()

    def initUI(self):
        self.setWindowTitle("Socket Server Example")
        self.setGeometry(100, 100, 1200, 1200)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.label = QLabel("Waiting for messages...", self)
        self.layout.addWidget(self.label)
        
        self.picture = QLabel(self)
        self.layout.addWidget(self.picture)
    
    def initResources(self):
        self.message_queue = queue.Queue()

        self.server_thread = zmq_thread(self.message_queue)
        self.server_thread.start()

        self.update_timer = self.startTimer(1000)
        
    def closeEvent(self, event):
        # TODO: Close this all of the way. Thread still runs after GUI closes. Have to kill prompt.
        event.accept()

    def timerEvent(self, event):
        try:
            message = self.message_queue.get_nowait()
            self.update_label(message)
            if message == b'ShowImage':
                self.sd_request('')
        except queue.Empty:
            pass

    def update_label(self, message):
        self.label.setText(f"Received message: {message}")
        
    def sd_request(self, prompt):
        try:
            control_net = ControlnetRequest(prompt)
            control_net.build_body()
            output = control_net.send_request()

            result = output['images'][0]
            
            # TODO: Find a better way to translate results to QPixmap without saving file

            pil_image = Image.open(io.BytesIO(base64.b64decode(result.split(",", 1)[0])))
            unique_id = str(uuid.uuid4())
            pil_image.save(f'{unique_id}.png')
            # # Convert PIL image to QImage
            # image = ImageQt(pil_image)
            # Create a QLabel to display the QImage 
            self.picture.setPixmap(QPixmap(f'{unique_id}.png'))
            
        except Exception as e:
            print(f"Error: {e}")    
        
        
class ControlnetRequest:
    def __init__(self, prompt):
        self.url = "http://localhost:7860/sdapi/v1/txt2img"
        self.prompt = prompt
        self.body = None

    def build_body(self):
        self.body = {
            "prompt": self.prompt,
            "negative_prompt": "",
            "batch_size": 1,
            "steps": 15,
            "cfg_scale": 7,
            "width": 512,
            "height": 768,
            # "seed": 1992241092
        }

    def send_request(self):
        response = requests.post(url=self.url, json=self.body)
        return response.json()

def main():
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec())
    

if __name__ == "__main__":
    main()