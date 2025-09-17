import asyncio
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Хранилища для сообщений на модерацию
# Key: admin_message_id, Value: original_message_key
moderation_storage = {}
# Key: original_message_key, Value: {data about the message}
original_message_data = {}

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

# Обработчик сообщений
@dp.message(F.text | F.photo | F.video)
async def handle_user_message(message: Message, bot: Bot):
    if message.photo or message.video or message.text:
        # Уникальный ключ для оригинального сообщения
        original_msg_key = f"{message.chat.id}_{message.message_id}"
        
        # Сохраняем данные об оригинальном сообщении
        original_message_data[original_msg_key] = {
            'chat_id': message.chat.id,
            'message_id': message.message_id,
            'admin_messages': {}
        }
        
        for admin_id in ADMIN_IDS:
            try:
                copied_message = await bot.copy_message(
                    chat_id=admin_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                    reply_markup=moderation_keyboard
                )
                # Связываем ID скопированного сообщения с ключом оригинального
                moderation_storage[copied_message.message_id] = original_msg_key
                # Добавляем ID копии в данные оригинального сообщения
                original_message_data[original_msg_key]['admin_messages'][admin_id] = copied_message.message_id
            except Exception as e:
                print(f"Failed to copy message to admin {admin_id}: {e}")
        
        await message.answer('✅ Ваше сообщение на одобрении у администрации.')

# Обработчик принятия
@dp.callback_query(F.data == 'approve')
async def approve_message(callback_query: CallbackQuery, bot: Bot):
    # Находим ключ оригинального сообщения по ID сообщения админа
    original_msg_key = moderation_storage.get(callback_query.message.message_id)
    
    if not original_msg_key:
        await callback_query.answer('Это сообщение уже обработано.', show_alert=True)
        try:
            await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        except:
            pass
        return

    message_info = original_message_data.get(original_msg_key)
    
    if message_info:
        try:
            # Публикуем оригинальное сообщение в канал
            await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=message_info['chat_id'],
                message_id=message_info['message_id']
            )
            
            # Удаляем все копии сообщения у админов
            for admin_id, mod_msg_id in message_info['admin_messages'].items():
                try:
                    await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
                    moderation_storage.pop(mod_msg_id, None)
                except Exception as e:
                    print(f"Failed to delete message for admin {admin_id}: {e}")
            
            # Очищаем данные об оригинальном сообщении
            original_message_data.pop(original_msg_key, None)
            
            await callback_query.answer('Сообщение успешно опубликовано.')
        except Exception as e:
            await callback_query.answer(f'❌ Не удалось опубликовать сообщение. Ошибка: {e}', show_alert=True)

# Обработчик отклонения
@dp.callback_query(F.data == 'decline')
async def decline_message(callback_query: CallbackQuery, bot: Bot):
    # Находим ключ оригинального сообщения по ID сообщения админа
    original_msg_key = moderation_storage.get(callback_query.message.message_id)

    if not original_msg_key:
        await callback_query.answer('Это сообщение уже обработано.', show_alert=True)
        try:
            await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)
        except:
            pass
        return

    message_info = original_message_data.get(original_msg_key)
    
    if message_info:
        # Удаляем все копии сообщения у админов
        for admin_id, mod_msg_id in message_info['admin_messages'].items():
            try:
                await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
                moderation_storage.pop(mod_msg_id, None)
            except Exception as e:
                print(f"Failed to delete message for admin {admin_id}: {e}")
        
        # Очищаем данные об оригинальном сообщении
        original_message_data.pop(original_msg_key, None)

        await callback_query.answer('Сообщение отклонено.')

# --- Код для вебхуков ---
WEBHOOK_PATH = f"/bot/{TOKEN}"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.environ.get("PORT", 5000))

async def on_startup(dp: Dispatcher):
    # Для развертывания на Render, используйте переменную окружения RENDER_EXTERNAL_HOSTNAME
    # В локальной разработке, используйте ngrok или похожий сервис
    if os.getenv('RENDER_EXTERNAL_HOSTNAME'):
        WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}{WEBHOOK_PATH}"
    else:
        # Замените на ваш вебхук URL при локальной разработке
        # Например: 'https://<your-ngrok-url>.ngrok-free.app/bot/...'
        WEBHOOK_URL = "https://bot-