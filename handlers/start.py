from telegram import Update
from telegram.ext import ContextTypes
from utils.data import get_user, add_user, update_user, update_daily_stats
from config import MAX_FILE_SIZE, DEFAULT_SPEED_LIMIT

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    first_name = update.effective_user.first_name

    user = get_user(user_id)

    if not user:
        user = {
            'user_id': user_id,
            'username': update.effective_user.username,
            'first_name': first_name,
            'last_name': update.effective_user.last_name,
            'is_active': True,
            'is_banned': False,
            'join_date': update.message.date,
            'total_downloads': 0,
            'max_download_size': MAX_FILE_SIZE,
            'max_speed': DEFAULT_SPEED_LIMIT,
            'last_activity': update.message.date
        }
        add_user(user)
        update_daily_stats(new_users=1)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🚀 أهلا بيك يا {first_name} في بوت التورنت المصري! 🇪🇬\n\n"
                 f"إزيك يا معلم؟ جاهزين نحمل أي حاجة عايزها 📥\n\n"
                 f"📌 بص عشان تحمل:\n"
                 f"- ابعت لي لينك ماجنت أو ملف تورنت وأنا هحمله علطول\n"
                 f"- هتقدر تتحكم في التحميل من خلال الأزرار اللي هتظهر\n\n"
                 f"👨‍💻 اكتب /help عشان تشوف كل الأوامر المتاحة"
        )
    else:
        if user['is_banned']:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"⛔️ معلش يا {first_name}، حسابك محظور من استخدام البوت."
            )
            return

        user['last_activity'] = update.message.date
        update_user(user)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"🚀 أهلا بيك تاني يا {first_name}! 🇪🇬\n\n"
                 f"جاهزين نحمل اللي تطلبه.. ابعت لينك ماجنت وانا اشتغل علطول 🚀"
        )
