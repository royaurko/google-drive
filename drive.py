#!/usr/bin/python
import os
import httplib2
import pprint
import mimetypes
from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from oauth2client.client import OAuth2WebServerFlow

# Set CLIENT_ID and CLIENT_SECRET as your environment variables

# Check https://developers.google.com/drive/scopes for all available scopes
OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

# Redirect URI for installed apps
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'

# Run through the OAuth flow and retrieve credentials
flow = OAuth2WebServerFlow(os.environ['CLIENT_ID'], os.environ['CLIENT_SECRET'], OAUTH_SCOPE,
                                                      redirect_uri=REDIRECT_URI)
authorize_url = flow.step1_get_authorize_url()
print 'Go to the following link in your browser: ' + authorize_url
code = raw_input('Enter verification code: ').strip()
credentials = flow.step2_exchange(code)

# Create an httplib2.Http object and authorize it with our credentials
http = httplib2.Http()
http = credentials.authorize(http)

drive_service = build('drive', 'v2', http=http)

# Upload a file
def upload(file_name='document'):
    media_body = MediaFileUpload(file_name, mimetype=mimetypes.guess_type(file_name), resumable=True)
    body = {
        'title': 'My document',
        'description': 'A test document',
        'mimeType': 'text/plain'
    }

    file = drive_service.files().insert(body=body, media_body=media_body).execute()
    pprint.pprint(file)

if __name__ == '__main__':
    upload('document.txt')
