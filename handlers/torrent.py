import asyncio
import os
import time
import aria2p
import subprocess
import shutil
from telegram import Update, constants
from telegram.ext import ContextTypes
from utils.data import get_user, add_download, update_download, update_user, update_daily_stats
from utils.format import format_size, format_time
from config import DEFAULT_DOWNLOAD_PATH, DELETION_PERIOD
import ffmpeg
from datetime import datetime

# إعداد عميل aria2
aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=6800,
        secret=""  # أضف السر إذا كنت تستخدمه في aria2c
    )
)

# دالة لتنظيف أسماء الملفات
def sanitize_filename(filename):
    invalid_chars = '\\/:*?"<>|'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename

# دالة لإعادة المحاولة (متزامنة)
def retry_with_backoff(func, max_retries=3, initial_backoff=1):
    backoff = initial_backoff
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(backoff)
            backoff *= 2

# دالة لإرسال الملفات الكبيرة مع التقسيم
async def send_large_file(context, chat_id, file_path, file_name, file_size):
    MAX_SIZE = 1.9 * 1024 * 1024 * 1024  # الحد الأقصى 1.9 جيجابايت
    
    try:
        if file_size <= MAX_SIZE:
            with open(file_path, 'rb') as doc_file:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=doc_file,
                    caption=f"📄 {file_name}\n📦 {format_size(file_size)}"
                )
        else:
            parts_dir = os.path.join(os.path.dirname(file_path), "parts")
            os.makedirs(parts_dir, exist_ok=True, mode=0o755)
            
            part_prefix = os.path.join(parts_dir, f"{file_name}_part_")
            subprocess.run(["split", "-b", str(int(MAX_SIZE)), file_path, part_prefix], check=True)
            
            parts = sorted(os.listdir(parts_dir))
            for i, part in enumerate(parts):
                part_path = os.path.join(parts_dir, part)
                with open(part_path, 'rb') as part_file:
                    await context.bot.send_document(
                        chat_id=chat_id,
                        document=part_file,
                        caption=f"📄 {file_name} (جزء {i+1}/{len(parts)})"
                    )
            
            await context.bot.send_message(
                chat_id=chat_id,
                text="لتجميع الأجزاء: استخدم الأمر `cat part_* > filename` في الطرفية."
            )
            shutil.rmtree(parts_dir)
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"⚠️ خطأ أثناء إرسال الملف: {e}")

async def handle_magnet_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    magnet_link = update.message.text

    user = get_user(user_id)
    if not user or user['is_banned'] or not user['is_active']:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ معلش، مش مسموح ليك تستخدم البوت دلوقتي")
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🚀 جاري تحميل التورنت...")

    try:
        # إعداد مسار التحميل مع التحقق من الصلاحيات
        download_path = os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id))
        try:
            os.makedirs(download_path, exist_ok=True, mode=0o755)
        except PermissionError:
            download_path = os.path.join(os.path.expanduser("~"), "temp_downloads", str(user_id))
            os.makedirs(download_path, exist_ok=True, mode=0o755)

        # إعدادات aria2 المحسنة
        options = {
            "dir": download_path,
            "max-concurrent-downloads": "20",
            "max-connection-per-server": "16",
            "min-split-size": "1M",
            "split": "16",
            "file-allocation": "none",
            "bt-max-peers": "200",
            "bt-request-peer-speed-limit": "5M",
            "check-integrity": "true"
        }

        # إضافة التورنت باستخدام retry_with_backoff بدون await
        download = retry_with_backoff(lambda: aria2.add_magnet(magnet_link, options=options))

        # انتظار الميتاداتا
        timeout = 60
        start_time = time.time()
        while not download.is_complete and not download.has_failed and download.total_length == 0:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text="❌ فشل في تحميل الميتاداتا\n\n⚠️ السبب: لا يوجد رد من الـ Peers أو الـ Seeders"
                )
                aria2.remove([download])
                return
            download.update()
            await asyncio.sleep(1)

        torrent_name = sanitize_filename(download.name)
        total_size = download.total_length

        if total_size > user['max_download_size']:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"⚠️ حجم التورنت أكبر من الحد المسموح: {format_size(total_size)}"
            )
            aria2.remove([download])
            return

        download_info = {
            'id': download.gid,
            'user_id': user_id,
            'file_name': torrent_name,
            'file_size': total_size,
            'magnet_link': magnet_link,
            'download_date': datetime.now(),
            'status': 'downloading'
        }
        add_download(download_info)

        # انتظار اكتمال التحميل بدون تحديثات متكررة
        start_time = time.time()
        while not download.is_complete:
            download.update()
            if download.has_failed:
                raise Exception(f"فشل التحميل: {download.error_message}")
            await asyncio.sleep(5)  # تحديث كل 5 ثوانٍ داخليًا بدون إرسال رسائل

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✅ اكتمل تحميل `{torrent_name}`\n📦 الحجم: {format_size(total_size)}\n⏱ المدة: {format_time(time.time() - start_time)}"
        )

        # إرسال الملفات
        torrent_path = download.dir
        files = [f for f in os.listdir(torrent_path) if os.path.isfile(os.path.join(torrent_path, f))]

        for i, file in enumerate(files):
            file_path = os.path.join(torrent_path, file)
            file_size = os.path.getsize(file_path)

            if file_size < 10000:  # تجاهل الملفات الصغيرة
                continue

            file_ext = os.path.splitext(file)[1].lower()
            video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp']

            if file_ext in video_exts:
                try:
                    thumb_path = os.path.join(torrent_path, f"{os.path.splitext(file)[0]}_thumb.jpg")
                    (
                        ffmpeg
                        .input(file_path, ss=0)
                        .filter('scale', 320, -1)
                        .output(thumb_path, vframes=1)
                        .run(capture_stdout=True, capture_stderr=True)
                    )

                    with open(file_path, 'rb') as video_file, open(thumb_path, 'rb') as thumb_file:
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=video_file,
                            caption=f"📹 {file}\n📦 {format_size(file_size)}",
                            thumb=thumb_file
                        )
                    os.remove(thumb_path)
                except Exception as e:
                    await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'),
                                                    caption=f"📹 {file}\n📦 {format_size(file_size)}")
            else:
                await send_large_file(context, chat_id, file_path, file, file_size)

        download_info['status'] = 'completed'
        update_download(download_info)
        update_user({
            'user_id': user_id,
            'total_downloads': user['total_downloads'] + 1,
            'last_activity': datetime.now()
        })
        update_daily_stats(0, 1, total_size)

        # تنظيف
        try:
            aria2.remove([download])
            shutil.rmtree(download_path)
        except Exception as e:
            print(f"فشل التنظيف: {e}")

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ فشل في تحميل التورنت\n\n⚠️ الخطأ: {e}"
        )
        print(f"خطأ: {e}")

async def handle_torrent_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    user = get_user(user_id)
    if not user or user['is_banned'] or not user['is_active']:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ معلش، مش مسموح ليك تستخدم البوت دلوقتي")
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🚀 جاري تحميل التورنت...")

    try:
        file = await context.bot.get_file(update.message.document.file_id)
        file_name = update.message.document.file_name
        download_path = os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id))
        
        try:
            os.makedirs(download_path, exist_ok=True, mode=0o755)
        except PermissionError:
            download_path = os.path.join(os.path.expanduser("~"), "temp_downloads", str(user_id))
            os.makedirs(download_path, exist_ok=True, mode=0o755)

        file_path = os.path.join(download_path, file_name)
        await file.download_to_drive(file_path)

        options = {
            "dir": download_path,
            "max-concurrent-downloads": "20",
            "max-connection-per-server": "16",
            "min-split-size": "1M",
            "split": "16",
            "file-allocation": "none",
            "bt-max-peers": "200",
            "bt-request-peer-speed-limit": "5M",
            "check-integrity": "true"
        }

        # إضافة التورنت باستخدام retry_with_backoff بدون await
        download = retry_with_backoff(lambda: aria2.add_torrent(file_path, options=options))

        timeout = 60
        start_time = time.time()
        while not download.is_complete and not download.has_failed and download.total_length == 0:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text="❌ فشل في تحميل الميتاداتا\n\n⚠️ السبب: لا يوجد رد من الـ Peers أو الـ Seeders"
                )
                aria2.remove([download])
                os.remove(file_path)
                return
            download.update()
            await asyncio.sleep(1)

        torrent_name = sanitize_filename(download.name)
        total_size = download.total_length

        if total_size > user['max_download_size']:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"⚠️ حجم التورنت أكبر من الحد المسموح: {format_size(total_size)}"
            )
            aria2.remove([download])
            os.remove(file_path)
            return

        download_info = {
            'id': download.gid,
            'user_id': user_id,
            'file_name': torrent_name,
            'file_size': total_size,
            'magnet_link': None,
            'download_date': datetime.now(),
            'status': 'downloading'
        }
        add_download(download_info)

        start_time = time.time()
        while not download.is_complete:
            download.update()
            if download.has_failed:
                raise Exception(f"فشل التحميل: {download.error_message}")
            await asyncio.sleep(5)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✅ اكتمل تحميل `{torrent_name}`\n📦 الحجم: {format_size(total_size)}\n⏱ المدة: {format_time(time.time() - start_time)}"
        )

        torrent_path = download.dir
        files = [f for f in os.listdir(torrent_path) if os.path.isfile(os.path.join(torrent_path, f))]

        for i, file in enumerate(files):
            file_path = os.path.join(torrent_path, file)
            file_size = os.path.getsize(file_path)

            if file_size < 10000:
                continue

            file_ext = os.path.splitext(file)[1].lower()
            video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp']

            if file_ext in video_exts:
                try:
                    thumb_path = os.path.join(torrent_path, f"{os.path.splitext(file)[0]}_thumb.jpg")
                    (
                        ffmpeg
                        .input(file_path, ss=0)
                        .filter('scale', 320, -1)
                        .output(thumb_path, vframes=1)
                        .run(capture_stdout=True, capture_stderr=True)
                    )

                    with open(file_path, 'rb') as video_file, open(thumb_path, 'rb') as thumb_file:
                        await context.bot.send_video(
                            chat_id=chat_id,
                            video=video_file,
                            caption=f"📹 {file}\n📦 {format_size(file_size)}",
                            thumb=thumb_file
                        )
                    os.remove(thumb_path)
                except Exception as e:
                    await context.bot.send_document(chat_id=chat_id, document=open(file_path, 'rb'),
                                                    caption=f"📹 {file}\n📦 {format_size(file_size)}")
            else:
                await send_large_file(context, chat_id, file_path, file, file_size)

        download_info['status'] = 'completed'
        update_download(download_info)
        update_user({
            'user_id': user_id,
            'total_downloads': user['total_downloads'] + 1,
            'last_activity': datetime.now()
        })
        update_daily_stats(0, 1, total_size)

        try:
            aria2.remove([download])
            os.remove(file_path)
            shutil.rmtree(download_path)
        except Exception as e:
            print(f"فشل التنظيف: {e}")

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ فشل في تحميل التورنت\n\n⚠️ الخطأ: {e}"
        )
        print(f"خطأ: {e}")
