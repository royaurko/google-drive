#!/usr/bin/python
import os
import httplib2
import pprint
import mimetypes
import time
import sys
from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage

# Set CLIENT_ID and CLIENT_SECRET as your environment variables

# Check https://developers.google.com/drive/scopes for all available scopes
OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

# Redirect URI for installed apps
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'


def authorize():
    # Check if credentials already exist
    fname = '.credentials'
    if os.path.isfile(fname):
        storage = Storage('.credentials')
        credentials = storage.get()
    else:
        # Create a flow object to get user authentication
        flow = OAuth2WebServerFlow(os.environ['CLIENT_ID'], os.environ['CLIENT_SECRET'], OAUTH_SCOPE,
                                                      redirect_uri=REDIRECT_URI)
        authorize_url = flow.step1_get_authorize_url()
        print 'Go to the following link in your browser: ' + authorize_url
        code = raw_input('Enter verification code: ').strip()
        credentials = flow.step2_exchange(code)
        # Store credentials for future use
        storage = Storage('.credentials')
        storage.put(credentials)

    # Create an httplib2.Http object and authorize it with our credentials
    http = httplib2.Http()
    http = credentials.authorize(http)

    drive_service = build('drive', 'v2', http=http)
    return drive_service


def upload(file_name, drive_service):
    # Upload a file
    mime_type = mimetypes.guess_type(file_name)
    print type(mime_type[0])
    if mime_type == (None, None):
        mime_type = 'text/plain'
    print mime_type
    media_body = MediaFileUpload(file_name, mimetype=mime_type, resumable=True)
    body = {
        'title': file_name,
        'description': 'A test document',
        'mimeType': mime_type
    }

    file = drive_service.files().insert(body=body, media_body=media_body).execute()
    pprint.pprint(file)


def watch(path, interval, drive_service):
    before = dict([(f, None) for f in os.listdir(path)])
    while True:
        time.sleep(interval)
        after = dict([(f, None) for f in os.listdir(path)])
        added = [f for f in after if not f in before]
        removed = [f for f in before if not f in after]
        if added:
            for f in added:
                print "Added: ", ", ".join(added)
                upload(f, drive_service)
        if removed:
            print "Removed: ", ", ".join(removed)
        before = after


if __name__ == '__main__':
    path = os.getcwd()
    interval = float(sys.argv[1])
    drive_service = authorize()
    watch(path, interval, drive_service)
