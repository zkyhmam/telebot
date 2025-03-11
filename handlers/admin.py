from telegram import Update, constants
from telegram.ext import ContextTypes
from utils.data import get_all_users, get_recent_users, get_total_downloads, get_total_bandwidth, get_active_users_count, get_banned_users_count, get_user, update_user
from utils.format import format_size
from utils.admin_check import is_admin
import os
import psutil
from datetime import datetime, timedelta
import asyncio

#  إنشاء رسم بياني للإحصائيات
async def create_stats_chart(period='week'):
    #   نظرًا لعدم وجود مكتبة رسوم بيانية جاهزة وسهلة في بايثون زي بتاعة JavaScript،
    #   هنرجع نص بسيط مؤقتًا. ممكن نضيف رسم بياني بعدين لو ضروري.
    return "📊 خاصية الرسوم البيانية لسه مش جاهزة في إصدار بايثون."

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not await is_admin(user_id):
        await context.bot.send_message(chat_id=chat_id, text="⛔️ أنت لا تملك صلاحيات الأدمن")
        return

    total_users = len(get_all_users())
    active_users = get_active_users_count()
    banned_users = get_banned_users_count()
    total_downloads_count = get_total_downloads()
    total_size = format_size(get_total_bandwidth())

    # System stats
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    total_mem = format_size(mem.total)
    free_mem = format_size(mem.available)

    chart_url = await create_stats_chart()  #  هترجع نص بسيط دلوقتي

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"""
📊 *إحصائيات البوت* 📊

👥 *المستخدمين:*
- إجمالي المستخدمين: {total_users}
- المستخدمين النشطين: {active_users}
- المستخدمين المحظورين: {banned_users}

📥 *التحميلات:*
- إجمالي التحميلات: {total_downloads_count}
- إجمالي الحجم: {total_size}

💻 *موارد النظام:*
- استخدام المعالج: {cpu_percent}%
- استخدام الذاكرة: {mem_percent}% ({format_size(mem.used)} / {total_mem})
- ذاكرة النظام: {free_mem} حرة من {total_mem}

🔍 للمزيد من التفاصيل:
/users - عرض قائمة المستخدمين
/admin_chart [week|month|year] - رسم بياني للإحصائيات (مش شغال دلوقتي)
{chart_url}
""",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def admin_chart(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        period = context.args[0].lower() if context.args else 'week'

        if not await is_admin(user_id):
            await context.bot.send_message(chat_id=chat_id, text="⛔️ أنت لا تملك صلاحيات الأدمن")
            return

        if period not in ['week', 'month', 'year']:
            await context.bot.send_message(chat_id=chat_id, text="⚠️ المدة غير صحيحة. استخدم week أو month أو year")
            return

        chart_url = await create_stats_chart(period)  #  هترجع نص بسيط دلوقتي
        await context.bot.send_message(chat_id=chat_id, text=chart_url)


async def users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not await is_admin(user_id):
        await context.bot.send_message(chat_id=chat_id, text="⛔️ أنت لا تملك صلاحيات الأدمن")
        return

    recent_users = get_recent_users()

    if not recent_users:
        await context.bot.send_message(chat_id=chat_id, text="👥 مفيش مستخدمين في قاعدة البيانات")
        return

    message = "👥 *آخر 20 مستخدم* 👥\n\n"
    for i, user in enumerate(recent_users):
        message += f"{i + 1}. *{user['first_name']} {user['last_name'] or ''}* "
        message += f"(@{user['username']})\n" if user['username'] else "\n"
        message += f"   🆔 الأيدي: `{user['user_id']}`\n"
        message += f"   📅 تاريخ الانضمام: {user['join_date'].strftime('%Y-%m-%d')}\n"
        message += f"   📥 عدد التحميلات: {user['total_downloads']}\n"
        message += f"   🔄 الحالة: {'✅ نشط' if user['is_active'] else '⛔ غير نشط'}{' (محظور)' if user['is_banned'] else ''}\n\n"

    message += "للتحكم في المستخدمين:\n"
    message += "/ban [userId] - حظر مستخدم\n"
    message += "/unban [userId] - إلغاء الحظر\n"
    message += "/set_limit [userId] [size in MB] - تعيين حجم أقصى للتحميل"

    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode=constants.ParseMode.MARKDOWN)

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id
    try:
        target_user_id = int(context.args[0])
    except (IndexError, ValueError):
        await context.bot.send_message(chat_id=chat_id, text="⚠️ الاستخدام: /ban [userId]")
        return

    if not await is_admin(admin_id):
        await context.bot.send_message(chat_id=chat_id, text="⛔️ أنت لا تملك صلاحيات الأدمن")
        return

    user = get_user(target_user_id)

    if not user:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ مفيش مستخدم بالأيدي ده: {target_user_id}")
        return

    user['is_banned'] = True
    update_user(user)

    await context.bot.send_message(chat_id=chat_id, text=f"✅ تم حظر المستخدم {user['first_name']} {user['last_name'] or ''} (ID: {user['user_id']}) بنجاح")

    try:
        await context.bot.send_message(chat_id=target_user_id, text="⛔️ عفواً، تم حظرك من استخدام البوت. للاستفسار تواصل مع الدعم")
    except Exception as e:
        print(f"Couldn't send message to banned user: {e}")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id
    try:
        target_user_id = int(context.args[0])
    except (IndexError, ValueError):
        await context.bot.send_message(chat_id=chat_id, text="⚠️ الاستخدام: /unban [userId]")
        return

    if not await is_admin(admin_id):
        await context.bot.send_message(chat_id=chat_id, text="⛔️ أنت لا تملك صلاحيات الأدمن")
        return

    user = get_user(target_user_id)

    if not user:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ مفيش مستخدم بالأيدي ده: {target_user_id}")
        return

    user['is_banned'] = False
    update_user(user)

    await context.bot.send_message(chat_id=chat_id, text=f"✅ تم إلغاء حظر المستخدم {user['first_name']} {user['last_name'] or ''} (ID: {user['user_id']}) بنجاح")

    try:
        await context.bot.send_message(chat_id=target_user_id, text="🎉 مبروك! تم إلغاء الحظر عنك، يمكنك استخدام البوت الآن")
    except Exception as e:
        print(f"Couldn't send message to unbanned user: {e}")

async def set_limit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id
    try:
        target_user_id = int(context.args[0])
        size_mb = int(context.args[1])
    except (IndexError, ValueError):
        await context.bot.send_message(chat_id=chat_id, text="⚠️ الاستخدام: /set_limit [userId] [size in MB]")
        return

    if not await is_admin(admin_id):
        await context.bot.send_message(chat_id=chat_id, text="⛔️ أنت لا تملك صلاحيات الأدمن")
        return

    if size_mb <= 0:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ حجم غير صالح. يجب أن يكون رقم موجب")
        return

    user = get_user(target_user_id)

    if not user:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ مفيش مستخدم بالأيدي ده: {target_user_id}")
        return

    user['max_download_size'] = size_mb * 1024 * 1024  # تحويل إلى بايت
    update_user(user)

    await context.bot.send_message(chat_id=chat_id, text=f"✅ تم تعيين الحجم الأقصى للمستخدم {user['first_name']} {user['last_name'] or ''} إلى {size_mb} ميجابايت")

    try:
        await context.bot.send_message(chat_id=target_user_id, text=f"ℹ️ تم تحديث الحد الأقصى للتحميل الخاص بك إلى {size_mb} ميجابايت")
    except Exception as e:
        print(f"Couldn't send message to user: {e}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    admin_id = update.effective_user.id
    message = ' '.join(context.args)

    if not await is_admin(admin_id):
      await context.bot.send_message(chat_id=chat_id, text='⛔️ أنت لا تملك صلاحيات الأدمن')
      return
    await context.bot.send_message(chat_id=chat_id, text='🔄 جاري إرسال الإشعار لكل المستخدمين...')

    users = get_all_users()
    success_count = 0
    fail_count = 0

    for user in users:
      if not user['is_banned']:
        try:
          await context.bot.send_message(
              chat_id=user['user_id'],
              text=f'📢 *إشعار من الإدارة* 📢\n\n{message}',
              parse_mode=constants.ParseMode.MARKDOWN,
          )
          success_count += 1
        except Exception as e:
          print(f"Couldn't send broadcast to {user['user_id']}: {e}")
          fail_count += 1
      await asyncio.sleep(0.1)
    await context.bot.send_message(
      chat_id=chat_id,
      text=f'✅ تم إرسال الإشعار بنجاح لـ {success_count} مستخدم\n❌ فشل الإرسال لـ {fail_count} مستخدم',
  )
