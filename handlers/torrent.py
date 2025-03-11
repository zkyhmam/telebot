import asyncio
import os
import time
import libtorrent as lt
from telegram import Update, InputMediaVideo, InputMediaDocument, constants
from telegram.ext import ContextTypes, CallbackContext
from utils.data import get_user, add_download, update_download, update_user, update_daily_stats
from utils.format import format_size, format_time
from config import DEFAULT_DOWNLOAD_PATH, DELETION_PERIOD
import ffmpeg
import shutil
from datetime import datetime

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
        # إنشاء جلسة مع إعدادات محسنة
        ses = lt.session()
        settings = ses.get_settings()
        settings['connections_limit'] = 500  # زيادة الحد الأقصى للاتصالات
        settings['download_rate_limit'] = 0  # بدون حد للتحميل
        settings['upload_rate_limit'] = 0    # بدون حد للرفع
        settings['active_downloads'] = 10    # تحميلات نشطة متعددة
        settings['active_seeds'] = 10        # Seeds نشطة
        settings['enable_dht'] = True        # تفعيل DHT لاكتشاف المزيد من Peers
        # حذف 'enable_utp' لأنه غير مدعوم
        ses.apply_settings(settings)
        ses.listen_on(6881, 6891)

        params = {
            'save_path': os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id)),
            'storage_mode': lt.storage_mode_t(2),  # lt.storage_mode_t.storage_mode_sparse
            'url': magnet_link
        }

        handle = lt.add_magnet_uri(ses, magnet_link, params)
        ses.start_dht()

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🔄 جاري تحميل الميتاداتا... استنى شوية 😎"
        )

        while not handle.has_metadata():
            await asyncio.sleep(1)

        torinfo = handle.get_torrent_info()
        torrent_name = torinfo.name()

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"🚀 *تورنت جديد* 🚀\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(torinfo.total_size())}\n🔄 جاري بدء التحميل...",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        if torinfo.total_size() > user['max_download_size']:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"⚠️ *حجم التورنت أكبر من الحد المسموح* ⚠️\n\n📝 اسم التورنت: {torrent_name}\n📦 حجم التورنت: {format_size(torinfo.total_size())}\n📏 الحد الأقصى المسموح: {format_size(user['max_download_size'])}\n\nاتواصل مع الأدمن لو محتاج تزود المساحة 😉",
                parse_mode=constants.ParseMode.MARKDOWN
            )
            ses.remove_torrent(handle)
            return

        download = {
            'id': str(handle.info_hash()),
            'user_id': user_id,
            'file_name': torrent_name,
            'file_size': torinfo.total_size(),
            'magnet_link': magnet_link,
            'download_date': datetime.now(),
            'status': 'downloading'
        }
        add_download(download)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"🚀 *تورنت جديد* 🚀\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(torinfo.total_size())}\n🔄 جاري التحميل...",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        start_time = time.time()
        last_update = start_time
        downloaded_before = 0

        while handle.status().state != lt.torrent_status.seeding:
            s = handle.status()

            # طباعة عدد الـ Seeders وPeers للتشخيص
            print(f"Seeders: {s.num_seeds}, Peers: {s.num_peers}")

            now = time.time()
            time_diff = now - last_update
            downloaded = s.total_done
            download_diff = downloaded - downloaded_before
            speed = download_diff / time_diff if time_diff > 0 else 0

            progress = s.progress * 100
            eta = (torinfo.total_size() - downloaded) / speed if speed > 0 else 0
            eta_formatted = format_time(eta)

            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"🚀 *جاري تحميل التورنت...* ⚡\n\n📝 الاسم: `{torrent_name}`\n▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢\n\n🔗 الحجم: {format_size(downloaded)} | {format_size(torinfo.total_size())}\n⏳️ اكتمل: {progress:.2f}%\n🚀 السرعة: {format_size(speed)}/s\n⏰️ المدة المتبقية: {eta_formatted}",
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
            text=f"✅ *تم تحميل التورنت بنجاح!* 🎉\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(torinfo.total_size())}\n⏱ المدة: {format_time(time.time() - start_time)}\n\n🔄 جاري معالجة الملفات وإرسالها... 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        # Send files
        torrent_path = os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id), torrent_name)
        files = [f for f in os.listdir(torrent_path) if os.path.isfile(os.path.join(torrent_path, f))]

        for i, file in enumerate(files):
            file_path = os.path.join(torrent_path, file)
            file_size = os.path.getsize(file_path)

            # Skip very small files (usually system files)
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
        download['status'] = 'completed'
        update_download(download)
        update_user({
            'user_id': user_id,
            'total_downloads': user['total_downloads'] + 1,
            'last_activity': datetime.now()
        })

        update_daily_stats(0, 1, torinfo.total_size())

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ *تم إرسال كل الملفات بنجاح!* 🎉\n\n📝 اسم التورنت: {torrent_name}\n📦 الحجم الكلي: {format_size(torinfo.total_size())}\n📁 عدد الملفات: {len(files)}\n\nشكراً لاستخدامك البوت المصري 🇪🇬 لو عايز تحمل حاجة تانية ابعت لينك جديد 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        # Clean up
        try:
            ses.remove_torrent(handle)
            shutil.rmtree(os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id)))
        except Exception as e:
            print(f'Failed to remove the torrent or directory: {e}')

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

    status_msg = await context.bot.send_message(chat_id=chat_id, text='🚀 جاري تحميل ملف التورنت... شد حيلك معانا! ⌛')

    try:
        file = await context.bot.get_file(update.message.document.file_id)
        file_name = update.message.document.file_name
        file_path = os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id), file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)  # Create user directory
        await file.download_to_drive(file_path)

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text='🔄 جاري معالجة ملف التورنت... استنى شوية 😎',
        )

        # إنشاء جلسة مع إعدادات محسنة
        ses = lt.session()
        settings = ses.get_settings()
        settings['connections_limit'] = 500
        settings['download_rate_limit'] = 0
        settings['upload_rate_limit'] = 0
        settings['active_downloads'] = 10
        settings['active_seeds'] = 10
        settings['enable_dht'] = True
        # حذف 'enable_utp' لأنه غير مدعوم
        ses.apply_settings(settings)
        ses.listen_on(6881, 6891)

        info = lt.torrent_info(file_path)
        torrent_name = info.name()

        params = {
            'save_path': os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id)),
            'storage_mode': lt.storage_mode_t(2),  # lt.storage_mode_t.storage_mode_sparse
            'ti': info
        }

        handle = ses.add_torrent(params)
        ses.start_dht()

        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f'🚀 *تورنت جديد* 🚀\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(info.total_size())}\n🔄 جاري بدء التحميل...',
            parse_mode=constants.ParseMode.MARKDOWN
        )

        if info.total_size() > user['max_download_size']:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text=f"⚠️ *حجم التورنت أكبر من الحد المسموح* ⚠️\n\n📝 اسم التورنت: {torrent_name}\n📦 حجم التورنت: {format_size(info.total_size())}\n📏 الحد الأقصى المسموح: {format_size(user['max_download_size'])}\n\nاتواصل مع الأدمن لو محتاج تزود المساحة 😉",
                parse_mode=constants.ParseMode.MARKDOWN
            )
            ses.remove_torrent(handle)
            os.remove(file_path)  # Clean up the .torrent file
            return

        download = {
            'id': str(handle.info_hash()),
            'user_id': user_id,
            'file_name': torrent_name,
            'file_size': info.total_size(),
            'magnet_link': None,  # No magnet link for .torrent files
            'download_date': datetime.now(),
            'status': 'downloading'
        }
        add_download(download)

        start_time = time.time()
        last_update = start_time
        downloaded_before = 0

        while handle.status().state != lt.torrent_status.seeding:
            s = handle.status()

            # طباعة عدد الـ Seeders وPeers للتشخيص
            print(f"Seeders: {s.num_seeds}, Peers: {s.num_peers}")

            now = time.time()
            time_diff = now - last_update
            downloaded = s.total_done
            download_diff = downloaded - downloaded_before
            speed = download_diff / time_diff if time_diff > 0 else 0

            progress = s.progress * 100
            eta = (info.total_size() - downloaded) / speed if speed > 0 else 0
            eta_formatted = format_time(eta)

            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"🚀 *جاري تحميل التورنت...* ⚡\n\n📝 الاسم: `{torrent_name}`\n▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢▢\n\n🔗 الحجم: {format_size(downloaded)} | {format_size(info.total_size())}\n⏳️ اكتمل: {progress:.2f}%\n🚀 السرعة: {format_size(speed)}/s\n⏰️ المدة المتبقية: {eta_formatted}",
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
            text=f"✅ *تم تحميل التورنت بنجاح!* 🎉\n\n📝 الاسم: `{torrent_name}`\n📦 الحجم: {format_size(info.total_size())}\n⏱ المدة: {format_time(time.time() - start_time)}\n\n🔄 جاري معالجة الملفات وإرسالها... 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        # Send files
        torrent_path = os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id), torrent_name)
        files = [f for f in os.listdir(torrent_path) if os.path.isfile(os.path.join(torrent_path, f))]

        for i, file in enumerate(files):
            file_path = os.path.join(torrent_path, file)
            file_size = os.path.getsize(file_path)

            # Skip very small files (usually system files)
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

        download['status'] = 'completed'
        update_download(download)
        update_user({
            'user_id': user_id,
            'total_downloads': user['total_downloads'] + 1,
            'last_activity': datetime.now()
        })

        update_daily_stats(0, 1, info.total_size())

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ *تم إرسال كل الملفات بنجاح!* 🎉\n\n📝 اسم التورنت: {torrent_name}\n📦 الحجم الكلي: {format_size(info.total_size())}\n📁 عدد الملفات: {len(files)}\n\nشكراً لاستخدامك البوت المصري 🇪🇬 لو عايز تحمل حاجة تانية ابعت لينك جديد 🚀",
            parse_mode=constants.ParseMode.MARKDOWN
        )

        # Clean up
        try:
            ses.remove_torrent(handle)
            os.remove(file_path)  # Delete the .torrent file
            shutil.rmtree(os.path.join(DEFAULT_DOWNLOAD_PATH, str(user_id)))
        except Exception as e:
            print(f'Failed to remove the torrent or directory: {e}')

    except Exception as e:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text=f"❌ *فشل في تحميل ملف التورنت* ❌\n\n⚠️ الخطأ: {e}\n\nحاول تاني بملف تاني 🧐",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        print(f"An error occurred: {e}")
