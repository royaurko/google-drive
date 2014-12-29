'''

This file contains all the functions that propagate changes from remote to local.

'''

import os
import shutil
import time
from apiclient import errors
from db import initialize_db
from pymongo import MongoClient
from local2remote import purge

def download_dir(drive_service, json_info, file_id, log_file):
    try:
        dir_path = json_info.find_one({'id': file_id})['path']
        if not os.path.exists(dir_path):
            print 'Downloading: ' + dir_path
            write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
            write_str += 'Downloaded directory: ' + dir_path + '\n'
            log_file.write(write_str)
            os.makedirs(dir_path)
    except:
        print 'An error occurred downloading directory\n'


def download_file(drive_service, json_info, file_id, log_file, parent_id=None):
    try:
        file = drive_service.files().get(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occured: %s' % error
    download_url = file.get('downloadUrl')
    file_path = json_info.find_one({'id': file_id})['path']
    if download_url:
        resp, content = drive_service._http.request(download_url)
        if resp.status == 200:
            # Need to check time stamp
            if not os.path.isfile(file_path):
                print 'Downloading: ' + file_path
                f = open(file_path, 'w')
                f.write(content)
                f.close()
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Downloaded file: ' + file_path + '\n'
                log_file.write(write_str)
            else:
                # File already exists, maybe it was modified in remote
                entry = json_info.find_one({'id': file_id})
                mtime_remote = entry['modifiedDate']
                # This is in RFC3399 need to convert it into UTC
                mtime_local = time.ctime(os.path.getmtime(file_path))
                # for now just download file, need to check modify time
                print 'Downloading: ' + file_path
                f = open(file_path, 'w')
                f.write(content)
                f.close()
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Downloaded file: ' + file_path + '\n'
                log_file.write(write_str)
        else:
            print 'An error occurred: %s' % resp


def mirror_dir(drive_service, json_info, log_file):
    cursor = json_info.find({'mimeType':'application/vnd.google-apps.folder'})
    for entry in cursor:
        file_id = entry['id']
        download_dir(drive_service, json_info, file_id, log_file)
    return json_info


def mirror_file(drive_service, json_info, log_file):
    cursor = json_info.find()
    for entry in cursor:
            if entry['mimeType'] != 'application/vnd.google-apps.folder':
                # If it is not a folder
                file_id = entry['id']
                download_file(drive_service, json_info, file_id, log_file,)


def mirror(drive_service, json_info, log_file):
    # Mirror remote content into the folder pointed by path
    # first download all the directories
    mirror_dir(drive_service, json_info, log_file)
    # Download files to appropriate folders
    mirror_file(drive_service, json_info, log_file)


def refresh(path, drive_service, db, log_file):
    # Check to see if the database is up to date with local changes
    new_json_info = db.tmpdb
    old_json_info = db.drivedb
    initialize_db(path, drive_service, new_json_info)
    old_cursor = old_json_info.find()
    new_cursor = new_json_info.find()
    added = set([])
    updated = set([])
    deleted = set([])
    # Check for new/updated files
    for entry1 in new_cursor:
        cursor = old_json_info.find({'path': entry1['path']})
        if cursor.count() == 0:
            # This is a new document
            print 'a file was added!'
            added.add(entry1['id'])
            continue
        '''
        for entry in cursor:
            if entry['modifiedDate'] != entry1['modifiedDate']:
                # It was updated, remove old entry from db.drivedb
                added.add(entry1['id'])
                old_json_info.remove({'id': entry['id']})
        '''
    # Check for deleted files
    for entry2 in old_cursor:
        print 'old: ' + entry2['path']
        tmp_cursor = new_json_info.find({'path': entry2['path']})
        if cursor.count() == 0:
            print 'a file was deleted!'
            # This means this entry was deleted
            deleted.add(entry2['id'])
    if added:
        for file_id in added:
            # First download all folders
            mimetype = db.tmpdb.find_one({'id': file_id})['mimeType']
            if mimetype == 'application/vnd.google-apps.folder':
                # Need to set path correctly, find highest ancestor in added etc
                download_dir(drive_service, db.tmpdb, file_id, log_file)
                entry = db.tmpdb.find_one({'id': file_id})
                db.drivedb.insert(entry)
        for file_id in added:
            mimetype = db.tmpdb.find_one({'id': file_id})['mimeType']
            if mimetype != 'application/vnd.google-apps.folder':
                # Need to set path correctly
                download_file(drive_service, db.tmpdb, file_id, log_file)
                entry = db.tmpdb.find_one({'id': file_id})
                db.drivedb.insert(entry)
    if deleted:
        print 'Deleted: ' + str(deleted)
        for file_id in deleted:
            # Check if it was a folder
            mimetype = json_info.find_one({'id': file_id})['mimeType']
            if mimetype == 'application/vnd.google-apps.folder':
                # It is a folder, use shutil to remove
                file_path = old_json_info.find_one({'id': file_id})['path']
                shutil.rmtree(file_path)
            else:
                # It is a file
                file_path = old_json_info.find_one({'id': file_id})['path']
                if os.exists(file_path):
                    os.remove(file_path)
            title = db.drivedb.find_one({'id': file_id})['path']
            print 'Removed file: ' + title
            purge(file_path, drive_service, db.drivedb, log_file)
    # Clean up tmpdb
    db.tmpdb.remove()
