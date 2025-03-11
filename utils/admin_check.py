from config import ADMIN_IDS

async def is_admin(user_id):
    return user_id in ADMIN_IDS
