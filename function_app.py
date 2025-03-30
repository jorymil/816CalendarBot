import azure.functions as func
import logging
from datetime import date, timedelta
import urllib.parse
import json

from calender_bot.calender_bot import send_slack_messages
from calender_bot.slack_poll import create_poll, update_poll

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.timer_trigger(schedule="0 0 15 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False) 
def calender_bot(myTimer: func.TimerRequest) -> None:
    logging.info('Python timer trigger function executed.')
    send_slack_messages()


@app.route(route="http_trigger_bot", auth_level=func.AuthLevel.ANONYMOUS)
def http_trigger_bot(req: func.HttpRequest) -> func.HttpResponse:
    """Function for testing purposes only. Used to debug and force runs on different days"""
    logging.info('Python HTTP trigger function processed a request.')

    delta = req.params.get('delta')

    if delta:
        today = date.today() + timedelta(days=int(delta))
        logging.info(today)
        send_slack_messages(today=today)
        return func.HttpResponse(f"Hello. Sending as if today was {today}")
    else:
        send_slack_messages()

    return func.HttpResponse(f"Hello. Sending as if today was today")

@app.route(route="create_poll", auth_level=func.AuthLevel.ANONYMOUS)
def create_poll_test(req: func.HttpRequest) -> func.HttpResponse:
    """Function for testing purposed only. Used to manually create a poll"""
    create_poll("test question", ["Yes", "No", "I can bring food"], notify_channel=True)

    return func.HttpResponse(f"End of function")

@app.route(route="handle_interaction", auth_level=func.AuthLevel.ANONYMOUS)
def handle_interaction(req: func.HttpRequest) -> func.HttpResponse:
    body = urllib.parse.unquote_plus(req.get_body().decode("utf-8"))

    body_json = json.loads(body[len("payload="):])

    update_poll(body_json)

    return func.HttpResponse(body="", status_code=200)