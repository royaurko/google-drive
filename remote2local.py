'''

This file contains all the functions that propagate changes from remote to local.

'''

import os
import time
from apiclient import errors
from db import populate_db
from pymongo import MongoClient

def download_dir(drive_service, json_info, file_id, log_file):
    try:
        dir_path = json_info.find_one({'id': file_id})['path']
        if not os.path.exists(dir_path):
            print 'Downloading: ' + dir_path
            write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
            write_str += 'Downloaded directory: ' + dir_path + '\n'
            log_file.write(write_str)
            os.makedirs(dir_path)
        return json_info
    except:
        print 'An error occurred downloading directory\n'
        return json_info


def download_file(drive_service, json_info, file_id, log_file, parent_id=None):
    try:
        file = drive_service.files().get(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occured: %s' % error
        return json_info
    download_url = file.get('downloadUrl')
    file_path = json_info.find_one({'id': file_id})['path']
    if download_url:
        resp, content = drive_service._http.request(download_url)
        if resp.status == 200:
            # need to set path properly
            if not os.path.isfile(file_path):
                print 'Downloading: ' + file_path
                f = open(file_path, 'w')
                f.write(content)
                f.close()
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Downloaded file: ' + file_path + '\n'
                log_file.write(write_str)
        else:
            print 'An error occurred: %s' % resp
    return json_info


def mirror_dir(drive_service, json_info, log_file):
    cursor = json_info.find({'mimeType':'application/vnd.google-apps.folder'})
    for entry in cursor:
        file_id = entry['id']
        json_info = download_dir(drive_service, json_info, file_id, log_file)
    return json_info


def mirror_file(drive_service, json_info, log_file):
    cursor = json_info.find()
    for entry in cursor:
            if entry['mimeType'] != 'application/vnd.google-apps.folder':
                # If it is not a folder
                file_id = entry['id']
                json_info = download_file(drive_service, json_info, file_id, log_file,)
    return json_info


def mirror(drive_service, json_info, log_file):
    # Mirror remote content into the folder pointed by path
    # first download all the directories
    mirror_dir(drive_service, json_info, log_file)
    # Download files to appropriate folders
    mirror_file(drive_service, json_info, log_file)
    return json_info



def refresh(path, drive_service, json_info, log_file):
    # Check to see if the database is up to date with local changes
    # Fetch current database from Drive
    current_json_info = populate_db(path, current_json_info, drive_service, log_file)
    old_cursor = json_info.find()
    new_cursor = current_json_info.find()
    print 'Old count: ' + str(old_cursor.count()) + '\n'
    print 'New count: ' + str(new_cursor.count()) + '\n'
    added = set([])
    deleted = set([])
    # Check for new/updated files
    for entry1 in new_cursor:
        cursor = json_info.find({'id': entry1['id']})
        if cursor.count() == 0:
            # This is a new document
            added.add(entry1['id'])
        for entry in cursor:
            if entry != entry1:
                # Either updated or moved, remove old entry from json_info
                added.add(entry1['id'])
                json_info.remove({'id': entry['id']})
    # Check for deleted files
    for entry2 in old_cursor:
        cursor = current_json_info.find({'id': entry2['id']})
        if cursor.count() == 0:
            # This means this entry was deleted
            deleted.add(entry2['id'])
    for file_id in added:
        title = json_info.find_one({'id': file_id})['title']
        print 'Added file from remote: ' + title
        mimetype = json_info.find_one({'id': file_id})['mimeType']
        if mimetype == 'application/vnd.google-apps.folder':
            # Need to set path correctly, find highest ancestor in added etc
            download_dir(drive_service, json_info, file_id, log_file)
        else:
            # Need to set path correctly
            download_file(drive_service, json_info, file_id, log_file)
    for file_id in deleted:
        file_path = json_info.find_one({'id': file_id})['path']
        title = json_info.find_one({'id': file_id})['path']
        print 'Removed file: ' + title
        purge(file_path, drive_service, json_info, log_file)
    return json_info
