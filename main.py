import base64
import os
import requests
import pickle
import json
from email.mime.text import MIMEText
from google.cloud import storage, secretmanager
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import functions_framework

# THis is the main cloud run function
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.insert'
]

# Cloud Storage configuration
BUCKET_NAME = "xyz" 
TOKEN_FILE_NAME = "token.pickle"   
HISTORY_FILE_NAME = "prev_history_id.txt"  


def get_token_from_gcs():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(TOKEN_FILE_NAME)
    token_pickle = blob.download_as_bytes()
    print("Loaded token from GCS.")
    return pickle.loads(token_pickle)

def save_token_to_gcs(creds):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(TOKEN_FILE_NAME)
    token_pickle = pickle.dumps(creds)
    blob.upload_from_string(token_pickle)
    print("Refreshed token saved to GCS.")

def get_history_id_from_gcs():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(HISTORY_FILE_NAME)
    if blob.exists():
        history_id = blob.download_as_text()
        print("Loaded history ID from GCS.")
        return history_id.strip()
    print("No previous history ID found in GCS.")
    return None

def save_history_id_to_gcs(new_id):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(HISTORY_FILE_NAME)
    blob.upload_from_string(new_id)
    print("Saved history ID to GCS.")

def get_gmail_service():
    creds = None
    try:
        creds = get_token_from_gcs()
        print("Token loaded successfully.")
    except Exception as e:
        raise Exception("Failed to load token from Cloud Storage: " + str(e))

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expired. Refreshing...")
            try:
                creds.refresh(Request())
                save_token_to_gcs(creds)
            except Exception as e:
                raise Exception("Failed to refresh access token: " + str(e))
        else:
            raise Exception("No valid credentials available. Please run the OAuth flow locally to generate the token.pickle file.")
    
    return build('gmail', 'v1', credentials=creds)


def get_perplexity_token():
    """
    Retrieves the Perplexity API token from Google Secret Manager.
      
    """
    client = secretmanager.SecretManagerServiceClient()
    #project_id = os.environ.get("GCP_PROJECT_ID", "your-project-id")
    secret_name = "projects/xyz/secrets/xyz/versions/latest"
    response = client.access_secret_version(request={"name": secret_name})
    token = response.payload.data.decode("UTF-8")
    print("Retrieved Perplexity token from Secret Manager.")
    return token


def analyze_email_with_perplexity(email_content):
    """
    Calls the Perplexity API to generate a motivational message.
    Uses a token fetched from Secret Manager rather than a hardcoded token.
    """
    url = "https://api.perplexity.ai/chat/completions"
    perplexity_token = get_perplexity_token()
    headers = {
        "Authorization": f"Bearer {perplexity_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    data = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "You are an advanced AI assistant that converts job rejection email with motivational messages under 150 words."},
            {"role": "user", "content": f"Replace this rejection email with a highly motivational message. Ensure that you never say you are rejected or you are not moving forward. First, I want you to say: You have a new message from [insert the company name here if you are able to find from the email]. Then add a positive motivating message about life, struggle, happiness, courage and other philosophy. You can also use a quote, even famous movie dialogues. In a nutshell, it should be highly motivating. Please don't use ending salutations at the end.:\n\n{email_content}"}
        ],
        "max_tokens": 1000
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()["choices"][0]["message"]["content"]
    else:
        raise Exception(f"Perplexity API call failed: {response.status_code}, {response.text}")


def get_email_content(service, message_id):
    message = service.users().messages().get(userId='me', id=message_id).execute()
    payload = message.get('payload', {})
    body_data = payload.get('body', {}).get('data', '')
    if not body_data and 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                body_data = part.get('body', {}).get('data', '')
                if body_data:
                    break
    if body_data:
        return base64.urlsafe_b64decode(body_data).decode('utf-8')
    return ""

def get_email_headers(service, message_id):
    try:
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        headers = {}
        for header in message.get('payload', {}).get('headers', []):
            headers[header['name']] = header['value']
        return headers
    except Exception as e:
        print(f"Error fetching email headers for message ID {message_id}: {e}")
        return {}

def create_motivational_email(original_headers, motivational_quote):
    new_body = (f"Hello,\n"
                f"{motivational_quote}\n\n"
                f"--- Original mail moved to Trash ---")
    mime_msg = MIMEText(new_body, "plain")
    mime_msg["Subject"] = "Motivational Message"
    mime_msg["From"] = original_headers.get("To", "")
    mime_msg["To"] = original_headers.get("To", "")
    print(mime_msg.as_string())
    return mime_msg.as_string()

def replace_email_content(service, message_id, new_raw_message):
    raw_message = base64.urlsafe_b64encode(new_raw_message.encode("utf-8")).decode("utf-8")
    inserted_message = service.users().messages().insert(userId='me', body={'raw': raw_message}).execute()
    service.users().messages().modify(
        userId='me',
        id=inserted_message['id'],
        body={'addLabelIds': ['INBOX','UNREAD']}
    ).execute()
    service.users().messages().trash(userId='me', id=message_id).execute()
    return inserted_message

def get_new_messages(service, start_history_id):
    try:
        response = service.users().history().list(
            userId='me',
            startHistoryId=start_history_id,
            historyTypes=['messageAdded']
        ).execute()
    except Exception as e:
        print("Error fetching history:", e)
        return [], None

    new_message_ids = []
    if "history" in response:
        for record in response['history']:
            if "messagesAdded" in record:
                for m in record['messagesAdded']:
                    new_message_ids.append(m['message']['id'])
    return new_message_ids, response.get('historyId')

@functions_framework.cloud_event
def hello_pubsub(cloud_event):
    print(cloud_event.data["message"])
    
    push_payload_encoded = cloud_event.data["message"]["data"]
    
    try:
        push_payload = json.loads(
            base64.urlsafe_b64decode(push_payload_encoded).decode("utf-8")
        )
        print(f"Decoded Pub/Sub payload: {push_payload}")
        
        email_address = push_payload.get("emailAddress")
        new_history_id = push_payload.get("historyId")
        
        if not email_address or not new_history_id:
            print("Push payload missing emailAddress or historyId.")
            return
        
        print(f"Push received for email: {email_address}, historyId: {new_history_id}")
        
        service = get_gmail_service()
        prev_history_id = get_history_id_from_gcs()
        
        if not prev_history_id:
            print("No prior history ID found; saving current historyId and exiting.")
            save_history_id_to_gcs(new_history_id)
            return

        new_message_ids, latest_history_from_api = get_new_messages(service, prev_history_id)
        
        if new_message_ids:
            print(f"Found new Gmail message IDs: {new_message_ids}")
            msg_id = new_message_ids[-1]
            message = service.users().messages().get(userId='me', id=msg_id).execute()
            
            if 'labelxyz' in message.get('labelIds', []):
                original_content = get_email_content(service, msg_id)
                print(f"Original content: {original_content}")
                
                if not original_content.strip():
                    print(f"No content found for message ID: {msg_id}")
                    return
                
                original_headers = get_email_headers(service, msg_id)
                
                try:
                    motivational_text = analyze_email_with_perplexity(original_content)
                    print(f"Generated motivational text: {motivational_text}")
                except Exception as e:
                    print(f"Error generating motivational text for message {msg_id}: {e}")
                    return
                
                new_email_raw = create_motivational_email(original_headers, motivational_text)
                
                try:
                    new_message = replace_email_content(service, msg_id, new_email_raw)
                    print(f"Replaced email. New message inserted with ID: {new_message.get('id')}")
                except Exception as e:
                    print(f"Error inserting motivational email for message {msg_id}: {e}")
            else:
                print("The latest message does not have the expected label; skipping processing.")
        
        else:
            print(f"No new messages since historyId: {prev_history_id}")

        if latest_history_from_api:
            save_history_id_to_gcs(latest_history_from_api)
        else:
            save_history_id_to_gcs(new_history_id)

    except Exception as e:
        print(f"Error processing Pub/Sub event: {e}")
