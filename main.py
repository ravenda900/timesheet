import requests
import json
import datetime
import calendar
from requests.auth import HTTPBasicAuth
from logging.handlers import RotatingFileHandler
import logging
import os
from dotenv import load_dotenv
import tkinter as tk
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# MessageBox parameters
MB_OK = 0x0  # OK button only
MB_ICONINFORMATION = 0x40  # Information icon
MB_ICONERROR = 0x10  # Error icon

# loading variables from .env file
load_dotenv()

EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

# Set up rotating log file
handler = RotatingFileHandler("timesheet_entry.log", maxBytes=2000,
                              backupCount=5)  # maxBytes is the size threshold, backupCount is the number of backup files
logging.basicConfig(
    handlers=[handler],
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)


def init():
    user_key = get_myself()["key"]
    now = datetime.datetime.now()
    date = now.strftime("%Y-%m-%d")
    holidays = get_holidays(user_key)
    leaves = get_leaves(user_key)

    show_missing_timesheet_entries(date, user_key, holidays, leaves)
    # create_timesheet_entry(date, user_key, holidays, leaves)


def get_working_days(user_key):
    contract_days = get_contract_days(user_key)

    return [x for x in contract_days if x["isWorkingDay"]]


def show_missing_timesheet_entries(date, user_key, holidays, leaves):
    timesheet_entries = get_timesheet_entries(user_key)
    working_days = get_working_days(user_key)

    past_working_days = []
    for working_day in working_days:
        working_day_date = working_day["date"]
        working_date = datetime.datetime.strptime(working_day_date, "%Y-%m-%d")

        # Convert date to datetime
        check_date = datetime.datetime.strptime(date, "%Y-%m-%d")

        # Check if the date is in the past and not a holiday nor a leave
        if working_date <= check_date and not is_holiday(working_day_date, holidays) and not is_on_leave(
                working_day_date, leaves):
            past_working_days.append(working_day_date)

    missing_timesheet_entries = []
    for past_working_day in past_working_days:
        # Check if a timesheet entry exists for this working day
        for timesheet_entry in timesheet_entries:
            timesheet_entry_date_timestamp = timesheet_entry["date"] / 1000
            timesheet_entry_date_obj = datetime.datetime.fromtimestamp(timesheet_entry_date_timestamp)
            timesheet_entry_date = timesheet_entry_date_obj.strftime("%Y-%m-%d")
            if timesheet_entry_date == past_working_day:
                # Remove the found entry to optimize subsequent searches
                timesheet_entries.remove(timesheet_entry)
                break
        else:
            # If no matching entry was found, add to missing list
            missing_timesheet_entries.append(past_working_day)

    # we will not show the dialog if there are no missing entries
    if len(missing_timesheet_entries) == 0:
        return

    title = "Missing Timesheet Entries"
    text = f"You have {len(missing_timesheet_entries)} missing timesheet entries..."
    details = "\n".join([f"No timesheet entry found in {x}" for x in missing_timesheet_entries])

    send_email(text, details)
    create_dialog(title, text, details, user_key, holidays, leaves, missing_timesheet_entries)


def create_timesheet_entry(date, user_key, holidays, leaves):
    # do not create a timesheet entry if the current day is a holiday
    if is_holiday(date, holidays) or is_on_leave(date, leaves):
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


def is_holiday(date, holidays):
    found = False
    for holiday in holidays:
        if holiday["date"] == date:
            found = holiday
            break

    if found:
        logging.info(f"Holiday found in {date}: {found['name']}. Skipping creation of timesheet entry...")

    return found


def is_on_leave(date, leaves):
    found = False
    for leave in leaves:
        if leave["status"]["name"] != "Approved" or leave["status"]["id"] != 1:
            continue

        start_timestamp = leave["startDate"] / 1000
        end_timestamp = leave["endDate"] / 1000

        # Convert timestamps to datetime
        start_date = datetime.datetime.fromtimestamp(start_timestamp)
        end_date = datetime.datetime.fromtimestamp(end_timestamp)

        # Convert date to datetime
        check_date = datetime.datetime.strptime(date, "%Y-%m-%d") + datetime.timedelta(hours=8)

        # Check if the date is within the range
        if start_date <= check_date <= end_date:
            found = leave

    if found:
        logging.info(f"Leave found in {date}: {found['leaveType']['name']}. Skipping creation of timesheet entry...")

    return found


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


def get_holidays(user_key):
    (first_day, last_day) = get_first_and_last_day_of_the_month()
    logging.info(f"Retrieving list of holidays for {first_day} - {last_day} date range")
    api_url = f"https://issues.mycollab.co/rest/com.easesolutions.jira.plugins.timesheet/latest/timesheet/holidays" \
              f"/{user_key}/{first_day}/{last_day}"
    response = requests.get(api_url, auth=HTTPBasicAuth(EMAIL, PASSWORD))

    # Check if the request was successful
    if response.status_code == 200:
        logging.info(f"Successfully retrieved holidays for {first_day} - {last_day} date range...")
        return response.json()
    else:
        logging.info(f"Failed to retrieve holidays for {first_day} - {last_day} date range...")
        logging.debug(f"Status code: {response.status_code}")
        logging.debug(f"Response: {response.text}")


def get_leaves(user_key):
    (first_day, last_day) = get_first_and_last_day_of_the_month()
    logging.info(f"Retrieving list of leaves for {first_day} - {last_day} date range")
    api_url = f"https://issues.mycollab.co/rest/com.easesolutions.jira.plugins.timesheet/latest/timesheet/leaves" \
              f"/{user_key}/{first_day}/{last_day}"
    response = requests.get(api_url, auth=HTTPBasicAuth(EMAIL, PASSWORD))

    # Check if the request was successful
    if response.status_code == 200:
        logging.info(f"Successfully retrieved leaves for {first_day} - {last_day} date range...")
        return response.json()
    else:
        logging.info(f"Failed to retrieve leaves for {first_day} - {last_day} date range...")
        logging.debug(f"Status code: {response.status_code}")
        logging.debug(f"Response: {response.text}")


def get_contract_days(user_key):
    (first_day, last_day) = get_first_and_last_day_of_the_month()
    logging.info(f"Retrieving list of contract days for {first_day} - {last_day} date range")
    api_url = f"https://issues.mycollab.co/rest/com.easesolutions.jira.plugins.timesheet/latest/timesheet/contract/days" \
              f"/{user_key}/{first_day}/{last_day}"
    response = requests.get(api_url, auth=HTTPBasicAuth(EMAIL, PASSWORD))

    # Check if the request was successful
    if response.status_code == 200:
        logging.info(f"Successfully retrieved contract days for {first_day} - {last_day} date range...")
        return response.json()
    else:
        logging.info(f"Failed to retrieve contract days for {first_day} - {last_day} date range...")
        logging.debug(f"Status code: {response.status_code}")
        logging.debug(f"Response: {response.text}")


def get_timesheet_entries(user_key):
    (first_day, last_day) = get_first_and_last_day_of_the_month()
    logging.info(f"Retrieving list of timesheet entries for {first_day} - {last_day} date range")
    api_url = f"https://issues.mycollab.co/rest/com.easesolutions.jira.plugins.timesheet/latest/timesheet/workspaces" \
              f"/{user_key}/{first_day}/{last_day}"
    response = requests.get(api_url, auth=HTTPBasicAuth(EMAIL, PASSWORD))

    # Check if the request was successful
    if response.status_code == 200:
        logging.info(f"Successfully retrieved timesheet entries for {first_day} - {last_day} date range...")
        return response.json()
    else:
        logging.info(f"Failed to retrieve timesheet entries for {first_day} - {last_day} date range...")
        logging.debug(f"Status code: {response.status_code}")
        logging.debug(f"Response: {response.text}")


def create_dialog(title, text, details, user_key, holidays, leaves, missing_entries):
    def toggle_details():
        # This function toggles the visibility of the details textbox
        if details_frame.winfo_ismapped():  # Check if the details frame is visible
            details_frame.pack_forget()  # Hide the details frame
            show_details_button.config(text="Show Details")  # Change button text back
        else:
            details_frame.pack(padx=10, pady=10)  # Show the details frame
            show_details_button.config(text="Hide Details")  # Change button text to "Hide Details"

    def on_missing_entries_button_click():
        for missing_entry in missing_entries:
            create_timesheet_entry(missing_entry, user_key, holidays, leaves)

        root.quit()

    # Create the main window
    root = tk.Tk()
    root.title(title)

    # Create a frame to hold the content
    main_frame = tk.Frame(root)
    main_frame.pack(padx=20, pady=20)

    # Create a label with the main message
    message_label = tk.Label(main_frame, text=text)
    message_label.pack(padx=10, pady=(0, 10))

    # Create a button to show/hide details
    show_details_button = tk.Button(main_frame, text="Show Details", command=toggle_details)
    show_details_button.pack(pady=5)

    # Create the additional button (always visible)
    create_missing_entries_button = tk.Button(main_frame, text="Create Missing Timesheet Entries", command=on_missing_entries_button_click)
    create_missing_entries_button.pack(pady=5)

    # Create a frame for the details, initially hidden
    details_frame = tk.Frame(root)

    # Create a read-only Text widget inside the details frame
    details_text = tk.Text(details_frame, height=10, width=40, wrap=tk.WORD)
    details_text.insert(tk.END, details)
    details_text.config(state=tk.DISABLED)  # Make the text field read-only
    details_text.pack(padx=10, pady=10)

    # Start the Tkinter main loop
    root.mainloop()


def send_email(text, details):
    # Create the message
    msg = MIMEMultipart()
    msg["From"] = EMAIL
    msg["To"] = EMAIL
    msg["Subject"] = "Missing Timesheet Entries"

    # Add the body of the email
    body = f"{text}\n\n" + details
    msg.attach(MIMEText(body, "plain"))

    try:
        # Setup the server for Outlook
        server = smtplib.SMTP("smtp.office365.com", 587)  # Outlook SMTP server
        server.starttls()  # Start TLS encryption
        server.login(EMAIL, PASSWORD)  # Login to the email account

        # Send the email
        text = msg.as_string()
        server.sendmail(EMAIL, EMAIL, text)

        logging.info("Email sent successfully!")

    except Exception as e:
        logging.error(f"Failed to send email: {e}")

    finally:
        server.quit()


# Press the green button in the gutter to run the script.
if __name__ == "__main__":
    init()
