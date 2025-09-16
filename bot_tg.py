import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

# Temporary storage for moderation messages
# Key: The message ID of the moderation request sent to the *first* admin
# Value: A dict containing original message info and a mapping of admin_id -> moderation_message_id
moderation_storage = {}

# Replace these values with your own
# NOTE: It's highly recommended to use environment variables for the TOKEN and other sensitive data
TOKEN = os.getenv('TOKEN', '8402137902:AAGfPEotg4Z5klNJjAeEDIH8BwPbBqV_CWQ')
ADMIN_IDS = [928321599, 8117211008, 1039676430, 860561862, 1480128887]
CHANNEL_ID = -1003098265954

# Admin keyboard
moderation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='✅ Принять', callback_data='approve'),
        InlineKeyboardButton(text='❌ Отклонить', callback_data='decline')
    ]
])

# Declare dispatcher dp in the global scope
dp = Dispatcher()

# Use decorators to register handlers
@dp.message(F.text | F.photo | F.video)
async def handle_user_message(message: Message, bot: Bot):
    admin_message_text = "Новое анонимное сообщение:\n\n"
    if message.text:
        admin_message_text += message.text
    elif message.photo:
        admin_message_text += message.caption if message.caption else "(Сообщение содержит фото)"
    elif message.video:
        admin_message_text += message.caption if message.caption else "(Сообщение содержит видео)"

    admin_messages = {}
    for admin_id in ADMIN_IDS:
        try:
            moderation_message = await bot.send_message(
                admin_id,
                admin_message_text,
                reply_markup=moderation_keyboard
            )
            admin_messages[admin_id] = moderation_message.message_id
        except Exception as e:
            print(f"Failed to send message to admin {admin_id}: {e}")

    first_admin_message_id = admin_messages[ADMIN_IDS[0]] if ADMIN_IDS else None
    if first_admin_message_id:
        moderation_storage[first_admin_message_id] = {
            'chat_id': message.chat.id,
            'message_id': message.message_id,
            'content_type': message.content_type,
            'admin_messages': admin_messages
        }
    await message.answer('✅ Ваше сообщение на одобрении у администрации.')

@dp.callback_query(F.data == 'approve')
async def approve_message(callback_query: CallbackQuery, bot: Bot):
    message_info = moderation_storage.get(callback_query.message.message_id)

    if message_info:
        try:
            await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=message_info['chat_id'],
                message_id=message_info['message_id']
            )
            for admin_id, mod_msg_id in message_info['admin_messages'].items():
                try:
                    await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
                except Exception as e:
                    print(f"Failed to delete message for admin {admin_id}: {e}")
            del moderation_storage[callback_query.message.message_id]
        except Exception as e:
            await bot.edit_message_text(
                f'❌ Не удалось опубликовать сообщение. Ошибка: {e}',
                chat_id=str(callback_query.from_user.id),
                message_id=callback_query.message.message_id
            )
    else:
        await bot.edit_message_text(
            '⚠️ Это сообщение уже было обработано.',
            chat_id=str(callback_query.from_user.id),
            message_id=callback_query.message.message_id
        )

@dp.callback_query(F.data == 'decline')
async def decline_message(callback_query: CallbackQuery, bot: Bot):
    if callback_query.message.message_id in moderation_storage:
        message_info = moderation_storage.get(callback_query.message.message_id)
        for admin_id, mod_msg_id in message_info['admin_messages'].items():
            try:
                await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
            except Exception as e:
                print(f"Failed to delete message for admin {admin_id}: {e}")
        moderation_storage.pop(callback_query.message.message_id, None)
    else:
        await bot.edit_message_text(
            '⚠️ Это сообщение уже было обработано.',
            chat_id=str(callback_query.from_user.id),
            message_id=callback_query.message.message_id
        )

# --- WEBHOOK-RELATED CODE ---
# This part replaces dp.start_polling
# You will get this URL from Render after you deploy your bot.
# The webhook path is important. Use a secret path to avoid spam.
WEBHOOK_PATH = f"/bot/53dc5d369033c78b36666ec405f12acb}" 
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 5000))

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

async def on_startup(app: web.Application):
    # This URL will be automatically generated by Render
    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{WEBHOOK_PATH}"
    print(f"Setting webhook URL to {WEBHOOK_URL}")
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

async def on_shutdown(app: web.Application):
    print("Shutting down...")
    await bot.delete_webhook()
    await bot.close_session()

async def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    app.router.add_post(WEBHOOK_PATH, dp.web_hook_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEB_SERVER_HOST, WEB_SERVER_PORT)
    print(f"Starting web server on {WEB_SERVER_HOST}:{WEB_SERVER_PORT}")
    await site.start()
    
    # Wait indefinitely for aiohttp to finish
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

