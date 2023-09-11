import requests
import sys
import threading
import io, base64
import uuid
import queue, zmq
import tempfile
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QLineEdit
from PyQt6.QtGui import QImage, QPixmap
from PIL import Image
from PIL.ImageQt import ImageQt

dark_stylesheet = """
QWidget {
    background-color: #222;
    color: #fff;
}

QPushButton {
    background-color: #333;
    color: #fff;
    border: 2px solid #555;
    border-radius: 5px;
    padding: 5px 10px;
}

QPushButton:hover {
    background-color: #444;
}

QMainWindow {
    background-color: #222;
    color: #fff;
}
"""
                       
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
        self.current_pil_image = None

    def initUI(self):
        self.setWindowTitle("Dreamer")
        self.setGeometry(0, 0, 512, 768)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.label = QLabel("Waiting for messages...", self)
        self.layout.addWidget(self.label)
        
        default_prompt = ""
        self.prompt_input = QLineEdit(self)
        self.prompt_input.setPlaceholderText(default_prompt)
        self.layout.addWidget(self.prompt_input)
        
        default_neg_prompt = ""
        self.neg_prompt_input = QLineEdit(self)
        self.neg_prompt_input.setPlaceholderText(default_neg_prompt)
        self.layout.addWidget(self.neg_prompt_input)
        
        self.picture = QLabel(self)
        self.layout.addWidget(self.picture)
        
        self.setStyleSheet(dark_stylesheet)
    
    def initResources(self):
        self.message_queue = queue.Queue()

        self.server_thread = zmq_thread(self.message_queue)
        self.server_thread.start()

        self.update_timer = self.startTimer(500)
        
    def closeEvent(self, event):
        # TODO: Close this all of the way. Thread still runs after GUI closes. Have to kill prompt.
        event.accept()

    def timerEvent(self, event):
        try:
            message = self.message_queue.get_nowait()
            self.update_label(message)
            if message == b'ShowImage':
                self.sd_request(self.prompt_input.text(), self.neg_prompt_input.text())
            elif message == b'SaveImage':
                unique_id = str(uuid.uuid4())
                self.current_pil_image.save(f'{unique_id}.png')
        except queue.Empty:
            pass

    def update_label(self, message):
        self.label.setText(f"Received message: {message}")
        
    def sd_request(self, prompt, neg_prompt):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                control_net = ControlnetRequest(prompt, neg_prompt)
                control_net.build_body()
                output = control_net.send_request()

                result = output['images'][0]
                print(f'Parameters: {output["parameters"]}')
                print(f'Info: {output["info"]}')
                
                # TODO: Find a better way to translate results to QPixmap without saving file

                self.current_pil_image = Image.open(io.BytesIO(base64.b64decode(result.split(",", 1)[0])))
                unique_id = str(uuid.uuid4())
                self.current_pil_image.save(f'{temp_dir}/{unique_id}.png')
                # # Convert PIL image to QImage
                # image = ImageQt(pil_image)
                # Create a QLabel to display the QImage 
                self.picture.setPixmap(QPixmap(f'{temp_dir}/{unique_id}.png'))
            
        except Exception as e:
            print(f"Error: {e}")    
        
        
class ControlnetRequest:
    def __init__(self, prompt, neg_prompt):
        self.url = "http://localhost:7860/sdapi/v1/txt2img"
        self.prompt = prompt
        self.neg_prompt = neg_prompt
        self.body = None

    def build_body(self):
        self.body = {
            "prompt": self.prompt,
            "negative_prompt": self.neg_prompt,
            "batch_size": 1,
            "steps": 15,
            "cfg_scale": 7,
            "width": 512,
            "height": 768,
            # "seed": 1992241092
            # "subseed": -1,
            # "subseed_strength": 0,
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