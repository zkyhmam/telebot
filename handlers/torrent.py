import asyncio
import os
import time
import aria2p
from telegram import Update, constants
from telegram.ext import ContextTypes
from utils.data import get_user, add_download, update_download, update_user, update_daily_stats
from utils.format import format_size, format_time
from config import DEFAULT_DOWNLOAD_PATH, DELETION_PERIOD
import ffmpeg
import shutil
from datetime import datetime

# إعداد عميل aria2
aria2 = aria2p.API(
    aria2p.Client(
        host="http://localhost",
        port=6800,
        secret=""  # إذا أضفت سرًا في aria2c، ضعه هنا
    )
)

async def handle_magnet_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    magnet_link = update.message.text

    user = get_user(user_id)
    if not user or user['is_banned'] or not user['is_active']:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ معلش، مش مسموح ليك تستخدم البوت دلوقتي")
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🚀 جاري تحليل لينك التورنت... شد حيلك معانا! ⌛")

    try:
        # إعداد مسار التحميل للمستخدم
        download_path = os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id))
        os.makedirs(download_path, exist_ok=True)

        # إضافة التورنت إلى aria2
        options = {
            "dir": download_path,
            "max-concurrent-downloads": "10",
            "bt-max-peers": "100",
            "enable-dht": "true",
            "bt-enable-lpd": "true"
        }
        download = aria2.add_magnet(magnet_link, options=options)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🔄 جاري تحميل الميتاداتا... استنى شوية 😎"
        )

        # انتظار الحصول على الميتاداتا مع مهلة زمنية
        timeout = 60  # 60 ثانية
        start_time = time.time()
        while not download.is_complete and not download.has_failed and download.total_length == 0:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text="❌ *فشل في تحميل الميتاداتا* ❌\n\n⚠️ السبب: ما فيش رد من الـ Peers أو الـ Seeders. جرب لينك تاني 🧐",
                    parse_mode=constants.ParseMode.MARKDOWN
                )
                aria2.remove([download])
                return
            print(f"Waiting for metadata - Elapsed: {elapsed_time:.1f}s, Status: {download.status}")
            await asyncio.sleep(1)
            download.update()

        torrent_name = download.name
        total_size = download.total_length

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"🚀 *تورنت جديد* 🚀\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(total_size)}\n🔄 جاري بدء التحميل...",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        if total_size > user['max_download_size']:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"⚠️ *حجم التورنت أكبر من الحد المسموح* ⚠️\n\n📝 اسم التورنت: {torrent_name}\n📦 حجم التورنت: {format_size(total_size)}\n📏 الحد الأقصى المسموح: {format_size(user['max_download_size'])}\n\nاتواصل مع الأدمن لو محتاج تزود المساحة 😉",
                parse_mode=constants.ParseMode.MARKDOWN
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

        start_time = time.time()
        last_update = start_time
        downloaded_before = 0

        while not download.is_complete:
            download.update()
            if download.has_failed:
                raise Exception(f"فشل التحميل: {download.error_message}")

            now = time.time()
            time_diff = now - last_update
            downloaded = download.completed_length
            download_diff = downloaded - downloaded_before
            speed = download_diff / time_diff if time_diff > 0 else 0

            progress = (downloaded / total_size) * 100 if total_size > 0 else 0
            eta = (total_size - downloaded) / speed if speed > 0 else 0
            eta_formatted = format_time(eta)

            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"🚀 *جاري تحميل التورنت...* ⚡\n\n📝 الاسم: `{torrent_name}`\n▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢\n\n🔗 الحجم: {format_size(downloaded)} | {format_size(total_size)}\n⏳️ اكتمل: {progress:.2f}%\n🚀 السرعة: {format_size(speed)}/s\n⏰️ المدة المتبقية: {eta_formatted}",
                    parse_mode=constants.ParseMode.MARKDOWN
                )
            except Exception as e:
                print(f"Error updating status: {e}")

            last_update = now
            downloaded_before = downloaded
            await asyncio.sleep(3)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✅ *تم تحميل التورنت بنجاح!* 🎉\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(total_size)}\n⏱ المدة: {format_time(time.time() - start_time)}\n\n🔄 جاري معالجة الملفات وإرسالها... 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        # إرسال الملفات
        torrent_path = os.path.join(download_path, torrent_name)
        files = [f for f in os.listdir(torrent_path) if os.path.isfile(os.path.join(torrent_path, f))]

        for i, file in enumerate(files):
            file_path = os.path.join(torrent_path, file)
            file_size = os.path.getsize(file_path)

            if file_size < 10000:
                print(f"Skipping small file: {file}")
                continue

            try:
                file_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔄 جاري إرسال الملف {i + 1}/{len(files)}: {file} ({format_size(file_size)})"
                )

                file_ext = os.path.splitext(file)[1].lower()
                video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp']

                if file_ext in video_exts:
                    try:
                        thumb_path = os.path.join(os.path.dirname(file_path), f"{os.path.splitext(file)[0]}_thumb.jpg")
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
                        print("Thumbnail deleted")
                    except ffmpeg.Error as e:
                        print(f"Error creating thumbnail: {e.stderr.decode()}")
                        with open(file_path, 'rb') as video_file:
                            await context.bot.send_video(
                                chat_id=chat_id,
                                video=video_file,
                                caption=f"📹 {file}\n📦 {format_size(file_size)}"
                            )
                else:
                    with open(file_path, 'rb') as doc_file:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=doc_file,
                            caption=f"📄 {file}\n📦 {format_size(file_size)}"
                        )

                await context.bot.delete_message(chat_id=chat_id, message_id=file_msg.message_id)
            except Exception as e:
                print(f"Error sending file {file}: {e}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ حصل خطأ أثناء إرسال الملف: {file}\n{e}"
                )

        download_info['status'] = 'completed'
        update_download(download_info)
        update_user({
            'user_id': user_id,
            'total_downloads': user['total_downloads'] + 1,
            'last_activity': datetime.now()
        })

        update_daily_stats(0, 1, total_size)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ *تم إرسال كل الملفات بنجاح!* 🎉\n\n📝 اسم التورنت: {torrent_name}\n📦 الحجم الكلي: {format_size(total_size)}\n📁 عدد الملفات: {len(files)}\n\nشكراً لاستخدامك البوت المصري 🇪🇬 لو عايز تحمل حاجة تانية ابعت لينك جديد 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        # تنظيف
        try:
            aria2.remove([download])
            shutil.rmtree(download_path)
        except Exception as e:
            print(f"Failed to clean up: {e}")

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ *فشل في تحميل التورنت* ❌\n\n⚠️ الخطأ: {e}\n\nتأكد أن اللينك صح وجرب تاني 🧐",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        print(f"An error occurred: {e}")

async def handle_torrent_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    user = get_user(user_id)
    if not user or user['is_banned'] or not user['is_active']:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ معلش، مش مسموح ليك تستخدم البوت دلوقتي")
        return

    status_msg = await context.bot.send_message(chat_id=chat_id, text="🚀 جاري تحميل ملف التورنت... شد حيلك معانا! ⌛")

    try:
        file = await context.bot.get_file(update.message.document.file_id)
        file_name = update.message.document.file_name
        download_path = os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id))
        file_path = os.path.join(download_path, file_name)
        os.makedirs(download_path, exist_ok=True)
        await file.download_to_drive(file_path)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🔄 جاري معالجة ملف التورنت... استنى شوية 😎"
        )

        # إضافة ملف التورنت إلى aria2
        options = {
            "dir": download_path,
            "max-concurrent-downloads": "10",
            "bt-max-peers": "100",
            "enable-dht": "true",
            "bt-enable-lpd": "true"
        }
        download = aria2.add_torrent(file_path, options=options)

        # انتظار الحصول على معلومات التحميل
        timeout = 60
        start_time = time.time()
        while not download.is_complete and not download.has_failed and download.total_length == 0:
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text="❌ *فشل في تحميل الميتاداتا* ❌\n\n⚠️ السبب: ما فيش رد من الـ Peers أو الـ Seeders. جرب ملف تاني 🧐",
                    parse_mode=constants.ParseMode.MARKDOWN
                )
                aria2.remove([download])
                os.remove(file_path)
                return
            print(f"Waiting for metadata - Elapsed: {elapsed_time:.1f}s, Status: {download.status}")
            await asyncio.sleep(1)
            download.update()

        torrent_name = download.name
        total_size = download.total_length

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"🚀 *تورنت جديد* 🚀\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(total_size)}\n🔄 جاري بدء التحميل...",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        if total_size > user['max_download_size']:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"⚠️ *حجم التورنت أكبر من الحد المسموح* ⚠️\n\n📝 اسم التورنت: {torrent_name}\n📦 حجم التورنت: {format_size(total_size)}\n📏 الحد الأقصى المسموح: {format_size(user['max_download_size'])}\n\nاتواصل مع الأدمن لو محتاج تزود المساحة 😉",
                parse_mode=constants.ParseMode.MARKDOWN
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
        last_update = start_time
        downloaded_before = 0

        while not download.is_complete:
            download.update()
            if download.has_failed:
                raise Exception(f"فشل التحميل: {download.error_message}")

            now = time.time()
            time_diff = now - last_update
            downloaded = download.completed_length
            download_diff = downloaded - downloaded_before
            speed = download_diff / time_diff if time_diff > 0 else 0

            progress = (downloaded / total_size) * 100 if total_size > 0 else 0
            eta = (total_size - downloaded) / speed if speed > 0 else 0
            eta_formatted = format_time(eta)

            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"🚀 *جاري تحميل التورنت...* ⚡\n\n📝 الاسم: `{torrent_name}`\n▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢\n\n🔗 الحجم: {format_size(downloaded)} | {format_size(total_size)}\n⏳️ اكتمل: {progress:.2f}%\n🚀 السرعة: {format_size(speed)}/s\n⏰️ المدة المتبقية: {eta_formatted}",
                    parse_mode=constants.ParseMode.MARKDOWN
                )
            except Exception as e:
                print(f"Error updating status: {e}")

            last_update = now
            downloaded_before = downloaded
            await asyncio.sleep(3)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"✅ *تم تحميل التورنت بنجاح!* 🎉\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(total_size)}\n⏱ المدة: {format_time(time.time() - start_time)}\n\n🔄 جاري معالجة الملفات وإرسالها... 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        # إرسال الملفات
        torrent_path = os.path.join(download_path, torrent_name)
        files = [f for f in os.listdir(torrent_path) if os.path.isfile(os.path.join(torrent_path, f))]

        for i, file in enumerate(files):
            file_path = os.path.join(torrent_path, file)
            file_size = os.path.getsize(file_path)

            if file_size < 10000:
                print(f"Skipping small file: {file}")
                continue

            try:
                file_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"🔄 جاري إرسال الملف {i + 1}/{len(files)}: {file} ({format_size(file_size)})"
                )

                file_ext = os.path.splitext(file)[1].lower()
                video_exts = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp']

                if file_ext in video_exts:
                    try:
                        thumb_path = os.path.join(os.path.dirname(file_path), f"{os.path.splitext(file)[0]}_thumb.jpg")
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
                        print("Thumbnail deleted")
                    except ffmpeg.Error as e:
                        print(f"Error creating thumbnail: {e.stderr.decode()}")
                        with open(file_path, 'rb') as video_file:
                            await context.bot.send_video(
                                chat_id=chat_id,
                                video=video_file,
                                caption=f"📹 {file}\n📦 {format_size(file_size)}"
                            )
                else:
                    with open(file_path, 'rb') as doc_file:
                        await context.bot.send_document(
                            chat_id=chat_id,
                            document=doc_file,
                            caption=f"📄 {file}\n📦 {format_size(file_size)}"
                        )

                await context.bot.delete_message(chat_id=chat_id, message_id=file_msg.message_id)
            except Exception as e:
                print(f"Error sending file {file}: {e}")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ حصل خطأ أثناء إرسال الملف: {file}\n{e}"
                )

        download_info['status'] = 'completed'
        update_download(download_info)
        update_user({
            'user_id': user_id,
            'total_downloads': user['total_downloads'] + 1,
            'last_activity': datetime.now()
        })

        update_daily_stats(0, 1, total_size)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ *تم إرسال كل الملفات بنجاح!* 🎉\n\n📝 اسم التورنت: {torrent_name}\n📦 الحجم الكلي: {format_size(total_size)}\n📁 عدد الملفات: {len(files)}\n\nشكراً لاستخدامك البوت المصري 🇪🇬 لو عايز تحمل حاجة تانية ابعت لينك جديد 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        # تنظيف
        try:
            aria2.remove([download])
            os.remove(file_path)
            shutil.rmtree(download_path)
        except Exception as e:
            print(f"Failed to clean up: {e}")

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ *فشل في تحميل التورنت* ❌\n\n⚠️ الخطأ: {e}\n\nتأكد أن الملف صحيح وجرب تاني 🧐",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        print(f"An error occurred: {e}")
