from telegram import Update, constants
from telegram.ext import ContextTypes
from utils.data import get_user, get_downloads
from utils.format import format_size

async def downloads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    user = get_user(user_id)

    if not user:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ معلش، مفيش معلومات عنك في قاعدة البيانات. أكتب /start الأول")
        return

    if user['is_banned']:
        await context.bot.send_message(chat_id=chat_id, text="⛔️ حسابك محظور من استخدام البوت.")
        return

    user_downloads = get_downloads(user_id)

    if not user_downloads:
        await context.bot.send_message(chat_id=chat_id, text="📭 مفيش تحميلات سابقة ليك")
        return

    message = "📥 *آخر 10 تحميلات* 📥\n\n"
    for i, download in enumerate(reversed(user_downloads[-10:])):
        message += f"{i + 1}. *{download['file_name'] or 'بدون اسم'}*\n"
        message += f"   📦 الحجم: {format_size(download['file_size'] or 0)}\n"
        message += f"   📅 التاريخ: {download['download_date'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"   🔄 الحالة: {'✅ مكتمل' if download['status'] == 'completed' else '⏳ جاري التحميل' if download['status'] == 'downloading' else '⌛️ في الانتظار' if download['status'] == 'pending' else '❌ فشل'}\n\n"

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=constants.ParseMode.MARKDOWN)
