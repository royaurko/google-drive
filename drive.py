#!/usr/bin/python
import os
import httplib2
import pprint
import mimetypes
import time
import sys
import pymongo
import string
from pymongo import MongoClient
from apiclient.discovery import build
from apiclient.http import MediaFileUpload
from apiclient import errors
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
# Set CLIENT_ID and CLIENT_SECRET as your environment variables

# Check https://developers.google.com/drive/scopes for all available scopes
OAUTH_SCOPE = 'https://www.googleapis.com/auth/drive'

# Redirect URI for installed apps
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'


def initialize_db(drive_service):
    # Populate database with the current metadata
    client = MongoClient()
    db = client.drivedb
    db.json_info.drop()
    json_info = db.drivedb
    file_list = drive_service.files().list().execute()['items']
    for i in range(len(file_list)):
        temp_dict = dict((k,file_list[i][k]) for k in ('id', 'title', 'createdDate', 'modifiedDate'))
        json_id = json_info.insert(temp_dict)
    print 'Database populated!'
    return json_info


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


def upload(file_name, drive_service, json_info):
    # Upload a file
    mime_type = mimetypes.guess_type(file_name)
    if mime_type == (None, None):
        mime_type = 'text/plain'
    media_body = MediaFileUpload(file_name, mimetype=mime_type, resumable=True)
    body = {
        'title': file_name,
        'description': 'A test document',
        'mimeType': mime_type
    }
    # Upload the returned metadata to mongodb
    try:
        file = drive_service.files().insert(body=body, media_body=media_body).execute()
        temp_dict = dict((k, file[k]) for k in ('id', 'title', 'createdDate', 'modifiedDate'))
        json_id = json_info.insert(temp_dict)
    except errors.HttpError, error:
        print 'An error occured: %s' % error


def delete(file_name, drive_service, json_info):
    file_id = json_info.find_one({'title': file_name})['id']
    json_info.remove({'title': file_name})
    try:
        drive_service.files().delete(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occurred: %s' % error


def watch(path, interval, drive_service, json_info):
    before = dict([(f, None) for f in os.listdir(path)])
    while True:
        time.sleep(interval)
        after = dict([(f, None) for f in os.listdir(path)])
        added = [f for f in after if not f in before]
        removed = [f for f in before if not f in after]
        if added:
            for f in added:
                print 'Added: ', ', '.join(added)
                upload(f, drive_service, json_info)
        if removed:
            for f in removed:
                print 'Removed: ', ', '.join(removed)
                delete(f, drive_service, json_info)
        before = after


if __name__ == '__main__':
    path = os.getcwd()
    interval = float(sys.argv[1])
    drive_service = authorize()
    file_list = drive_service.files().list().execute()['items']
    json_info = initialize_db(drive_service)
    watch(path, interval, drive_service, json_info)
