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
        temp_dict = dict((k,file_list[i][k]) for k in ('id', 'title', 'parents', 'createdDate', 'modifiedDate'))
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


def upload(file_name, drive_service, json_info, flag = True, parent_id = None):
    # Upload a file
    if flag:
        mime_type = mimetypes.guess_type(file_name)
        if mime_type == (None, None):
            mime_type = 'text/plain'
        media_body = MediaFileUpload(file_name, mimetype = mime_type, resumable = True)
    else:
        # It is a folder, set appropriate mime type
        media_body = None
        mime_type = 'application/vnd.google-apps.folder'
    body = {
        'title': file_name,
        'mimeType': mime_type
    }
    if parent_id:
        body['parents'] = [{'id': parent_id}]
    # Upload the returned metadata to mongodb
    try:
        file = drive_service.files().insert(body=body, media_body=media_body).execute()
        temp_dict = dict((k, file[k]) for k in ('id', 'title', 'createdDate', 'modifiedDate'))
        json_id = json_info.insert(temp_dict)
    except errors.HttpError, error:
        print 'An error occured: %s' % error


def update(file_name, drive_service, json_info):
    # Update existing file
    try:
        file_id = json_info.find_one({'title': file_name})['id']
        file = drive_service.files().get(fileId = file_id).execute()
        mime_type = mimetypes.guess_type(file_name)
        if mime_type == (None, None):
            mime_type = 'text/plain'
        media_body = MediaFileUpload(file_name, mimetype = mime_type, resumable = True)
        body = {
            'title': file_name,
            'description': '',
            'mimeType': mime_type
        }
        # Send file
        updated_file = drive_service.files().update(fileId = file_id, body = file, media_body = media_body).execute()
    except errors.HttpError, error:
        print 'An error has occured: %s' % error


def delete(file_name, drive_service, json_info):
    print 'Delete called on filename %s' % file_name
    file_id = json_info.find_one({'title': file_name})['id']
    json_info.remove({'title': file_name})
    try:
        drive_service.files().delete(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occurred: %s' % error


def watch(path, interval, drive_service, json_info, log_file):
    forbidden = ['.git', '.credentials', 'log', 'drive.py', '.ropeproject']
    before_file = {}
    before_dir = {}
    after_dir = {}
    after_file = {}
    for root, dirs, files in os.walk(path, topdown = True):
        dirs[:] = [d for d in dirs if d not in forbidden]
        before_file[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f)))) for f in files if f not in forbidden])
        before_dir[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f)))) for f in dirs if f not in forbidden])
    while True:
        time.sleep(interval)
        # First check if any of the old files were modified
        for root, dirs, files in os.walk(path, topdown = True):
            dirs[:] = [d for d in dirs if d not in forbidden]
            after_file[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f)))) for f in files if f not in forbidden])
            after_dir[root] = dict([(f, time.ctime(os.path.getmtime(os.path.join(root, f)))) for f in dirs if f not in forbidden])
            # Get list of files changed since last check
            added_file = [f for f in after_file[root] if not f in before_file[root]]
            removed_file = [f for f in before_file[root] if not f in after_file[root]]
            modified_file = [f for f in before_file if f in after_file[root] and before_file[root][f]!=after_file[root][f]]
            # Get list of directories changed since last check
            added_dir = [f for f in after_dir[root] if not f in before_dir[root]]
            removed_dir = [f for f in before_dir[root] if not f in after_dir[root]]
            modified_dir = [f for f in before_dir if f in after_dir[root] and before_dir[root][f]!=after_dir[root][f]]
            if added_file:
                print 'Added file', ','.join(added_file)
                title = root.lstrip(path)
                parent_id = json_info.find_one({'title': title})
                print parent_id
                for f in added_file:
                    upload(f, drive_service, json_info, flag = True, parent_id = parent_id)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (new) files: ' + ', '.join(added_file) + '\n'
                    log_file.write(write_str)
            if modified_file:
                print 'Modified file', ','.join(modified_file)
                for f in modified_file:
                    update(f, drive_service, json_info)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (modified) files: ' + ', '.join(modified_file) + '\n'
                    log_file.write(write_str)
            if removed_file:
                for f in removed_file:
                    delete(f, drive_service, json_info)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Removed: ' + ', '.join(removed_file) + '\n'
                    log_file.write(write_str)
            if added_dir:
                print 'Added directory', ','.join(added_dir)
                title = root.lstrip(path)
                parent_id = json_info.find_one({'title': title})
                for f in added_dir:
                    upload(f, drive_service, json_info, flag = False, parent_id = parent_id)
                    print os.path.join(root, f)
                    before_dir[os.path.join(root, f)] = {}
                    before_file[os.path.join(root, f)] ={}
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (new) directories: ' + ', '.join(added_dir) + '\n'
                    log_file.write(write_str)
            if modified_dir:
                for f in modified_dir:
                    update(f, drive_service, json_info)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Uploaded (modified) directories: ' + ', '.join(modified_dir) + '\n'
                    log_file.write(write_str)
            if removed_dir:
                for f in removed_dir:
                    delete(f, drive_service, json_info)
                    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                    write_str += 'Removed directories: ' + ', '.join(removed_dir) + '\n'
                    log_file.write(write_str)
            before_file[root] = after_file[root]
            before_dir[root] = after_dir[root]


if __name__ == '__main__':
    path = os.getcwd()
    interval = float(sys.argv[1])
    drive_service = authorize()
    file_list = drive_service.files().list().execute()['items']
    json_info = initialize_db(drive_service)
    log_file = open('log', 'wb', 0)
    watch(path, interval, drive_service, json_info, log_file)
