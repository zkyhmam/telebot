from telegram import Update, constants
from telegram.ext import ContextTypes

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"""
🚀 *أوامر بوت التورنت المصري* 🇪🇬

🔹 *الأوامر العامة:*
/start - بدء استخدام البوت
/help - عرض قائمة الأوامر
/stats - عرض إحصائياتك الشخصية
/downloads - عرض تحميلاتك الأخيرة

🔸 *كيفية الاستخدام:*
- ابعت لينك ماجنت أو ملف تورنت
- اختار الملفات اللي عايز تحملها
- هيتم إرسال الملفات ليك فور انتهاء التحميل

📊 لأي مشكلة تواصل مع الأدمن: @zaky1million
""",  # تأكد من تغيير هذا بالأدمن
        parse_mode=constants.ParseMode.MARKDOWN
    )
