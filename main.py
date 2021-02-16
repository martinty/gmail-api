from __future__ import print_function

import mimetypes
import pickle
import os.path
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import subprocess
import base64
import email

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


def run_shell_script(name):
    subprocess.call(["sh", name], stderr=subprocess.PIPE, stdout=subprocess.PIPE)


def get_feedback(name):
    f = open(name, "r")
    text = f.read()
    f.close()
    return text


def get_msg_all(service, user_id):
    try:
        return service.users().messages().list(userId=user_id).execute()
    except Exception as error:
        print('An error occurred: %s' % error)
        return None


def get_msg(service, user_id, msg_id):
    try:
        return service.users().messages().get(userId=user_id, id=msg_id, format='metadata').execute()
    except Exception as error:
        print('An error occurred: %s' % error)
        return None


def load_attachments(service, user_id, msg_id, store_dir):
    try:
        message = service.users().messages().get(userId=user_id, id=msg_id).execute()
        for part in message['payload']['parts']:
            if(part['filename'] and part['body'] and part['body']['attachmentId']):
                attachment = service.users().messages().attachments().get(id=part['body']['attachmentId'], userId=user_id, messageId=msg_id).execute()
                file_data = base64.urlsafe_b64decode(attachment['data'].encode('utf-8'))
                path = ''.join([store_dir, part['filename']])
                f = open(path, 'wb')
                f.write(file_data)
                f.close()
    except Exception as error:
        print('An error occurred: %s' % error)


def find_msg_ids(service, subject):
    msg_all = get_msg_all(service, 'me').get('messages')
    msg_id_list = []
    for msg_info in msg_all:
        msg_id = msg_info.get('id')
        msg = get_msg(service, 'me', msg_id)
        label_ids = msg.get('labelIds')
        if label_ids[0] != 'UNREAD':
            continue
        payload = msg.get('payload')
        headers = payload.get('headers')
        for info in headers:
            if info.get('name') == 'Subject' and info.get('value') == subject:
                msg_id_list.append(msg_id)
    return msg_id_list


def find_sender_email(service, msg_id):
    msg = get_msg(service, 'me', msg_id)
    payload = msg.get('payload')
    headers = payload.get('headers')
    for info in headers:
        if info.get('name') == 'Return-Path':
            return info.get('value')
    return None


def create_msg(sender, to, subject, message_text):
    """Create a message for an email.

    Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.

    Returns:
    An object containing a base64url encoded email object.
    """
    message = MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject
    raw_message = base64.urlsafe_b64encode(message.as_string().encode("utf-8"))
    return {'raw': raw_message.decode("utf-8")}


def create_msg_with_attachment(sender, to, subject, message_text, file):
    """Create a message for an email.

    Args:
    sender: Email address of the sender.
    to: Email address of the receiver.
    subject: The subject of the email message.
    message_text: The text of the email message.
    file: The path to the file to be attached.

    Returns:
    An object containing a base64url encoded email object.
    """
    message = MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    msg = MIMEText(message_text)
    message.attach(msg)

    content_type, encoding = mimetypes.guess_type(file)

    if content_type is None or encoding is not None:
        content_type = 'application/octet-stream'
    main_type, sub_type = content_type.split('/', 1)
    if main_type == 'text':
        fp = open(file, 'rb')
        msg = MIMEText(fp.read(), _subtype=sub_type)
        fp.close()
    elif main_type == 'image':
        fp = open(file, 'rb')
        msg = MIMEImage(fp.read(), _subtype=sub_type)
        fp.close()
    elif main_type == 'audio':
        fp = open(file, 'rb')
        msg = MIMEAudio(fp.read(), _subtype=sub_type)
        fp.close()
    else:
        fp = open(file, 'rb')
        msg = MIMEBase(main_type, sub_type)
        msg.set_payload(fp.read())
        fp.close()
    filename = os.path.basename(file)
    msg.add_header('Content-Disposition', 'attachment', filename=filename)
    message.attach(msg)

    return {'raw': base64.urlsafe_b64encode(message.as_string())}


def create_draft(service, user_id, message_body):
    """Create and insert a draft email. Print the returned draft's message and id.

    Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    message_body: The body of the email message, including headers.

    Returns:
    Draft object, including draft id and message meta data.
    """
    try:
        message = {'message': message_body}
        draft = service.users().drafts().create(userId=user_id, body=message).execute()
        print("Draft id: %s\nDraft message: %s" % (draft['id'], draft['message']))
        return draft
    except Exception as e:
        print('An error occurred: %s' % e)
        return None


def send_msg(service, user_id, message):
    """Send an email message.

    Args:
      service: Authorized Gmail API service instance.
      user_id: User's email address. The special value "me"
      can be used to indicate the authenticated user.
      message: Message to be sent.

    Returns:
      Sent Message.
    """
    try:
        msg = service.users().messages().send(userId=user_id, body=message).execute()
        print('Message Id: %s' % msg['id'])
        return msg
    except Exception as e:
        print('An error occurred: %s' % e)
        return None


def remove_label_from_msg(service, msg_id, label):
    try:
        service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': [label]}).execute()
    except Exception as e:
        print('An error occurred: %s' % e)

def main():
    """
    Shows basic usage of the Gmail API.
    """

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    service = build('gmail', 'v1', credentials=creds)
    profile = service.users().getProfile(userId='me').execute()

    msg_id_list = find_msg_ids(service, 'TDT4102')
    for msg_id in msg_id_list:
        subprocess.call(["rm -f handin.zip"], shell=True)
        load_attachments(service, 'me', msg_id, './')
        run_shell_script("run_test.sh")
        from_email = profile.get('emailAddress')
        to_email = find_sender_email(service, msg_id)
        text = get_feedback('feedback.txt')
        msg = create_msg(from_email, to_email, 'TDT4102 feedback', text)
        send_msg(service, 'me', msg)
        print("Email sent to " + to_email + " from " + from_email)
        remove_label_from_msg(service, msg_id, 'UNREAD')

    print("Done...")


if __name__ == '__main__':
    main()

