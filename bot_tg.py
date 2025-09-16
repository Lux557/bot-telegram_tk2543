import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums.parse_mode import ParseMode

# Temporary storage for moderation messages
# Key: The message ID of the moderation request sent to the *first* admin
# Value: A dict containing original message info and a mapping of admin_id -> moderation_message_id
moderation_storage = {}

# Replace these values with your own
TOKEN = '8402137902:AAGfPEotg4Z5klNJjAeEDIH8BwPbBqV_CWQ'
ADMIN_IDS = [928321599, 8117211008, 1039676430, 860561862, 1480128887]
CHANNEL_ID = -1002911613947

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

    # Store a mapping of admin_id to the sent message ID for synchronization
    admin_messages = {}

    # Send the message for moderation to each admin
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

    # Save the original message info and the admin message IDs
    first_admin_message_id = admin_messages[ADMIN_IDS[0]] if ADMIN_IDS else None
    if first_admin_message_id:
        moderation_storage[first_admin_message_id] = {
            'chat_id': message.chat.id,
            'message_id': message.message_id,
            'content_type': message.content_type,
            'admin_messages': admin_messages  # <-- Store all admin message IDs here
        }

    await message.answer('✅ Ваше сообщение на одобрении у администрации.')


@dp.callback_query(F.data == 'approve')
async def approve_message(callback_query: CallbackQuery, bot: Bot):
    # Get information about the original message using the message ID of the callback
    message_info = moderation_storage.get(callback_query.message.message_id)

    if message_info:
        try:
            # Use bot.copy_message to copy the message to the channel, keeping it anonymous
            await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=message_info['chat_id'],
                message_id=message_info['message_id']
            )

            # Synchronize across all admins by deleting the messages
            for admin_id, mod_msg_id in message_info['admin_messages'].items():
                try:
                    await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
                except Exception as e:
                    print(f"Failed to delete message for admin {admin_id}: {e}")

            # Remove the entry from temporary storage
            del moderation_storage[callback_query.message.message_id]

        except Exception as e:
            await bot.edit_message_text(
                f'❌ Не удалось опубликовать сообщение. Ошибка: {e}',
                chat_id=str(callback_query.from_user.id),
                message_id=callback_query.message.message_id
            )
    else:
        # This will be shown if another admin already processed it
        await bot.edit_message_text(
            '⚠️ Это сообщение уже было обработано.',
            chat_id=str(callback_query.from_user.id),
            message_id=callback_query.message.message_id
        )


@dp.callback_query(F.data == 'decline')
async def decline_message(callback_query: CallbackQuery, bot: Bot):
    if callback_query.message.message_id in moderation_storage:
        message_info = moderation_storage.get(callback_query.message.message_id)

        # Synchronize across all admins by deleting the messages
        for admin_id, mod_msg_id in message_info['admin_messages'].items():
            try:
                await bot.delete_message(chat_id=admin_id, message_id=mod_msg_id)
            except Exception as e:
                print(f"Failed to delete message for admin {admin_id}: {e}")

        moderation_storage.pop(callback_query.message.message_id, None)
    else:
        # This will be shown if another admin already processed it
        await bot.edit_message_text(
            '⚠️ Это сообщение уже было обработано.',
            chat_id=str(callback_query.from_user.id),
            message_id=callback_query.message.message_id
        )


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.delete_webhook()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())