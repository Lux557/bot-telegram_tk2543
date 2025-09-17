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

# Генерация уникального ID для сообщения
def generate_moderation_id():
    import uuid
    return str(uuid.uuid4())

# Обработчики сообщений и колбэков
@dp.message(F.text | F.photo | F.video)
async def handle_user_message(message: Message, bot: Bot):
    if message.photo or message.video or message.text:
        moderation_id = generate_moderation_id()
        admin_messages = {}
        
        for admin_id in ADMIN_IDS:
            try:
                # Создаем клавиатуру с уникальным callback_data для каждого сообщения
                admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text='✅ Принять', callback_data=f'approve_{moderation_id}'),
                        InlineKeyboardButton(text='❌ Отклонить', callback_data=f'decline_{moderation_id}')
                    ]
                ])
                
                copied_message = await bot.copy_message(
                    chat_id=admin_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=admin_keyboard
                )
                admin_messages[admin_id] = copied_message.message_id
            except Exception as e:
                print(f"Failed to copy message to admin {admin_id}: {e}")

        # Сохраняем информацию о сообщении с уникальным ID
        moderation_storage[moderation_id] = {
            'chat_id': message.chat.id,
            'message_id': message.message_id,
            'content_type': message.content_type,
            'admin_messages': admin_messages,
            'moderation_id': moderation_id
        }
        
        await message.answer('✅ Ваше сообщение на одобрении у администрации.')

@dp.callback_query(F.data.startswith('approve_'))
async def approve_message(callback_query: CallbackQuery, bot: Bot):
    moderation_id = callback_query.data.split('_')[1]
    message_info = moderation_storage.get(moderation_id)
    
    if message_info:
        try:
            # Отправляем сообщение в канал
            await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=message_info['chat_id'],
                message_id=message_info['message_id']
            )
            
            # Удаляем сообщения у всех администраторов
            for admin_id, mod_msg_id in message_info['admin_messages'].items():
                try:
                    await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
                except Exception as e:
                    print(f"Failed to delete message for admin {admin_id}: {e}")
            
            # Удаляем из хранилища
            del moderation_storage[moderation_id]
            
            # Отправляем подтверждение админу
            await callback_query.answer('Сообщение опубликовано в канале!')
            
        except Exception as e:
            await callback_query.answer(f'❌ Ошибка: {e}')
    else:
        await callback_query.answer('Сообщение уже обработано или не найдено')
        await bot.delete_message(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

@dp.callback_query(F.data.startswith('decline_'))
async def decline_message(callback_query: CallbackQuery, bot: Bot):
    moderation_id = callback_query.data.split('_')[1]
    message_info = moderation_storage.get(moderation_id)
    
    if message_info:
        # Удаляем сообщения у всех администраторов
        for admin_id, mod_msg_id in message_info['admin_messages'].items():
            try:
                await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
            except Exception as e:
                print(f"Failed to delete message for admin {admin_id}: {e}")
        
        # Удаляем из хранилища
        moderation_storage.pop(moderation_id, None)
        
        await callback_query.answer('Сообщение отклонено!')
    else:
        await callback_query.answer('Сообщение уже обработано или не найдено')
        await bot.delete_message(
            chat_id=callback_query.from_user.id,
            message_id=callback_query.message.message_id
        )

# --- Код для вебхуков ---
WEBHOOK_PATH = f"/bot/{TOKEN}"
WEB_SERVER_HOST = "0.0.0.0"
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

    request_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        handle_in_background=True
    )
    request_handler.register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)

if __name__ == "__main__":
    main()