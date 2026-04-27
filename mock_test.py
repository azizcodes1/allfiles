import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import logging

# We import the handlers to test them directly
from bot import cmd_start, cmd_buy, handle_text, process_payment_selection, handle_photo
from database import init_db

from aiogram.types import Message, User, Chat, CallbackQuery

async def simulate_terminal_test():
    init_db()
    print("========================================")
    print("--- Modern Luxury AI Bot - Terminal Mock ---")
    print("========================================\n")

    # Setup Mocks
    mock_user = User(id=777, is_bot=False, first_name="VIP Client")
    mock_chat = Chat(id=777, type="private")

    # 1. Test /start
    print(">>> [Client]: /start")
    msg_start = AsyncMock(spec=Message)
    msg_start.answer = AsyncMock()
    msg_start.from_user = mock_user
    msg_start.chat = mock_chat
    await cmd_start(msg_start)
    print(f"<<< [Bot]:    {msg_start.answer.call_args[0][0]}\n")

    # 2. Test /buy
    print(">>> [Client]: /buy")
    msg_buy = AsyncMock(spec=Message)
    msg_buy.answer = AsyncMock()
    msg_buy.from_user = mock_user
    msg_buy.chat = mock_chat
    await cmd_buy(msg_buy)
    markup = msg_buy.answer.call_args[1].get('reply_markup')
    buttons = [btn.text for row in markup.inline_keyboard for btn in row]
    print(f"<<< [Bot]:    {msg_buy.answer.call_args[0][0]}")
    print(f"    [Options]: {', '.join(buttons)}\n")

    # 3. Test Callback Query (Selects Payme Gateway)
    print(">>> [Client]: *Selects 'Uzbekistan (Payme)'*")
    mock_cb = AsyncMock(spec=CallbackQuery)
    mock_cb.data = "pay_payme"
    mock_cb.answer = AsyncMock()
    mock_cb.message = AsyncMock()
    mock_cb.message.answer = AsyncMock()
    mock_cb.message.chat.id = 777
    
    with patch('bot.bot') as mock_bot:
        await process_payment_selection(mock_cb)
        if mock_cb.message.answer.called:
            print(f"<<< [Bot Alert]: {mock_cb.message.answer.call_args[0][0]}\n")
        elif mock_bot.send_invoice.called:
            invoice_args = mock_bot.send_invoice.call_args[1]
            print(f"<<< [Bot]:    *Sent Invoice via {invoice_args['provider_token']}*")
            print(f"              Amount: {invoice_args['prices'][0].amount} {invoice_args['currency']}\n")

    # 4. Test Text Prompt
    print(">>> [Client]: What defines modern luxury?")
    msg_text = AsyncMock(spec=Message)
    msg_text.answer = AsyncMock()
    msg_text.from_user = mock_user
    msg_text.text = "What defines modern luxury?"
    
    with patch('bot.ai_model') as mock_ai:
        mock_ai.generate_content.return_value = MagicMock(
            text="Modern luxury is an exclusive experience, bespoke and tailored to your sophisticated needs, encompassing both grace and refinement."
        )
        await handle_text(msg_text)
        print(f"<<< [Bot]:    {msg_text.answer.call_args[0][0]}\n")
        
    print("========================================")
    print("Mock tests completed successfully. ")

if __name__ == "__main__":
    logging.getLogger("aiogram").setLevel(logging.CRITICAL)
    asyncio.run(simulate_terminal_test())
