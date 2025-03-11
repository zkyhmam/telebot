import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

logger.debug("utils/data.py is being loaded!")

users = []
downloads = []
daily_stats = {
    'date': None,  # هنحط تاريخ اليوم لما نبدأ البوت
    'new_users': 0,
    'total_downloads': 0,
    'total_bandwidth': 0
}

def get_user(user_id):
    return next((u for u in users if u['user_id'] == user_id), None)

def add_user(user):
    users.append(user)

logger.debug("Defining updateUser...")  # قبل التعريف

def update_user(updated_user):
    for i, user in enumerate(users):
        if user['user_id'] == updated_user['user_id']:
            users[i] = updated_user
            break

logger.debug("updateUser defined!")  # بعد التعريف

def get_downloads(user_id):
    return [d for d in downloads if d['user_id'] == user_id]

def add_download(download):
    downloads.append(download)

def update_download(updated_download):
    for i, download in enumerate(downloads):
        if download['id'] == updated_download['id']:
            downloads[i] = updated_download
            break

def get_completed_downloads(user_id):
    return [d for d in downloads if d['user_id'] == user_id and d['status'] == 'completed']

def get_daily_stats():
    return daily_stats

def update_daily_stats(new_users=0, total_downloads=0, total_bandwidth=0):
    from datetime import datetime, date

    today = date.today()
    if daily_stats['date'] != today:
         daily_stats['date'] = today
         daily_stats['new_users'] = 0
         daily_stats['total_downloads'] = 0
         daily_stats['total_bandwidth'] = 0

    daily_stats['new_users'] += new_users
    daily_stats['total_downloads'] += total_downloads
    daily_stats['total_bandwidth'] += total_bandwidth

def get_all_users():
    return users
def get_recent_users(limit=20):
    return sorted(users, key=lambda u: u['join_date'], reverse=True)[:limit]

def get_total_downloads():
    return len([d for d in downloads if d['status'] == 'completed'])
def get_total_bandwidth():
    return sum(d['file_size'] for d in downloads if d['status'] == 'completed')

def get_active_users_count():
    return len([u for u in users if u['is_active'] and not u['is_banned']])

def get_banned_users_count():
    return len([u for u in users if u['is_banned']])
