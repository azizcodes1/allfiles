import asyncio
import logging
import random
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import BOT_TOKEN, ADMIN_ID, GEMINI_API_KEY, PAYME_TOKEN, CLICK_TOKEN, MY_CARD_NUMBER, MY_VISA_CARD_NUMBER, SUBSCRIPTION_PRICE_UZS, SUBSCRIPTION_PRICE_USD
from database import init_db, add_user, set_premium, is_premium, set_user_language, get_user_language, create_transaction, save_generation, get_user_generations
from strings import LOCALIZED_STRINGS

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

POLLINATIONS_API_KEY = "sk_AJy1m7EisgRZEluJF8AR5e7CGs6DVBcy" # Get at enter.pollinations.ai

# Setup Gemini AI
genai.configure(api_key=GEMINI_API_KEY)

system_instruction_base = "You are a highly sophisticated, modern luxury AI assistant. Your tone should be elegant, refined, professional, and exclusively tailored. Address the user with grace and provide high-end, premium quality assistance. NEVER output JSON, code blocks, or internal reasoning unless explicitly asked. Always respond with clean, natural language."

ai_model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview",
    system_instruction=system_instruction_base
)

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_strings(user_id):
    lang = get_user_language(user_id) or "en"
    return LOCALIZED_STRINGS.get(lang, LOCALIZED_STRINGS["en"])

class ImageStates(StatesGroup):
    entering_prompt = State()
    entering_idea = State()
    entering_reference = State()

def get_main_menu(user_id):
    s = get_strings(user_id)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=s["menu_create"])],
            [KeyboardButton(text=s["menu_gallery"]), KeyboardButton(text=s["menu_buy"])],
            [KeyboardButton(text=s["support"])]
        ],
        resize_keyboard=True
    )
    return keyboard

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command with language selection"""
    add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz"),
                types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
                types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
            ]
        ]
    )
    
    await message.answer("Please select your preferred language:/ Iltimos, tilni tanlang:", reply_markup=markup)

@dp.callback_query(F.data.startswith("lang_"))
async def process_language_selection(callback: types.CallbackQuery):
    """Handle language selection and show welcome message"""
    lang = callback.data.split("_")[1]
    user_id = callback.from_user.id
    set_user_language(user_id, lang)
    
    s = LOCALIZED_STRINGS[lang]
    
    welcome_photo = "https://images.unsplash.com/photo-1614850523459-c2f4c699c52e?q=80&w=2670&auto=format&fit=crop"
    welcome_text = (
        f"✨ <b>{s['welcome']} to LuxePrompt AI</b> ✨\n\n"
        f"{s['desc']}\n\n"
        f"{s['create']}\n"
        f"Example: <code>/image A futuristic gold-plated workstation</code>\n\n"
        f"{s['premium']}"
    )
    
    try:
        await callback.message.delete()
    except: pass
    await bot.send_photo(
        chat_id=callback.message.chat.id,
        photo=welcome_photo,
        caption=welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu(user_id)
    )
    await callback.answer()

@dp.message(Command("buy"))
async def cmd_buy(message: types.Message):
    """Handle /buy command to show payment gateways"""
    s = get_strings(message.from_user.id)
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=s["pay_uzb"], callback_data="pay_manual")],
            [types.InlineKeyboardButton(text=s["pay_visa"], callback_data="pay_visa_manual")]
        ]
    )
    await message.answer(s["buy_prompt"], reply_markup=markup)

@dp.message(Command("imagine", "image"))
async def cmd_imagine(message: types.Message):
    """Handle /imagine and /image with speed tiers"""
    prompt = message.text.replace("/imagine", "").replace("/image", "").strip()
    await run_image_generation(message, prompt)

async def run_image_generation(message: types.Message, prompt: str, user: types.User = None):
    """Core image generation logic shared across handlers"""
    effective_user = user or message.from_user
    user_id = effective_user.id
    add_user(user_id, effective_user.full_name, effective_user.username)
    s = get_strings(user_id)
    
    if not prompt:
        await message.answer(s["imagine_prompt"], parse_mode="Markdown")
        return

    # Determine if user is premium and log status
    premium = is_premium(user_id)
    logging.info(f"User {user_id} premium status: {premium}")
    
    if premium:
        wait_time = 5  # Premium users get fast response
        await message.answer(s["premium_wait"], parse_mode="HTML")
    else:
        # Check nudges for free users
        gens = get_user_generations(user_id)
        if len(gens) == 3:
            await message.answer("💎 <b>Level Up:</b> You have a great eye for design. Upgrade to Premium now to skip the 2-minute wait and unlock 4K Ultra Analysis. Use /buy", parse_mode="HTML")
        
        wait_time = 150
        status_msg = await message.answer(f"{s['progress_prefix']} [░░░░░░░░░░] 0%", parse_mode="HTML")
    
    # --- DIRECTOR MODE: Refining the prompt ---
    director_msg = await message.answer(s["director_mode"], parse_mode="HTML")
    try:
        import re as _re
        # Detect if the user wants text/letters in the image (catches "...", '...', «...» etc.)
        text_in_image = _re.findall(r'["\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a]([^"\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a]{1,60})["\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a]', prompt)
        # Also detect common patterns like: spell "TEXT", text "TEXT", letters spell TEXT
        keyword_text = _re.findall(r'(?:spell(?:s)?|text|letters?|reads?|says?|written|sign(?:s)?)[^a-zA-Z]*["\u201c\u201d]?([A-Z][A-Z\s]{1,40})["\u201c\u201d]?', prompt)
        all_texts = list(dict.fromkeys(text_in_image + keyword_text))  # deduplicate
        text_hint = ""
        if all_texts:
            quoted = ", ".join([f'"{t.strip()}"' for t in all_texts])
            text_hint = (
                f"CRITICAL TEXT RULE: The image MUST display the following text exactly as written: {quoted}. "
                f"Each letter must be perfectly formed, sharp, clearly legible, and correctly spelled — no rearranging or skipping letters. "
                f"Reinforce by stating: 'the 3D letters clearly spell {quoted}' and 'text reads exactly {quoted} with perfect letter accuracy'. "
                f"Treat the text as large, prominent 3D physical objects in the scene. "
            )

        enhancer_prompt = (
            f"You are a world-class cinematic prompt engineer for Flux image generation. "
            f"Your task is to transform the user's idea into a breathtaking, highly detailed image prompt.\n\n"
            f"USER PROMPT: '{prompt}'\n\n"
            f"STEP-BY-STEP BUILDING RULES:\n"
            f"1. SUBJECT & SCENE: Identify the core subject. Describe it with hyper-specific visual detail — materials, textures, colors, proportions.\n"
            f"2. ART STYLE: Identify or infer the best art style (e.g. Studio Ghibli, Hyperrealistic, Lo-Fi Digital Illustration, Cinematic Photography, Oil Painting). State it clearly.\n"
            f"3. LIGHTING: Describe the exact lighting setup — golden hour, volumetric rays, soft rim lighting, neon glow, warm desk lamp, moonlight, etc.\n"
            f"4. ATMOSPHERE & MOOD: Describe the emotional feel — peaceful, majestic, nostalgic, tense, dreamy, cozy, epic.\n"
            f"5. COMPOSITION: Specify the shot type — cinematic wide shot, eye-level medium shot, low angle, bird's eye, rule of thirds, centered symmetry.\n"
            f"6. BACKGROUND & ENVIRONMENT: Paint the background in detail — weather, time of day, location, depth-of-field blur on distant elements.\n"
            f"7. TECHNICAL TAGS: End with quality boosters like: ultra-detailed, 8K resolution, sharp focus, vibrant colors, photorealistic textures, award-winning composition, masterpiece.\n"
            f"8. INTEGRITY: Do NOT add elements the user did NOT mention. Preserve every element they described exactly.\n"
            f"9. FACIAL DETAIL: If a person is present — realistic skin texture, expressive eyes, no distortion.\n"
            f"{text_hint}\n"
            f"Output ONLY the final enhanced prompt as a single, richly-worded paragraph. No JSON, no lists, no explanations."
        )
        enhanced_res = ai_model.generate_content(enhancer_prompt)
        enhanced_prompt = enhanced_res.text.strip()
    except:
        enhanced_prompt = prompt # Fallback
    
    try:
        await director_msg.delete()
    except: pass

    # --- PROGRESS BAR logic (for free users) ---
    if not premium:
        steps = 5
        for i in range(1, steps + 1):
            await asyncio.sleep(wait_time / steps)
            progress = i * (100 // steps)
            bar_len = i * 2
            bar = "█" * bar_len + "░" * (10 - bar_len)
            try:
                await status_msg.edit_text(f"{s['progress_prefix']} [{bar}] {progress}%", parse_mode="HTML")
            except: pass
    else:
        await asyncio.sleep(wait_time)
    
    try:
        from urllib.parse import quote
        safe_prompt = quote(enhanced_prompt)
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true&model=flux"
        
                # Download image to avoid "failed to get HTTP URL content" error
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=60) as response:
                if response.status == 200:
                    image_data = await response.read()
                    # Add watermark for free users
                    if not premium:
                        from PIL import Image, ImageDraw, ImageFont
                        import io

                        img = Image.open(io.BytesIO(image_data)).convert("RGBA")
                        watermark_text = "@LuxePromptBot"
                        width, height = img.size
                        font_size = max(20, width // 30)
                        try:
                            font = ImageFont.truetype("arial.ttf", font_size)
                        except Exception:
                            font = ImageFont.load_default()
                        draw = ImageDraw.Draw(img)
                        text_width, text_height = draw.textsize(watermark_text, font=font)
                        x = (width - text_width) / 2
                        y = (height - text_height) / 2
                        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 128))
                        output = io.BytesIO()
                        img.save(output, format="PNG")
                        image_data = output.getvalue()
                    photo = types.BufferedInputFile(image_data, filename="masterpiece.png")
                else:
                    photo = image_url  # Fallback
        
        # Markup for Gallery and Archive
        gallery_url = "https://azizcodes1.github.io/telegbot/gallery.html"
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=s["publish"], callback_data="publish_last")],
                [types.InlineKeyboardButton(text=s["add_to_gallery"], callback_data="confirm_add_gallery")],
                [types.InlineKeyboardButton(text=s["view_gallery"], web_app=types.WebAppInfo(url=gallery_url))]
            ]
        )
        
        caption_footer = "💎 Premium" if premium else "⚪ Standard"
        
        import html
        escaped_prompt = html.escape(enhanced_prompt)
        
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=photo,
            caption=f"🎥 <b>Director Refinement:</b>\n<i>{escaped_prompt[:800]}</i>\n\n<b>Tier:</b> {caption_footer}\n\nCreated via @LuxePromptBot",
            parse_mode="HTML",
            reply_markup=markup
        )
        
        if not premium:
            try:
                await status_msg.delete()
            except: pass
    except Exception as e:
        logging.error(f"Image generation error: {e}")
        await message.answer(s["error"])

@dp.message(Command("gallery"))
async def cmd_gallery(message: types.Message):
    """Open the Luxury Gallery Mini App"""
    user_id = message.from_user.id
    s = get_strings(user_id)
    gallery_url = "https://azizcodes1.github.io/telegbot/gallery.html"
    
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text=s["view_gallery"], web_app=types.WebAppInfo(url=gallery_url))]
        ]
    )
    await message.answer(f"✨ <b>LuxeArchive:</b> {s['view_gallery']}", reply_markup=markup, parse_mode="HTML")

@dp.callback_query(F.data == "open_gallery")
async def cb_open_gallery(callback: types.CallbackQuery):
    """Prompt to use /gallery command"""
    s = get_strings(callback.from_user.id)
    await callback.message.answer(f"Please use /gallery to open your exclusive visual archive.")
    await callback.answer()

@dp.callback_query(F.data == "confirm_add_gallery")
async def cb_confirm_add_gallery(callback: types.CallbackQuery):
    """Confirm image added to gallery"""
    # Note: Already saved in database during generation for reliability
    await callback.answer("📥 Masterpiece successfully added to your archive!", show_alert=True)

@dp.callback_query(F.data == "publish_last")
async def cb_publish_last(callback: types.CallbackQuery):
    """Publish the image to the Global Archive channel"""
    user_id = callback.from_user.id
    s = get_strings(user_id)
    
    gens = get_user_generations(user_id)
    if not gens:
        await callback.answer("No images found.")
        return
        
    last_gen = gens[0]
    CHANNEL_ID = "@LuxePrompt_Gallery" 
    
    try:
        import html
        escaped_vision = html.escape(last_gen[0])
        await bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=last_gen[1],
            caption=f"🏆 <b>Global Showcase Spotlight</b>\n\n<i>Refined Vision:</i>\n{escaped_vision}\n\n✨ Created via @LuxePromptBot",
            parse_mode="HTML"
        )
        await callback.message.answer("💎 Your masterpiece has been published to the Global Channel!")
    except Exception as e:
        logging.error(f"Publishing error: {e}")
        await callback.message.answer("An elegant interruption occurred. Ensure the bot is an admin in the channel.")
    
    await callback.answer()

@dp.callback_query(F.data.startswith("pay_"))
async def process_payment_selection(callback: types.CallbackQuery):
    """Handle payment gateway selection callbacks"""
    user_id = callback.from_user.id
    s = get_strings(user_id)
    gateway = callback.data.split("_")[1]
    
    try:
        if gateway == "visa":
            # Log as a manual transaction in DB for admin reference
            comment_id = f"VISA_{random.randint(100000, 999999)}"
            create_transaction(user_id, comment_id, SUBSCRIPTION_PRICE_USD)
            
            info = s["manual_visa_info"].format(amount=SUBSCRIPTION_PRICE_USD, card=MY_VISA_CARD_NUMBER)
            await callback.message.answer(info, parse_mode="HTML")
            await callback.answer()
            
            # Notify admin that a Visa payment was initiated
            try:
                username = callback.from_user.username or "N/A"
                full_name = callback.from_user.full_name or "N/A"
                admin_msg = (
                    f"💳 <b>New Visa Payment Initiated</b>\n\n"
                    f"👤 User: <a href='tg://user?id={user_id}'>{full_name}</a>\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"🔖 Username: @{username}\n"
                    f"💰 Amount: <b>${SUBSCRIPTION_PRICE_USD} USD</b>\n\n"
                    f"Once you receive the screenshot at @vm_aziz, click below to activate:"
                )
                
                # Inline button for instant activation
                markup = types.InlineKeyboardMarkup(
                    inline_keyboard=[[
                        types.InlineKeyboardButton(text="✅ Activate Premium", callback_data=f"activate_{user_id}")
                    ]]
                )
                
                await bot.send_message(ADMIN_ID, admin_msg, parse_mode="HTML", reply_markup=markup)
            except Exception as notify_err:
                logging.warning(f"Could not notify admin: {notify_err}")
            return

        if gateway == "manual":
            comment_id = str(random.randint(100000, 999999))
            create_transaction(user_id, comment_id, SUBSCRIPTION_PRICE_UZS)
            
            info = s["manual_info"].format(amount=SUBSCRIPTION_PRICE_UZS, card=MY_CARD_NUMBER, comment=comment_id)
            await callback.message.answer(info, parse_mode="HTML")
            await callback.answer()
            return
    except Exception as e:
        logging.error(f"Payment selection error: {e}")
        await callback.answer("An elegant interruption occurred. Please contact support.", show_alert=True)

@dp.callback_query(F.data.startswith("activate_"))
async def process_admin_activation(callback: types.CallbackQuery):
    """Handle instant premium activation from admin notification"""
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Unauthorized.", show_alert=True)
        return
        
    try:
        target_id = int(callback.data.split("_")[1])
        set_premium(target_id, True)
        
        # Notify Admin
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>SUCCESS:</b> Premium has been activated for this user.",
            parse_mode="HTML"
        )
        
        # Notify User
        try:
            await bot.send_message(target_id, "💎 *Premium Activated:* Your account has been upgraded to the *Modern Luxury Tier*. Welcome back!", parse_mode="Markdown")
        except: pass
        
        await callback.answer("User activated successfully!")
    except Exception as e:
        logging.error(f"Activation error: {e}")
        await callback.answer("Failed to activate user.")


@dp.message(ImageStates.entering_reference, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    """Handle premium image inputs"""
    user_id = message.from_user.id
    add_user(user_id, message.from_user.full_name, message.from_user.username)
    s = get_strings(user_id)
    
    if not is_premium(user_id):
        await message.answer(s["vision_premium"])
        return
        
    await message.answer(s["vision_processing"])
    
    try:
        from PIL import Image
        import io
        
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        downloaded_photo = await bot.download_file(file.file_path)
        
        img = Image.open(io.BytesIO(downloaded_photo.read()))
        user_instruction = message.caption if message.caption else "Create a high-end, cinematic artistic version of this image."
        
        # Analyze and refine prompt for image-to-image style experience
        analysis_prompt = (
            f"Analyze this image in detail. Then, based on the user's instruction: '{user_instruction}', "
            f"create a highly detailed, professional, cinematic image generation prompt for a new image. "
            f"The new prompt should preserve the core essence, subjects, and composition of the original "
            f"but apply the user's requested transformation in a modern luxury style. "
            f"Output ONLY the refined prompt text. No explanations."
        )
        
        response = ai_model.generate_content([analysis_prompt, img])
        refined_prompt = response.text.strip()
        
        # Clear state if any
        await state.clear()
        
        # Generate the new image based on the refined vision
        await run_image_generation(message, refined_prompt)
    except Exception as e:
        logging.error(f"Error processing image: {e}")
        await message.answer(s["error"])

@dp.message(F.text.in_([LOCALIZED_STRINGS["uz"]["support"], LOCALIZED_STRINGS["ru"]["support"], LOCALIZED_STRINGS["en"]["support"]]))
async def menu_support(message: types.Message):
    """Handle Support button from menu"""
    s = get_strings(message.from_user.id)
    await message.answer(s["support_msg"], parse_mode="HTML")

@dp.message(F.text.in_([LOCALIZED_STRINGS["uz"]["menu_gallery"], LOCALIZED_STRINGS["ru"]["menu_gallery"], LOCALIZED_STRINGS["en"]["menu_gallery"]]))
async def menu_gallery(message: types.Message):
    """Handle Gallery button from menu"""
    await cmd_gallery(message)

@dp.message(F.text.in_([LOCALIZED_STRINGS["uz"]["menu_buy"], LOCALIZED_STRINGS["ru"]["menu_buy"], LOCALIZED_STRINGS["en"]["menu_buy"]]))
async def menu_buy(message: types.Message):
    """Handle Premium button from menu"""
    await cmd_buy(message)

@dp.message(F.text.in_([LOCALIZED_STRINGS["uz"]["menu_create"], LOCALIZED_STRINGS["ru"]["menu_create"], LOCALIZED_STRINGS["en"]["menu_create"]]))
async def menu_create_image(message: types.Message, state: FSMContext):
    """Ask user for creation method"""
    s = get_strings(message.from_user.id)
    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=s["method_ref"], callback_data="method_ref")],
            [InlineKeyboardButton(text=s["method_idea"], callback_data="method_idea")]
        ]
    )
    await message.answer(s["choose_method"], reply_markup=markup)

@dp.callback_query(F.data == "method_ref")
async def cb_method_ref(callback: types.CallbackQuery, state: FSMContext):
    """Handle Reference Photo choice"""
    user_id = callback.from_user.id
    s = get_strings(user_id)
    
    if not is_premium(user_id):
        await callback.answer(s["vision_premium"], show_alert=True)
        return
        
    await state.set_state(ImageStates.entering_reference)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=s["welcome"])]], 
        resize_keyboard=True
    )
    await callback.message.answer(s["ref_req"], reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "method_idea")
async def cb_method_idea(callback: types.CallbackQuery, state: FSMContext):
    """Handle Idea/Prompt choice"""
    user_id = callback.from_user.id
    s = get_strings(user_id)
    
    await state.set_state(ImageStates.entering_prompt)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=s["idea_button"])], [KeyboardButton(text=s["welcome"])]], 
        resize_keyboard=True
    )
    await callback.message.answer(s["prompt_request"], reply_markup=keyboard)
    await callback.answer()



@dp.message(ImageStates.entering_prompt, F.text.in_([LOCALIZED_STRINGS["uz"]["idea_button"], LOCALIZED_STRINGS["ru"]["idea_button"], LOCALIZED_STRINGS["en"]["idea_button"]]))
async def process_idea_click(message: types.Message, state: FSMContext):
    """Handle Idea button click"""
    s = get_strings(message.from_user.id)
    await state.set_state(ImageStates.entering_idea)
    await message.answer(s["idea_request"])

@dp.message(ImageStates.entering_idea)
async def process_idea_description(message: types.Message, state: FSMContext):
    """Generate an upgraded prompt from user's idea"""
    s = get_strings(message.from_user.id)
    user_idea = message.text
    
    status_msg = await message.answer(s["thinking"], parse_mode="HTML")
    
    try:
        import re as _re
        # Detect text/letters the user wants in the image
        text_in_image = _re.findall(r'["\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a]([^"\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a]{1,60})["\u2018\u2019\u201c\u201d\u00ab\u00bb\u2039\u203a]', user_idea)
        keyword_text = _re.findall(r'(?:spell(?:s)?|text|letters?|reads?|says?|written|sign(?:s)?)[^a-zA-Z]*["\u201c\u201d]?([A-Z][A-Z\s]{1,40})["\u201c\u201d]?', user_idea)
        all_texts = list(dict.fromkeys(text_in_image + keyword_text))
        text_hint = ""
        if all_texts:
            quoted = ", ".join([f'"{t.strip()}"' for t in all_texts])
            text_hint = (
                f"CRITICAL TEXT RULE: The image MUST contain this exact readable text: {quoted}. "
                f"Every single letter must be sharp, well-formed, legible and correctly spelled. "
                f"Repeat the exact text twice more in the prompt to reinforce it: "
                f"'the text clearly reads {quoted}' and 'letters spell {quoted} with perfect accuracy'."
            )

        enhancer_prompt = (
            f"You are a world-class cinematic prompt engineer for Flux image generation.\n"
            f"The user described their idea in simple words: '{user_idea}'.\n\n"
            f"Your task is to transform this into a breathtaking, richly detailed image generation prompt by following these steps:\n"
            f"1. SUBJECT & SCENE: Identify the core subject. Describe it with hyper-specific visual detail — materials, textures, colors, proportions.\n"
            f"2. ART STYLE: Choose or infer the best art style (e.g. Studio Ghibli, Hyperrealistic, Lo-Fi Digital Illustration, Cinematic Photography, Oil Painting, Anime). State it clearly.\n"
            f"3. LIGHTING: Describe the exact lighting — golden hour glow, soft volumetric rays, warm desk lamp, moonlight, neon glow, diffused sunlight, etc.\n"
            f"4. ATMOSPHERE & MOOD: Describe the emotional feel — peaceful, epic, cozy, nostalgic, tense, dreamy, majestic.\n"
            f"5. COMPOSITION: Specify shot type — cinematic wide shot, medium eye-level, low angle hero shot, bird's eye, rule of thirds.\n"
            f"6. BACKGROUND & ENVIRONMENT: Describe weather, time of day, location, depth of field on background.\n"
            f"7. TECHNICAL QUALITY TAGS: End with: ultra-detailed, 8K resolution, sharp focus, vibrant color palette, hyper-realistic textures, award-winning composition, masterpiece.\n"
            f"8. INTEGRITY: Only include elements the user mentioned. Never add people, objects or scenes they didn't request.\n"
            f"9. FACIALS: If a person is present — realistic skin texture, expressive eyes, no distortion, natural proportions.\n"
            f"{text_hint}\n\n"
            f"Output ONLY the final enhanced prompt as one richly-worded paragraph. No JSON, no lists, no code blocks, no explanations."
        )
        res = ai_model.generate_content(enhancer_prompt)
        upgraded_prompt = res.text.strip()
        
        # Clean up in case model still outputs JSON
        if upgraded_prompt.startswith("{") and "action_input" in upgraded_prompt:
            try:
                import json
                parsed = json.loads(upgraded_prompt)
                upgraded_prompt = parsed.get("action_input", {}).get("prompt", upgraded_prompt)
                if isinstance(upgraded_prompt, dict): upgraded_prompt = upgraded_prompt.get("prompt", str(upgraded_prompt))
            except: pass
        
        # Remove markdown code blocks if any
        upgraded_prompt = upgraded_prompt.replace("```json", "").replace("```", "").strip()
        
        await state.update_data(current_prompt=upgraded_prompt)
        
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=s["send_to_bot"], callback_data="confirm_gen")]]
        )
        
        await status_msg.delete()
        safe_upgraded = upgraded_prompt.replace("_", "\\_").replace("*", "\\*")
        await message.answer(f"{s['refined_vision']}\n\n<i>{safe_upgraded}</i>", parse_mode="HTML", reply_markup=markup)
    except ResourceExhausted:
        logging.error("Gemini Quota Exceeded")
        await status_msg.edit_text("✨ <b>Concierge Notice:</b> Our digital atelier is currently operating at full capacity. Please allow a few moments before your next request.", parse_mode="HTML")
    except Exception as e:
        logging.error(f"Error in idea generation: {e}")
        await status_msg.edit_text(s["error"])

@dp.callback_query(F.data == "confirm_gen")
async def process_confirm_gen(callback: types.CallbackQuery, state: FSMContext):
    """Handle 'Send to Bot!' button"""
    data = await state.get_data()
    prompt = data.get("current_prompt")
    
    if not prompt:
        await callback.answer("Session expired. Please try again.")
        return
        
    await callback.message.delete()
    await state.clear()
    await run_image_generation(callback.message, prompt, user=callback.from_user)
    await callback.answer()

@dp.message(ImageStates.entering_prompt)
async def process_direct_prompt(message: types.Message, state: FSMContext):
    """Handle direct prompt input while in entering_prompt state"""
    if message.text in [LOCALIZED_STRINGS["uz"]["welcome"], LOCALIZED_STRINGS["ru"]["welcome"], LOCALIZED_STRINGS["en"]["welcome"]]:
        await state.clear()
        await message.answer("Returning to main menu.", reply_markup=get_main_menu(message.from_user.id))
        return
        
    prompt = message.text
    await state.clear()
    await run_image_generation(message, prompt)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Admin command to view user statistics"""
    if message.from_user.id != ADMIN_ID:
        return
        
    try:
        from database import get_conn
        conn = get_conn()
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM users WHERE is_premium = true")
        premium_users = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM generations")
        total_gens = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        stats_text = (
            "📊 <b>LuxePrompt AI Statistics</b>\n\n"
            f"👥 Total Users: <code>{total_users}</code>\n"
            f"💎 Premium Users: <code>{premium_users}</code>\n"
            f"🎨 Total Generations: <code>{total_gens}</code>\n"
        )
        await message.answer(stats_text, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Error fetching stats: {e}")

@dp.message(Command("setpremium"))
async def cmd_set_premium(message: types.Message):
    """Admin command to manually set premium for a user"""
    if message.from_user.id != ADMIN_ID:
        return
        
    try:
        parts = message.text.split()
        if len(parts) < 2:
            await message.answer("Usage: <code>/setpremium &lt;user_id&gt;</code>", parse_mode="HTML")
            return
            
        target_id = int(parts[1])
        set_premium(target_id, True)
        await message.answer(f"✅ User <code>{target_id}</code> has been elevated to Premium status.", parse_mode="HTML")
        
        # Notify the user
        try:
            await bot.send_message(target_id, "💎 <b>Premium Activated:</b> Your account has been manually upgraded by the administrator. Welcome to LuxePrompt AI!", parse_mode="HTML")
        except: pass
    except Exception as e:
        await message.answer(f"Error: {e}")

@dp.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """Confirm the checkout query"""
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: types.Message):
    """Handle successful automated payment"""
    user_id = message.from_user.id
    set_premium(user_id, True)
    s = get_strings(user_id)
    await message.answer("💎 <b>Payment Confirmed!</b> Welcome to the elite tier of LuxePrompt AI. Your premium status has been activated.", parse_mode="HTML")

@dp.message(F.text)
async def handle_text(message: types.Message):
    """Handle general AI text (should be defined LAST)"""
    user_id = message.from_user.id
    add_user(user_id, message.from_user.full_name, message.from_user.username)
    
    try:
        lang_name = {"uz": "Uzbek", "ru": "Russian", "en": "English"}.get(get_user_language(user_id), "English")
        full_prompt = f"Please respond in {lang_name} language: {message.text}"
        
        response = ai_model.generate_content(full_prompt)
        await message.answer(response.text)
    except ResourceExhausted:
        logging.error("Gemini Quota Exceeded")
        await message.answer("✨ <b>Concierge Notice:</b> Our digital atelier is currently operating at full capacity. Please allow a few moments before trying again or use /start to refresh.")
    except Exception as e:
        logging.error(f"Error generating text: {e}")
        s = get_strings(user_id)
        await message.answer(s["error"])

async def main():
    """Bot Entrypoint"""
    init_db()
    print("Modern Luxury AI Bot Initialized.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
