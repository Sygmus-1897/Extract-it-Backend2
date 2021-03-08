from flask import Flask, jsonify, request
from flask_sse import sse
from flask_cors import CORS
from threading import Thread
import threading
import initialize_praw
import pymongo
import time
import datetime
import requests
import os
import json
import shutil
import logging


app = Flask(__name__)
app.config["REDIS_URL"] = "redis://localhost"
app.register_blueprint(sse, url_prefix='/extraction')
CORS(app)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not os.path.exists("./logs"):
    os.mkdir("./logs")

log_file_name = './logs/log_file_' + \
    datetime.datetime.now().__format__("%y_%m_%d %H_%M_%S")+'.log'
file_handler = logging.FileHandler(log_file_name)
formatter = logging.Formatter(
    "%(asctime)s : %(levelname)s : %(name)s : %(message)s")
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class extract:

    def __init__(self, subreddit, query=None, after=None, before=None, resume=False):
        self.subreddit_name = subreddit
        subreddit = self.verify_subreddit(subreddit)
        logger.info("subreddit verified")

        if not subreddit:
            logger.info("Subreddit not found")
            return

        self.after, self.before = self.set_bounds(
            subreddit, after, before, resume)
        # self.db = self.initialize_db(self.subreddit_name)

        # if not self.db:
        #     return

        self.save_path = './images/{subreddit}/'.format(
            subreddit=str(subreddit))
        self.store_path_desktop = '../images/desktop_images/'
        self.store_path_mobile = '../images/mobile_images/'

        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        if not os.path.exists(self.store_path_desktop):
            os.makedirs(self.store_path_desktop)
        if not os.path.exists(self.store_path_mobile):
            os.makedirs(self.store_path_mobile)

    def generate_link(self, subreddit, after, before):
        base_link = "https://api.pushshift.io/reddit/submission/search/?q=&subreddit={subreddit}&after={after}&before={before}&size=1000"
        new_link = base_link.format(
            subreddit=subreddit, after=after, before=before)
        return new_link

    def initialize_db(self, collection):
        col = None
        try:
            client = pymongo.MongoClient('localhost', 27017)
            db = client.image_link_db
            col = db[collection]
            col.create_index([('id', pymongo.ASCENDING)], unique=True)
        except Exception as err:
            logger.error("DB not initialized"+str(err))
            print("DB not initialized")
        return col

    def verify_subreddit(self, subreddit):
        verify = None
        reddit_obj = initialize_praw.getReddit()
        subreddit_obj = reddit_obj.subreddit(subreddit)

        id = subreddit_obj.id
        if id:
            verify = subreddit_obj

        return verify

    def set_bounds(self, subreddit, after, before, resume):
        if after is None:
            if resume:
                with open("last_run.txt", "r") as file:
                    after = file.read()
                    after = int(after) - 172800
            else:
                created_utc = subreddit.created_utc
                after = created_utc

        if before is None:
            curr_time = datetime.datetime.now()
            curr_time_utc = curr_time.replace(tzinfo=datetime.timezone.utc)
            curr_time_utc_timestamp = curr_time_utc.timestamp()
            before = curr_time_utc_timestamp

        return int(after), int(before)

    def inc_bounds(self, curr, downloading):
        self.after = curr
        if self.before - self.after < 1:
            downloading = False
        if self.before - self.after > 86400:
            curr = self.after + 86400
        else:
            curr = self.after + (self.before - self.after)
        return curr, downloading

    def save_step(self):
        with open("last_run.txt", "w") as file:
            file.write(str(self.after))
            logger.info("Last Step Recorded")

    def extract_images(self):
        downloading = True
        curr, downloading = self.inc_bounds(self.after, downloading)
        with app.app_context():
            logger.info("PUBLISHING: bounds")
            sse.publish({"starting_date": str(self.after), "ending_date": str(self.before)},
                        type="bounds")
        retries = 0
        while curr <= self.before and downloading:
            try:
                print("Current :", datetime.datetime.utcfromtimestamp(curr))
                logger.info("Lower and Upper bounds: " +
                            str(self.after) + ", " + str(curr))
                with app.app_context():
                    logger.info("PUBLISHING: curr_date")
                    sse.publish({"current_date": str(curr)},
                                type="curr_date")
                link = self.generate_link(
                    self.subreddit_name, self.after, curr)
                logger.info("Requesting: "+link)
                res = requests.get(link, timeout=10)
                time.sleep(1)
                if res.status_code != 200:
                    logger.info("Bad Response, Skipping: " + link)
                    curr, downloading = self.inc_bounds(curr, downloading)
                    continue
                time.sleep(1)
                json_string = res.text
                data_json = json.loads(json_string)
                logger.info("Data Loaded")
                with app.app_context():
                    logger.info("PUBLISHING: metadata_data_size")
                    sse.publish({'data_size': len(data_json['data'])},
                                type='metadata_data_size')
                counter = 0
                for post in data_json['data']:
                    counter += 1
                    logger.info("Working on: "+post['id'])
                    with app.app_context():
                        logger.info("PUBLISHING: post_id")
                        sse.publish(
                            {"post_id": post['id'], "curr_data": counter}, type='post_id')
                    flag = 1
                    if post['url'][-3:] in ['png', 'jpg']:
                        logger.info("Image Detected!")
                        filename = self.save_path + \
                            post['id'] + "." + post['url'][-3:]
                        desktop = self.store_path_desktop + \
                            post['id'] + "." + post['url'][-3:]
                        mobile = self.store_path_mobile + \
                            post['id'] + "." + post['url'][-3:]

                        if os.path.exists(filename) or os.path.exists(desktop) or os.path.exists(mobile):
                            logger.info(
                                "Image already exist, skipping download")
                            continue
                        try:
                            logger.info("Requesting: "+post['url'])
                            image = requests.get(
                                post['url'], stream=True, timeout=20)
                            time.sleep(1)
                            if image.status_code == 200:
                                logger.info("Image Received!")
                                image.raw.decode_content = True
                                filename = self.save_path + \
                                    post['id'] + "." + post['url'][-3:]
                                with open(filename, 'wb') as file:
                                    shutil.copyfileobj(image.raw, file)
                                    logger.info("Image Saved!")
                                    flag = 0
                                try:
                                    logger.info("Image Saved! Saving Post")
                                    # self.db.insert_one(post)
                                    logger.info("Post Saved!")
                                except pymongo.errors.DuplicateKeyError as err:
                                    logger.error("Post is already saved!")
                                except Exception as err:
                                    self.save_step()
                                    logger.error(
                                        "Exception while saving post: " + str(err))
                        except Exception as err:
                            self.save_step()
                            logger.error(
                                "Error while retreiving image: "+str(err))
                            print(err)
                    if flag:
                        try:
                            logger.error(
                                "Album or exception found, saving post")
                            # self.db.insert_one(post)
                        except pymongo.errors.DuplicateKeyError as err:
                            logger.error("Post is already saved!")
                        except Exception as err:
                            self.save_step()
                            logger.error(
                                "Exception while saving post: "+str(err))

                curr, downloading = self.inc_bounds(curr, downloading)
                logger.info("Incrementing bounds")
                logger.info("New Bounds- After: "+str(self.after) +
                            " Before: "+str(curr)+" End Point: "+str(self.before))
                retries = 0
                self.save_step()
            except Exception as err:
                self.save_step()
                retries += 1
                if retries > 2:
                    break
                logger.error("Cannot retreive from: "+str(link))
                logger.error("Exception Occured: " + str(err))


class stop_class:
    stop = False


global stop_class_obj
resume = threading.Event()


@app.route("/extract_posts", methods=['POST'])
def extract_posts():
    req_json = request.get_json()
    subreddit, resume = req_json['data']['subreddit'], req_json['data']['resume']
    # x(subreddit, resume)
    t1 = Thread(target=extract_call, args=[subreddit, resume])
    t1.start()
    # global stop_class_obj
    # stop_class_obj = stop_class()
    # t1 = Thread(target=testProgressBar, args=[stop_class_obj])
    # t1.start()
    return jsonify({'status': 'Extraction Started!'})


def extract_call(subreddit, resume):
    e = extract(subreddit=subreddit, resume=resume)
    e.extract_images()
    with app.app_context():
        logger.info("PUBLISHING: stop")
        sse.publish({'status': 'finished'}, type='stop', retry=None)


@app.route("/stop_posts", methods=['GET', 'POST'])
def stopLoop():
    global stop_class_obj
    if stop_class_obj.stop:
        stop_class_obj.stop = False
        resume.set()
    else:
        stop_class_obj.stop = True
        resume.clear()
        print("inside stoploop():", stop_class_obj.stop)
    return jsonify({"stop": "done"})


def testProgressBar(stop_class_obj):
    time.sleep(2)
    with app.app_context():
        sse.publish({"start_loop": "yes"}, type='start_test', retry=None)

    for j in range(3):
        if stop_class_obj.stop:
            resume.wait()
        with app.app_context():
            sse.publish({"outer_loop": j}, type='outer_test', retry=None)
        for i in range(10):
            print("inside innerloop:", stop_class_obj.stop)
            if stop_class_obj.stop:
                resume.wait()
            with app.app_context():
                sse.publish({"inner_loop": i}, type='inner_test', retry=None)
            time.sleep(2)

    with app.app_context():
        sse.publish({"stop_loop": "yes"}, type='stop_test', retry=None)
