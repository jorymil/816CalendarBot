import os
import requests
from dateutil.parser import parse
from datetime import date, timedelta
from typing import Callable

from calender_bot.slack import send_volunteer_warning_message, send_special_note_message, send_bike_school_message, send_message
from calender_bot.config import * # yeah this is kinda awful but I don't feel like improving it with a real config file

## shamelessly stolen from gspread
def rowcol_to_a1(row: int, col: int) -> str:
    """Translates a row and column cell address to A1 notation.

    :param row: The row of the cell to be converted.
        Rows start at index 1.
    :type row: int, str

    :param col: The column of the cell to be converted.
        Columns start at index 1.
    :type row: int, str

    :returns: a string containing the cell's coordinates in A1 notation.

    Example:

    >>> rowcol_to_a1(1, 1)
    A1

    """

    div = col
    column_label = ""

    while div:
        (div, mod) = divmod(div, 26)
        if mod == 0:
            mod = 26
            div -= 1
        column_label = chr(mod + 64) + column_label

    label = "{}{}".format(column_label, row)

    return label

# returns sheet map that has an index of 0
def get_default_sheet(sheets):
    for sheet in sheets:
        if sheet['properties']['index'] == 0:
            return sheet
        
    return None

# returns the range of all the sheets values in A1 format
def get_entire_sheet_range(num_rows, num_cols):
    return f"A1:{rowcol_to_a1(num_rows, num_cols)}"

# returns true if the cells background color rgb channels are all the same
# false otherwise
def get_cell_is_gray(cell):
    effectiveFormat = cell["effectiveFormat"] if "effectiveFormat" in cell else None
    backgroundColor = effectiveFormat["backgroundColor"] if effectiveFormat is not None and "backgroundColor" in effectiveFormat else None
    if backgroundColor is not None:
        # does not always seem to have all three color channels :(
        red = backgroundColor['red'] if 'red' in backgroundColor else None
        green = backgroundColor['green'] if 'green' in backgroundColor else None
        blue = backgroundColor['blue'] if 'blue' in backgroundColor else None
        if red == green and green == blue:
            return True
        else:
            return False

    return True

# returns true if the cell is a date, false otherwise
def get_cell_is_date(cell):
    try:
        if cell['effectiveFormat']['numberFormat']['type'] == 'DATE':
            return True
    except Exception:
        pass # yeah this is lazy but it works
    return False

# returns true if the text of a cell is striked through, false otherwise
def get_cell_is_strkethrough(cell):
    try:
        if cell['effectiveFormat']['textFormat']['strikethrough'] == True:
            return True
    except Exception:
        pass # yeah this is lazy but it works
    return False

def get_sheet_data(api_key, sheet_id):
    base_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    key_param = f"key={api_key}"
    # what fields to return from the api
    field_mask = "fields=sheets.properties(index,gridProperties(rowCount,columnCount))"
    r = requests.get(f"{base_url}?{key_param}&{field_mask}")

    sheets = r.json()['sheets']
    default_sheet = get_default_sheet(sheets)

    num_rows = default_sheet['properties']['gridProperties']['rowCount']
    num_cols = default_sheet['properties']['gridProperties']['columnCount']
    sheet_range = get_entire_sheet_range(num_rows, num_cols)

    # what fields to return from the third api call
    field_mask = "fields=sheets.data.rowData.values(effectiveFormat(numberFormat,backgroundColor,textFormat.strikethrough),formattedValue)"
    r = requests.get(f"{base_url}?{key_param}&ranges={sheet_range}&{field_mask}")

    row_data = r.json()['sheets'][0]['data'][0]['rowData']

    data = []

    for row in row_data:
        new_row = []

        for cell in row['values']:
            is_gray = get_cell_is_gray(cell)
            is_date = get_cell_is_date(cell)
            is_strikethrough = get_cell_is_strkethrough(cell)
            value = cell['formattedValue'] if 'formattedValue' in cell else ''

            new_row.append({"is_gray": is_gray, "is_date": is_date, "is_strikethrough": is_strikethrough, "value": value})

        data.append(new_row)

    return data


def convert_dates(all_cells):
    for row in range(len(all_cells)):
        for col in range(len(all_cells[row])):
            if all_cells[row][col]["is_date"] and len(all_cells[row][col]["value"]) > 0:
                all_cells[row][col]["value"] = parse(all_cells[row][col]["value"]).date()

def get_date_location(date, all_cells):
    """
    Finds the row and column of the given date in the given cells using 0 based indexing
    Throws an error if the date is not found

    """
    for row_idx, row in enumerate(all_cells):
        for col_idx, cell in enumerate(row):
            if cell['value'] == date:
                return row_idx, col_idx  # Return the first occurrence
    raise ValueError(f"Date: {date} not found in the calender")

def get_voluneers_for_date(date, all_cells):
    """
    Returns a tuple of two elements. The first is the list of volunteers for the shift. The second
    Is the list of special cells, like new volunteer that the shift may need to know about
    """
    # find the location of the given date in the worksheet
    row, col = get_date_location(date, all_cells)

    # increment the row by one to go one cell under the date
    row = row + 1

    all_volunteers = []
    special_rows = []

    # go down each row until the next date is reached or the end of the sheet is reached
    while type(all_cells[row][col]['value']) is str and row < len(all_cells):
        cell = all_cells[row][col]

        # check if the cell is special or contains volunteer signup info
        if not cell['is_gray']:
            special_rows.append(cell['value'])
        elif not cell['is_strikethrough']:
            # get volunteers names. The cell may contain multiple volunteers sigining up separated
            # by commas so split by commas and then remove any leading/trailing whitespace before
            # adding the volunteers to the volunteers list
            all_volunteers.extend(item.strip() for item in cell['value'].split(","))

        # go down to the next cell
        row = row + 1

    # remove any possibly blank cells
    all_volunteers = [volunteer for volunteer in all_volunteers if volunteer.strip() not in (None, '')]
    special_rows = [special_row for special_row in special_rows if special_row.strip() not in (None, '')]

    return all_volunteers, special_rows

def get_has_keyholder(volunteers, config: MessageConfig):
    return any(keyholder_mark in volunteer.lower() for keyholder_mark in config.keyholder_marks for volunteer in volunteers)

def send_shift_warning_messages(config: MessageConfig, all_cells, today: date):
    date_to_check = today + timedelta(days=config.days_before)
    day_of_week = DAYS_OF_WEEK[date_to_check.weekday()]
    
    if day_of_week in config.days:
        volunteers, _ = get_voluneers_for_date(date_to_check, all_cells)
        has_keyholder = get_has_keyholder(volunteers, config)

        if len(volunteers) < config.volunteer_threshold or not has_keyholder:
            send_volunteer_warning_message(config, day_of_week, date_to_check, volunteers, has_keyholder)

def send_shift_notes_messages(config: MessageConfig, all_cells, today: date):
    date_to_check = today + timedelta(days=config.days_before)
    day_of_week = DAYS_OF_WEEK[date_to_check.weekday()]

    if day_of_week in config.days:
        _, special_cells = get_voluneers_for_date(date_to_check, all_cells)

        if special_cells:
            send_special_note_message(config, day_of_week, date_to_check, special_cells)


def is_bike_school(special_cells, config: MessageConfig):
    """checks if any of the given special cells contains any of the marks of a bike school event"""
    lower_special_cells = set([cell.lower() for cell in special_cells])
    lower_school_marks = [mark.lower() for mark in config.bikeschool_marks]

    for cell in lower_special_cells:
        for mark in lower_school_marks:
            if mark in cell:
                return True
    return False

def send_bike_school_reminder_messages(config: MessageConfig, all_cells, today: date):
    """Sends a bike school reminder based on the message config"""
    date_to_check = today + timedelta(days=config.days_before)
    day_of_week = DAYS_OF_WEEK[date_to_check.weekday()]

    if day_of_week in config.days:
        _, special_cells = get_voluneers_for_date(date_to_check, all_cells)

        if is_bike_school(special_cells, config):
            send_bike_school_message(config, day_of_week, date_to_check, special_cells)

        

def send_messages_of_type(message_configs: MessageConfig, message_sender: Callable, all_cells, today: date):
    """For each configured message in the message type, check if a message needs to be sent (and send it if needed)"""
    for message_config in message_configs:
        message_sender(message_config, all_cells, today)

def send_slack_messages(today = date.today()):
    google_api_key = os.getenv('google_api_key')

    # get the entire sheet as a 2D array
    all_cells = get_sheet_data(google_api_key, SHEET_ID)

    # # converts any strings that are dates into date objects
    # # if a cell is not a date, leave as is
    convert_dates(all_cells)

    config = get_config()

    # send a message of each message type based on config for those message types
    send_messages_of_type(config.shift_warning, send_shift_warning_messages, all_cells, today)
    send_messages_of_type(config.shift_notes, send_shift_notes_messages, all_cells, today)
    send_messages_of_type(config.bike_school_reminder, send_bike_school_reminder_messages, all_cells, today)
