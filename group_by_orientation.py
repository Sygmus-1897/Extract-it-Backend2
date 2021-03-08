import logging
import shutil
import os
import datetime
from PIL import Image

def setup_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    log_file_name = './logs/group_log_file_' + datetime.datetime.now().__format__("%y_%m_%d %H_%M_%S") + '.log'
    file_handler = logging.FileHandler(log_file_name)
    formatter = logging.Formatter("%(asctime)s : %(levelname)s : %(name)s : %(message)s")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


setup_logger()
desktop_dir = "./images/desktop_images"
mobile_dir = "./images/mobile_images"
corrupt_dir = "./images/corrupt_images"
images_dir = "./images/Animewallpaper/"

if not os.path.exists(desktop_dir):
    os.mkdir(desktop_dir)
if not os.path.exists(mobile_dir):
    os.mkdir(mobile_dir)
if not os.path.exists(corrupt_dir):
    os.mkdir(corrupt_dir)

images = os.listdir(images_dir)


for image in images:
    try:
        image_dir = images_dir + image

        if os.path.isdir(image_dir):
            continue

        print(image)

        with Image.open(image_dir) as img:
            width = img.size[0]
            height = img.size[1]
            ratio = width/height

        if ratio >= 1:
            shutil.move(image_dir, desktop_dir)
        else:
            shutil.move(image_dir, mobile_dir)
    except shutil.Error as err:
        print(err, image)
    except Exception as err:
        print(err)