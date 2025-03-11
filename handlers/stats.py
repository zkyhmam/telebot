from telegram import Update, constants
from telegram.ext import ContextTypes
from utils.data import get_user, get_completed_downloads
from utils.format import format_size, format_time

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    user = get_user(user_id)

    if not user:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ معلش، مفيش معلومات عنك في قاعدة البيانات. أكتب /start الأول")
        return

    if user['is_banned']:
        await context.bot.send_message(chat_id=chat_id, text="⛔️ حسابك محظور من استخدام البوت.")
        return

    downloads_count = len(get_completed_downloads(user_id))
    total_download_size = sum(d['file_size'] for d in get_completed_downloads(user_id))

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"""
📊 *إحصائياتك الشخصية* 📊

👤 الاسم: {user['first_name']} {user['last_name'] or ''}
📅 تاريخ الانضمام: {user['join_date'].strftime('%Y-%m-%d')}
📥 عدد التحميلات: {downloads_count}
📦 حجم التحميلات الكلي: {format_size(total_download_size)}
⚡️ أقصى سرعة تحميل: {format_size(user['max_speed'])}/s
📏 أقصى حجم ملف: {format_size(user['max_download_size'])}
🕰 آخر نشاط: {user['last_activity'].strftime('%Y-%m-%d %H:%M:%S')}
""",
        parse_mode=constants.ParseMode.MARKDOWN
    )
