from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sse import sse
from threading import Thread
from time import sleep

app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"
app.register_blueprint(sse, url_prefix='/events')
CORS(app)


class ABC:
    def test_method(self):
        name = request.get_json()
        t1 = Thread(target=self.server_side_method)
        t1.start()
        return jsonify(name['data'])

    def server_side_method(self):
        for i in range(1, 3):
            sleep(1)
            with app.app_context():
                sse.publish({"data": str(i)}, type='test', retry=None)


@app.route("/test", methods=['POST'])
def action():
    a = ABC()
    return a.test_method()
