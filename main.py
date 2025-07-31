from datetime import date, timedelta

from calendar_bot.calendar_bot import send_slack_messages


if __name__ == "__main__":
    today = date.today() + timedelta(days=14)
    print(today)
    send_slack_messages(today=today)