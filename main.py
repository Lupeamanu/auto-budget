import os.path
import argparse
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Setup argument parser for command-line arguments
parser = argparse.ArgumentParser(description="Auto Budget")
parser.add_argument(
    "-s", "--saved",
    type=float,
    help="Amount saved",
    required=True
)
parser.add_argument(
    "-c", "--category",
    type=str,
    help="Category of the expense",
    choices=["flight", "other"],
    required=False
)
args = parser.parse_args()

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# The ID and range of a sample spreadsheet.
SPREADSHEET_ID = "1r31bozcuKWcqU03O_5ic-xYKbEZpDZOTZTC3ERyO6Jk"
SHEET_NAME = "Sheet1"


def get_credentials():
    """Gets user credentials for Google Sheets API."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds


def get_all_sheet_values(service):
    """Get all values from a spreadsheet."""
    try:
        sheet = service.spreadsheets()
        result = (
            sheet.values()
            .get(spreadsheetId=SPREADSHEET_ID, range=SHEET_NAME)
            .execute()
        )
        values = result.get("values", [])
        return values
    except HttpError as err:
        print(err)
        return None


def get_rows(service):
    """Get all rows from the spreadsheet, skipping the header."""
    # Get all rows from the sheet (excluding header)
    sheet_range = f"{SHEET_NAME}!A2:F"
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=sheet_range
    ).execute()
    rows = result.get("values", [])
    return rows


def get_cumulative_sum(service):
    """Get the previous cumulative sum from the last row."""
    previous_cumulative_sum = 0
    # Get the last row of the sheet
    try:
        rows = get_rows(service)

        if rows:
            last_row = rows[-1]
            try:
                previous_cumulative_sum = float(last_row[3] if len(last_row) > 3 else 0)
            except ValueError:
                previous_cumulative_sum = 0
        else:
            previous_cumulative_sum = 0
    except HttpError as err:
        print(f"An error occurred: {err}")
        previous_cumulative_sum = 0

    return previous_cumulative_sum


def calculate_target_amount(service):
    """Calculate the target amount for the current date based on category."""
    rows = get_rows(service)

    target = 0

    if args.category == "flight":
        # Get the target amount for flight
        flight_count = sum(1 for row in rows if len(row) > 1 and row[1].strip().lower() == "flight")
        target = (flight_count + 1) * 416.67
    elif args.category == "other":
        # Get last row
        last_row = rows[-1] if rows else []
        # Get the target amount from last row
        if len(last_row) > 4:
            try:
                target = float(last_row[4])
            except ValueError:
                target = 0
        target = target + 305.72

    return target


def add_row_to_sheet(service):
    """Add a new row to the spreadsheet with calculated values."""
    # Get the previous cumulative sum
    previous_cumulative_sum = get_cumulative_sum(service)
    # Calculate the new cumulative sum
    new_cumulative_sum = previous_cumulative_sum + args.saved
    # Calculate the target amount to be saved for this date
    target_amount = calculate_target_amount(service)
    # Calculate the ahead/behind amount
    ahead_behind = new_cumulative_sum - target_amount
    # Build new row data
    row = [
        datetime.now().strftime("%Y-%m-%d"),
        "Flight" if args.category == "flight" else "Trip Expenses",
        args.saved,
        new_cumulative_sum,
        target_amount,
        ahead_behind
    ]

    # Append data to the end of the sheet
    try:
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1:F1",
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={
                "values": [row]
            }
        ).execute()

        print(f"Row added: {row}")
    except HttpError as err:
        print(f"An error occurred: {err}")
        return None


def main():
    """Main function to authenticate and add a row to the sheet."""
    creds = get_credentials()

    try:
        service = build("sheets", "v4", credentials=creds)

        # Add a row to the sheet
        add_row_to_sheet(service)

    except HttpError as err:
        print(err)


if __name__ == "__main__":
    main()
