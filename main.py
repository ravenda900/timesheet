import requests
import json
from datetime import datetime
from requests.auth import HTTPBasicAuth

# importing os module for environment variables
import os
# importing necessary functions from dotenv library
from dotenv import load_dotenv, dotenv_values

# loading variables from .env file
load_dotenv()


def create_timesheet_entry():
    username = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
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
        "userKey": username
    }
    headers = {"Content-Type": "application/json"}

    response = requests.post(api_url, data=json.dumps(payload), headers=headers, auth=HTTPBasicAuth(username, password))

    # Check if the request was successful
    if response.status_code == 200:
        print("Request was successful")
        print("Response:", response.json())
    else:
        print("Failed to send request")
        print("Status code:", response.status_code)
        print("Response:", response.text)


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    create_timesheet_entry()

