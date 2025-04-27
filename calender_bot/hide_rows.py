import os
import requests
from dateutil.parser import parse
from datetime import date, timedelta
from typing import Callable
from pprint import pprint, pformat
import logging
import httplib2

from apiclient import discovery
from google.oauth2 import service_account

from calender_bot.calender_bot import get_default_sheet, get_entire_sheet_range, get_cell_is_date
from calender_bot.config import *



def get_sheet_data(api_key, sheet_id):
    base_url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    key_param = f"key={api_key}"
    # what fields to return from the api
    field_mask = "fields=sheets.properties(index,sheetId,gridProperties(rowCount,columnCount,frozenRowCount))"
    r = requests.get(f"{base_url}?{key_param}&{field_mask}")

    sheets = r.json()['sheets']
    default_sheet = get_default_sheet(sheets)

    num_rows = default_sheet['properties']['gridProperties']['rowCount']
    num_cols = default_sheet['properties']['gridProperties']['columnCount']
    sheet_range = get_entire_sheet_range(num_rows, num_cols)

    # what fields to return from the third api call
    field_mask = "fields=sheets.data(rowMetadata.hiddenByUser,rowData.values(effectiveFormat(numberFormat,backgroundColor),formattedValue))"
    r = requests.get(f"{base_url}?{key_param}&ranges={sheet_range}&{field_mask}")

    response = r.json()

    with open('output.txt', 'w') as f:
        f.write(str(pformat(response)))

    row_data = response['sheets'][0]['data'][0]['rowData']
    row_metadata = response['sheets'][0]['data'][0]['rowMetadata']

    data = []

    for index, row in enumerate(row_data):
        ## TODO GET is CELL hidden
        is_row_hidden = row_metadata[index]['hiddenByUser'] if 'hiddenByUser' in row_metadata[index] else False

        new_row = {"hidden": is_row_hidden, "cells": []}

        for cell in row['values']:
            is_date = get_cell_is_date(cell)
            value = cell['formattedValue'] if 'formattedValue' in cell else ''
            if is_date and value:
                # convert value to date
                value = parse(value).date()

            new_row['cells'].append({"is_date": is_date, "value": value})

        data.append(new_row)

    return default_sheet, data

def get_date_location(date, data):
    """
    Finds the row and column of the given date in the given cells using 0 based indexing
    Throws an error if the date is not found
    """
    for row_idx, row in enumerate(data):
        for col_idx, cell in enumerate(row['cells']):
            if cell['value'] == date:
                return row_idx, col_idx  # Return the first occurrence
    raise ValueError(f"Date: {date} not found in the calender")

def get_first_non_hidden_row(data, frozen_row_count):
    for row_index, row in enumerate(data):
        # return first row that is not hidden and is not frozen (pinned)
        if not row['hidden'] and row_index >= frozen_row_count:
            return row_index

    return len(data)

def do_hide_rows_api_call(credentials, spreadsheet_id, sheet_id, start_row, end_row):
    """
    Hides the given range of rows [start_row, end_row) (inclusive on start, exclusive on end)
    rows are specified using zero based indexing
    """
    service = discovery.build('sheets', 'v4', credentials=credentials)

    # url = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate?key={api_key}"

    body = {
        "requests": [{
            "updateDimensionProperties": {
                "properties": {
                    "hiddenByUser": True
                },
                "fields": "hiddenByUser",
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start_row,
                    "endIndex": end_row,
                }
            }
        }],
        "includeSpreadsheetInResponse": False,
    }

    r = service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id,
        body=body
    ).execute()

    print(r)



def hide_rows(today = date.today()):
    print("hiding rows")
    google_api_key = os.getenv('google_api_key')

    # COPY SHEET
    SHEET_ID = "1b3T18ioa4aaM3H8qk45C-KCpIUS4pN_UhBokh_b8XYg"

    default_sheet, data = get_sheet_data(google_api_key, SHEET_ID)

    today_row_index, _ = get_date_location(today, data)

    frozen_row_count = default_sheet['properties']['gridProperties']['frozenRowCount']
    first_non_hidden_row_index = get_first_non_hidden_row(data, frozen_row_count)

    print(first_non_hidden_row_index, today_row_index)

    scopes = ["https://www.googleapis.com/auth/drive", "https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/spreadsheets"]
    google_service_account_private_key = json.loads(os.getenv('google_service_account'))

    credentials = service_account.Credentials.from_service_account_info(google_service_account_private_key, scopes=scopes)

    default_sheet_id = default_sheet['properties']['sheetId']
    # SHEET_ID is technically the spreadsheet id, and default_sheet_id is the actual sheet id to modify
    do_hide_rows_api_call(credentials, SHEET_ID, default_sheet_id, first_non_hidden_row_index, today_row_index)