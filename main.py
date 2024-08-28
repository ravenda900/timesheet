import requests
import json
import datetime
import calendar
from requests.auth import HTTPBasicAuth
from logging.handlers import RotatingFileHandler
import logging

# importing os module for environment variables
import os
# importing necessary functions from dotenv library
from dotenv import load_dotenv, dotenv_values

# loading variables from .env file
load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

# Set up rotating log file
handler = RotatingFileHandler("timesheet_entry.log", maxBytes=2000, backupCount=5)  # maxBytes is the size threshold, backupCount is the number of backup files
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


def create_timesheet_entry():
    (holidays, user_key) = get_holidays()

    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")

    found = False
    for holiday in holidays:
        if holiday["date"] == date:
            found = holiday
            break

    # do not create a timesheet entry if the current day is a holiday
    if found:
        logging.info(f"Holiday found in {date}: {found['name']}. Skipping creation of timesheet entry...")
        return

    api_url = "https://issues.mycollab.co/rest/com.easesolutions.jira.plugins.timesheet/latest/timesheet/workspace"
    payload = {
        "wsId": None,
        "date": date,
        "workStart": "10:00",
        "workEnd": "19:00",
        "workPause": 60,
        "comment": "",
        "endIsNextDay": False,
        "submitStatus": 0,
        "items": [{
            "issueId": "205031",
            "workingTime": 480,
            "comment": ""
        }],
        "userKey": user_key
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(api_url, data=json.dumps(payload), headers=headers, auth=HTTPBasicAuth(EMAIL, PASSWORD))

    # Check if the request was successful
    if response.status_code == 200:
        logging.info(f"Successfully created a timesheet entry for {date}...")
    else:
        logging.error(f"Failed to create a timesheet entry for {date}...")
        logging.debug(f"Status code: {response.status_code}")
        logging.debug(f"Response: {response.text}")


def get_first_and_last_day_of_the_month():
    # Get the current date
    today = datetime.date.today()

    # Get the first day of the current month
    first_day_of_month = today.replace(day=1)

    # Get the last day of the current month
    last_day_of_month = today.replace(day=calendar.monthrange(today.year, today.month)[1])

    return first_day_of_month, last_day_of_month

def get_myself():
    api_url = f"https://issues.mycollab.co/rest/api/2/myself"
    response = requests.get(api_url, auth=HTTPBasicAuth(EMAIL, PASSWORD))

    # Check if the request was successful
    if response.status_code == 200:
        logging.info(f"Successfully retrieved current user info...")
        return response.json()
    else:
        logging.info(f"Failed to retrieve current user info...")
        logging.debug(f"Status code: {response.status_code}")
        logging.debug(f"Response: {response.text}")


def get_holidays():
    user_key = get_myself()["key"]
    (first_day, last_day) = get_first_and_last_day_of_the_month()
    logging.info(f"Retrieving list of holidays for {first_day} - {last_day} date range")
    api_url = f"https://issues.mycollab.co/rest/com.easesolutions.jira.plugins.timesheet/latest/timesheet/holidays" \
              f"/{user_key}/{first_day}/{last_day}"
    response = requests.get(api_url, auth=HTTPBasicAuth(EMAIL, PASSWORD))

    # Check if the request was successful
    if response.status_code == 200:
        logging.info(f"Successfully retrieved holidays for {first_day} - {last_day} date range...")
        return response.json(), user_key
    else:
        logging.info(f"Failed to retrieve holidays for {first_day} - {last_day} date range...")
        logging.debug(f"Status code: {response.status_code}")
        logging.debug(f"Response: {response.text}")


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    create_timesheet_entry()
