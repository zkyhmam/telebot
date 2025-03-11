import importlib
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from config import TOKEN  # استيراد TOKEN من config.py

# إنشاء التطبيق باستخدام التوكن من config.py
application = Application.builder().token(TOKEN).build()

# Configure logging (very detailed)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)
logger = logging.getLogger(__name__)

modules_to_import = ['start', 'help', 'stats', 'downloads', 'admin', 'torrent']
handlers = {}

for module_name in modules_to_import:
    try:
        logger.debug(f"Trying to import: handlers.{module_name}")
        handlers[module_name] = importlib.import_module(f'handlers.{module_name}')
        logger.info(f"Successfully imported: handlers.{module_name}")
    except UnicodeDecodeError as e:
        logger.error(f"Failed to import handlers.{module_name}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred while importing handlers.{module_name}: {e}", exc_info=True)

# on different commands - answer in Telegram
application.add_handler(CommandHandler("start", handlers['start'].start))
application.add_handler(CommandHandler("help", handlers['help'].help_cmd))
application.add_handler(CommandHandler("stats", handlers['stats'].stats))
application.add_handler(CommandHandler("downloads", handlers['downloads'].downloads))

# Admin commands
application.add_handler(CommandHandler("admin_stats", handlers['admin'].admin_stats))
application.add_handler(CommandHandler("admin_chart", handlers['admin'].admin_chart))
application.add_handler(CommandHandler("users", handlers['admin'].users))
application.add_handler(CommandHandler("ban", handlers['admin'].ban))
application.add_handler(CommandHandler("unban", handlers['admin'].unban))
application.add_handler(CommandHandler("set_limit", handlers['admin'].set_limit))
application.add_handler(CommandHandler('broadcast', handlers['admin'].broadcast))

# on non command i.e message - echo the message on Telegram
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers['torrent'].handle_magnet_link))
application.add_handler(MessageHandler(filters.Document.MimeType("application/x-bittorrent"), handlers['torrent'].handle_torrent_file))

if __name__ == "__main__":
    logger.info("Starting bot...")
    application.run_polling()
