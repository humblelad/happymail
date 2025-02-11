import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Define the required scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels'
]

def authenticate_gmail():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
      
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service

def get_label_id_by_name(service, label_name):
    response = service.users().labels().list(userId='me').execute()
    labels = response.get('labels', [])
    for label in labels:
        if label['name'].lower() == label_name.lower(): 
    raise ValueError(f"Label '{label_name}' not found.")

if __name__ == "__main__":
    gmail_service = authenticate_gmail()

    # Replace with your desired label name
    label_name = "rejected mails"
    label_id = get_label_id_by_name(gmail_service, label_name)
    print(label_id)
