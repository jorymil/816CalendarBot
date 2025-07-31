from pprint import pprint
import re
import requests
import json

from calendar_bot.config import *
from calendar_bot.slack import send_message

def get_question_section(question, notify_channel):
    message_text = f"<!channel> *{question}*" if notify_channel else f"*{question}*"

    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": message_text
        }
    }

EMOJI_LIST = [":one:", ":two:", ":three:", ":four:", ":five:", ":six:", ":seven:", ":eight:", ":nine:"]

def get_option_section(option, option_index):
    if option_index < 0 or option_index >= len(EMOJI_LIST):
        raise Exception("There must be at most nine options")
    
    option_emoji = EMOJI_LIST[option_index]

    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"{option_emoji} {option}    `0`\n"
        },
        "accessory": {
            "type": "button",
            "text": {
                "type": "plain_text",
                "text": option_emoji,
                "emoji": True
            },
            "value": f"{option_index}",
            "action_id": f"option-select"
        }
    }

def get_num_respondents():
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*Respondents:* `0`\n"
        }
    }


def create_poll(question, options, notify_channel=False):
    if not options:
        raise Exception("There must be at least one option")

    blocks = []

    if question and question.strip():
        blocks.append(get_question_section(question, notify_channel))

    for option_index, option in enumerate(options):
        blocks.append(get_option_section(option, option_index))

    blocks.append(get_num_respondents())

    send_message(
        '#bot-tester', 
        message=blocks, 
        use_blocks=True, 
        fallback_text=f"Poll: {question}")
    

# update poll option section by either adding or removing user from section
def update_response(blocks, user_id, option_index: int):
    block_to_update = blocks[option_index + 1] # plus one due to question block

    text_split = block_to_update['text']['text'].splitlines()

    prefix_text = text_split[0]
    user_list_raw = text_split[1] if len(text_split) > 1 else ''

    # get all user ids who have selected this option
    user_ids = [s.replace('<@', '').replace('>', '') for s in re.findall(r'<@[A-Z0-9]+>', user_list_raw)]

    # check if current user has not responded
    should_add_user = not user_id in user_ids

    if should_add_user:
        user_ids.append(user_id)
    else:
        user_ids.remove(user_id)

    # update the number of users who have selected this option
    prefix_text_split = prefix_text.split('`')
    prefix_text_split[-2] = f"{len(user_ids)}"
    prefix_text = '`'.join(prefix_text_split)

    # format user ids into a string slack understands 
    formatted_user_ids = [f"<@{id}>" for id in user_ids]

    block_to_update['text']['text'] = f"{prefix_text}\n{', '.join(formatted_user_ids)}\n"
    

    
# updates the last section that contains the total number of unique users who have responded to the poll
def update_num_responses(blocks):
    # get all the user ids who have responded
    user_ids = [s.replace('<@', '').replace('>', '') for s in re.findall(r'<@[A-Z0-9]+>', str(blocks))]

    num_unique_users = len(set(user_ids))

    last_block = blocks[-1]

    block_text = last_block['text']['text']
    # update number in text
    block_text_split = block_text.split('`')
    block_text_split[-2] = f"{num_unique_users}"
    block_text = '`'.join(block_text_split)

    last_block['text']['text'] = block_text


def update_poll(body_json):
    # id of user who pressed button
    user_id = body_json['user']['id']

    # old message to be updated
    blocks = body_json['message']['blocks']

    # list of actions the user took
    actions = body_json['actions']

    for action in actions:
        option_index = int(action['value'])
        # add or remove them from an option
        update_response(blocks, user_id, option_index)

    # update total number of unique users who have responded    
    update_num_responses(blocks)

    data = {
        "replace_original": "true",
        "blocks": blocks
    }

    headers = {
        'Content-type': 'application/json'
    }

    response_url = body_json['response_url']

    # update the poll message with the new body
    response = requests.post(response_url, data=json.dumps(data), headers=headers)

    if response.status_code == 200:
        print("Update message successful")
    else:
        print(f"Update message failed {response}")
