import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Временное хранилище для сообщений на модерацию
moderation_storage = {}

# Используйте переменные окружения для ТОКЕНА в целях безопасности
# Если переменная окружения не установлена, будет использовано значение по умолчанию
TOKEN = os.getenv('TOKEN', '8402137902:AAGfPEotg4Z5klNJjAeEDIH8BwPbBqV_CWQ')
ADMIN_IDS = [928321599, 8117211008, 1039676430, 860561862, 1480128887]
CHANNEL_ID = -1003098265954

# Клавиатура для админа
moderation_keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text='✅ Принять', callback_data='approve'),
        InlineKeyboardButton(text='❌ Отклонить', callback_data='decline')
    ]
])

dp = Dispatcher()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Обработчики сообщений и колбэков
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

# --- Код для вебхуков ---
WEBHOOK_PATH = f"/bot/{TOKEN}"
WEB_SERVER_HOST = "44.229.227.142"
WEB_SERVER_PORT = int(os.environ.get("PORT", 5000))

async def on_startup(dp: Dispatcher):
    WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{WEBHOOK_PATH}"
    print(f"Setting webhook URL to {WEBHOOK_URL}")
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

async def on_shutdown(dp: Dispatcher):
    print("Shutting down...")
    await bot.delete_webhook()
    await bot.session.close()

def main():
    app = web.Application()

    # Правильная регистрация обработчика вебхуков для aiogram v3+
    request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True
    )
    request_handler.register(app, path=WEBHOOK_PATH)

    # Правильная регистрация обработчиков запуска и остановки
    setup_application(app, dp, bot=bot)

    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    main()

