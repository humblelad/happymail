import pickle
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google.cloud import storage
from functions_framework import http

BUCKET_NAME = 'xyz'
TOKEN_FILE = 'token.pickle'
HISTORY_ID_FILE = 'prev_history_id.txt'

def download_blob(bucket_name, source_blob_name, destination_file_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)

def authenticate_gmail():
    creds = None
    download_blob(BUCKET_NAME, TOKEN_FILE, TOKEN_FILE)
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
        upload_blob(BUCKET_NAME, TOKEN_FILE, TOKEN_FILE)
    service = build('gmail', 'v1', credentials=creds)
    return service

def setup_watch():
    gmail_service = authenticate_gmail()
    request_body = {
        'labelIds': ['thelabelid'],
        'labelFilterBehavior': 'include',
        'topicName': 'projects/xyz-450100/topics/xyz'
    }
    response = gmail_service.users().watch(userId='me', body=request_body).execute()
    history_id = response.get('historyId')
    if history_id:
        with open(HISTORY_ID_FILE, 'w') as f:
            f.write(history_id)
        upload_blob(BUCKET_NAME, HISTORY_ID_FILE, HISTORY_ID_FILE)
    return response

@http
def setup_watch_endpoint(request):
    response = setup_watch()
    return response, 200
