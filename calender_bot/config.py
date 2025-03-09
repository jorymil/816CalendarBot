import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional

# do not change (for internal use of the program to map numbers to days)
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_config_from_environment(key_name, default=None):
    value = os.getenv(key_name)
    if value == None:
        if default != None:
            return default
        raise Exception(f"Environment Variable {key_name} is required")

    return value

@dataclass
class MessageConfig:
    days: List[str]
    days_before: int
    notify_channel: bool
    volunteer_threshold: int = 4
    channel: str = "#bot-tester"
    notify_keyholders: bool = False
    keyholder_marks: List[str] = field(default_factory=lambda: ["🔑"])
    bikeschool_marks: List[str] = field(default_factory=lambda: ["skool", "school"])
    

    def get_keyholder_marks_list(self):
        if len(self.keyholder_marks) < 2:
            return self.keyholder_marks[0]
        
        # Join all but the last element with commas
        comma_separated = ", ".join(self.keyholder_marks[:-1])

        # Add "and" before the last element
        return f"{comma_separated} or {self.keyholder_marks[-1]}"


@dataclass
class Config:
    shift_warning: List[MessageConfig]
    shift_notes: List[MessageConfig]
    bike_school_reminder: List[MessageConfig]

def get_config() -> Config:
    with open("./calender_bot/config.json", "r") as file:
        raw_config = os.getenv("calender_bot_config")
        data_dict = None
        if raw_config:
            data_dict = json.loads(raw_config)
        else:
            data_dict = json.load(file)

        shift_warning = [MessageConfig(**msg_config) for msg_config in data_dict['shift_warning']]
        shift_notes = [MessageConfig(**msg_config) for msg_config in data_dict['shift_notes']]
        bike_school_reminder = [MessageConfig(**msg_config) for msg_config in data_dict['bike_school_reminder']]

        return Config(shift_warning=shift_warning, shift_notes=shift_notes, bike_school_reminder=bike_school_reminder)
    raise Exception("Failed to open file and get config")

# Can find in the URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/
SHEET_ID = get_config_from_environment('SHEET_ID')
# must be of the form https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
SHEET_URL=f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
