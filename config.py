import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv('TOKEN')
ADMIN_IDS = [int(admin_id) for admin_id in os.getenv('ADMIN_IDS').split(',')]
DEFAULT_DOWNLOAD_PATH = './downloads'
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
DEFAULT_SPEED_LIMIT = 8 * 1024 * 1024  # 8MB/s
DELETION_PERIOD = 24 * 60 * 60  # 24 hours (in seconds)
