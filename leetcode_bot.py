
# 7768504324:AAER6bx9OA24hxYBK-QlbZJdc1hltyZTYXc
import logging
import datetime
import pytz
import json
import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue
import requests

# Боттың логын баптау
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Файл атауы
USER_STATUS_FILE = "user_status.json"


# Пайдаланушы күйін сақтау және жүктеу
def load_user_status():
    if os.path.exists(USER_STATUS_FILE):
        with open(USER_STATUS_FILE, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)

                # Егер ескі форматта болса, оны жаңа форматқа түрлендіру
                for chat_id, value in data.items():
                    if "solved_problems" not in value:
                        data[chat_id] = {"solved_problems": [{"title": value["problem"], "solved": value["solved"]}]}

                return data
            except json.JSONDecodeError:
                return {}
    return {}


def save_user_status():
    with open(USER_STATUS_FILE, "w", encoding="utf-8") as file:
        json.dump(user_status, file, indent=4, ensure_ascii=False)


# Жаңа қолданушылардың есебін жүргізу
user_status = load_user_status()


# LeetCode Medium деңгейіндегі есепті алу функциясы (тек премиум емес есептер)
import random

def get_leetcode_medium_problem():
    url = "https://leetcode.com/api/problems/algorithms/"
    response = requests.get(url)
    if response.status_code == 200:
        problems = response.json()['stat_status_pairs']
        medium_problems = [p for p in problems if p['difficulty']['level'] == 2 and not p['paid_only']]

        if medium_problems:
            problem = random.choice(medium_problems)  # Кездейсоқ есеп таңдау
            problem_title = problem['stat']['question__title']
            problem_slug = problem['stat']['question__title_slug']
            problem_url = f"https://leetcode.com/problems/{problem_slug}/"
            return problem_title, problem_url
    return None, None


# Пайдаланушыға есеп жіберу функциясы
async def send_daily_problem(context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(context.job.data)
    problem_title, problem_url = get_leetcode_medium_problem()

    if problem_title and problem_url:
        message = (
            f"🧠 *Бүгінгі LeetCode Medium есеп:*\n\n"
            f"📚 *{problem_title}*\n\n"
            f"🔗 [Есепке өту]({problem_url})\n\n"
            "📝 *Шешіміңізді растауды ұмытпаңыз!* Сәттілік! 🚀"
        )
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='Markdown')

        # Егер пайдаланушы бұрын тіркелмесе немесе тізімі жоқ болса, оны қосу
        if chat_id not in user_status or "solved_problems" not in user_status[chat_id]:
            user_status[chat_id] = {"solved_problems": []}

        # Жаңа есепті тізімге қосу
        user_status[chat_id]["solved_problems"].append({"title": problem_title, "solved": False})
        save_user_status()
    else:
        await context.bot.send_message(chat_id=chat_id, text="LeetCode тегін есептерін табуда қиындықтар болды. Кешіріңіз.")


# Есепті еске түсіру функциясы
async def remind_unsolved_problem(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    user_data = user_status.get(str(chat_id), {})

    if user_data and not user_data.get("solved", True):
        await context.bot.send_message(chat_id=chat_id, text="⏰ *Есепті әлі шығарған жоқсыз!* Көріп шығыңыз.")


# Пайдаланушы есепті шығарғанын растау үшін /done командасы
async def done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)

    # Егер қолданушы бұрын болмаған болса немесе оның тізімі жоқ болса
    if chat_id not in user_status or "solved_problems" not in user_status[chat_id] or not user_status[chat_id]["solved_problems"]:
        await update.message.reply_text("❌ Сізге есеп жіберілмеген немесе ешқандай тапсырма орындалмады.")
        return

    # Соңғы тапсырманы шешілген деп белгілеу
    last_problem = user_status[chat_id]["solved_problems"][-1]
    if not last_problem["solved"]:
        last_problem["solved"] = True
        save_user_status()
        await update.message.reply_text(f"🎉 Жарайсың! '{last_problem['title']}' есебі шығарылды деп белгіленді. 🚀")
    else:
        await update.message.reply_text("✅ Бұл есепті бұрын шығарғансыз.")


# Ботқа START командасын беру
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text("Күн сайын LeetCode Medium есеп жіберіледі.")

    # JobQueue-ға қол жеткізу
    job_queue = context.job_queue

    if job_queue is None:
        await update.message.reply_text("JobQueue қол жетімді емес.")
        return

    # Уақыт белдеуі үшін Almaty +05:00 (300 минут)
    timezone_offset = pytz.FixedOffset(300)

    # Есепті күнделікті 17:31-де жіберу
    job_queue.run_daily(
        send_daily_problem,
        time=datetime.time(hour=9, minute=0, second=0, tzinfo=timezone_offset),
        data=chat_id,
        name=str(chat_id)
    )

    # Еске түсіруді күнде 17:30-да баптау
    job_queue.run_daily(
        remind_unsolved_problem,
        time=datetime.time(hour=17, minute=30, second=0, tzinfo=timezone_offset),
        data=chat_id,
        name=str(chat_id) + '_reminder'
    )


def main():
    # Application құру
    application = ApplicationBuilder().token('7768504324:AAER6bx9OA24hxYBK-QlbZJdc1hltyZTYXc').build()

    # Командалар
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("done", done))

    # JobQueue-ды баптау
    job_queue = JobQueue()
    job_queue.set_application(application)
    job_queue.start()

    # Ботты іске қосу
    application.run_polling()


if __name__ == "__main__":
    main()
