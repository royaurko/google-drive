'''

This file contains all the functions that propagate changes from the local directory to the remote copy

'''

import os
import mimetypes
import time
from apiclient.http import MediaFileUpload
from apiclient import errors

def upload(file_name, drive_service, json_info, log_file, flag=True, parent_id=None):
    # Function to upload a file
    try:
        # Before uploading check if the file already exists in drive
        k = file_name.rfind('/') + 1
        fname = file_name[k:]
        cursor = json_info.find({'title': fname, 'path': file_name})
        if cursor.count() > 1:
            return json_info
        if flag:
            mime_type = mimetypes.guess_type(file_name)
            if mime_type == (None, None):
                mime_type = 'text/plain'
            media_body = MediaFileUpload(file_name, mimetype=mime_type, resumable=True)
        else:
            media_body = None
            mime_type = 'application/vnd.google-apps.folder'
        body = {
            'title': fname,
            'mimeType': mime_type
        }
        if parent_id:
            body['parents'] = [{'id': parent_id}]
        # Upload the returned metadata to mongodb
        try:
            file = drive_service.files().insert(body=body, media_body=media_body).execute()
            temp_dict = dict((k, file[k])
                             for
                             k
                             in
                             ('id', 'title', 'parents',
                             'mimeType', 'createdDate', 'modifiedDate'))
            temp_dict['path'] = file_name
            temp_dict['broken'] = False
            write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
            if flag:
                write_str += 'Uploaded (new) file: ' + file_name + '\n'
                log_file.write(write_str)
            else:
                write_str += 'Uploaded (new) directory: ' + file_name + '\n'
                log_file.write(write_str)
            json_id = json_info.insert(temp_dict)
        except errors.HttpError, error:
            print 'An error occured: %s' % error
    except:
        print 'An error occured uploading file\n'


def update(file_name, drive_service, json_info, log_file):
    # Update existing file, find entry in database, check if path matches
    fpath = file_name
    entry = json_info.find_one({'path': file_name})
    file_id = entry['id']
    file = drive_service.files().get(fileId=file_id).execute()
    mime_type = mimetypes.guess_type(file_name)
    if mime_type == (None, None):
        mime_type = 'text/plain'
    media_body = MediaFileUpload(file_name,
                                     mimetype=mime_type, resumable=True)
    body = {
        'title': file_name,
        'description': '',
        'mimeType': mime_type
    }
    # Send file
    updated_file = drive_service.files().update(fileId=file_id, body=file,
                                                    media_body=media_body).execute()
    # Update last modified date in the database entry for this file
    file = drive_service.files().get(fileId=file_id).execute()
    modifiedDate = file.get('modifiedDate')
    json_info.update({'id': file_id}, {"$set": {'modifiedDate': modifiedDate}})
    # Write log entry
    write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
    write_str += 'Uploaded (modified) file: ' + file_name + '\n'
    log_file.write(write_str)
    # except errors.HttpError, error:
      #  print 'An error has occured: %s' % error


def delete(file_name, drive_service, json_info, log_file):
    try:
        # Delete individual file or folder
        k = file_name.rfind('/') + 1
        fname = file_name[k:]
        cursor = json_info.find({'title': fname, 'path': file_name})
        for entry in cursor:
            # delete all files with matching file_name (includes path)
            file_id = entry['id']
            try:
                drive_service.files().delete(fileId=file_id).execute()
                json_info.remove({'id': entry['id']})
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Deleted: ' + file_name + '\n'
                log_file.write(write_str)
            except errors.HttpError, error:
                print 'An error occurred: %s' % error
    except:
        print 'Error deleting file: ' + file_name


def purge(file_name, drive_service, json_info, log_file):
    # Delete file or folder and all the resulting orphans
    try:
        cursor = json_info.find({'path': file_name})
        if cursor.count() == 0:
            return
        for entry in cursor:
            file_id = entry['id']
            if entry['mimeType'] != 'application/vnd.google-apps.folder':
                #It is a file and so no need to check for orphans
                json_info = delete(file_name, drive_service, json_info, log_file)
                return
        # It must be a folder, check for possible orphans
        delete_info = set([(file_name, file_id)])
        flag = True
        while flag:
            cursor = json_info.find()
            old_size = len(delete_info)
            for entry in cursor:
                if 'parents' in entry:
                    if entry['parents']:
                        delete_id = set([f[1] for f in delete_info])
                        if entry['parents'][0]['id'] in delete_id:
                            # It has a parent in the list of items to be deleted
                            delete_info.add((entry['path'], entry['id']))
            if len(delete_info) == old_size:
                # No new children found
                flag = False
        # Delete all the files and folders accumulated in delete_id
        for f in delete_info:
            json_info = delete(f[0], drive_service, json_info, log_file)
    except:
        print 'Error deleting file\n'
