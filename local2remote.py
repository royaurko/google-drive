'''

This file contains all the functions that propagate changes from the local directory to the remote copy

'''

import os
import mimetypes
import time
from apiclient.http import MediaFileUpload
from apiclient import errors

def upload(file_name, drive_service, json_info, log_file, flag=True, parent_id=None):
    # Upload a file
    if flag:
        k = file_name.rfind('/') + 1
        fpath = file_name[:k-1]
        print fpath
        fname = file_name[k:]
        if os.path.isfile(file_name):
            return json_info
        mime_type = mimetypes.guess_type(file_name)
        if mime_type == (None, None):
            mime_type = 'text/plain'
        media_body = MediaFileUpload(file_name,
                                     mimetype=mime_type, resumable=True)
    else:
        # It is a folder, set appropriate mime type
        if os.path.isdir(file_name):
            return json_info
        fname = file_name
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
        file = drive_service.files().insert(body=body,
                                            media_body=media_body).execute()
        temp_dict = dict((k, file[k])
                         for
                         k
                         in
                         ('id', 'title', 'parents',
                          'mimeType', 'createdDate', 'modifiedDate'))
        if flag:
            temp_dict['path'] = fpath
            temp_dict['broken'] = False
            write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
            write_str += 'Uploaded (new) file: ' + file_name + '\n'
            log_file.write(write_str)
        else:
            temp_dict['path'] = file_name
            temp_dict['broken'] = False
            write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
            write_str += 'Uploaded (new) directory: ' + file_name + '\n'
            log_file.write(write_str)
        json_id = json_info.insert(temp_dict)
    except errors.HttpError, error:
        print 'An error occured: %s' % error


def update(file_name, drive_service, json_info, log_file, parent_id=None):
    # Update existing file
    try:
        k = file_name.rfind('/') + 1
        fname = file_name[k:]
        cursor = json_info.find({'title': fname})
        file_id = ''
        for entries in cursor:
            if 'parents' in entries:
                if parent_id == entries['parents'][0]['id']:
                    file_id = entries['id']
                    print 'here'
            else:
                if parent_id is None:
                    file_id = entries['id']
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
        write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
        write_str += 'Uploaded (modified) file: ' + file_name + '\n'
        log_file.write(write_str)
    except errors.HttpError, error:
        print 'An error has occured: %s' % error


def delete(file_name, drive_service, json_info, log_file, parent_id=None):
    cursor = json_info.find({'title': file_name})
    for entries in cursor:
        # delete all files with the file name
        file_id = entries['id']
        if 'parents' in entries:
            if entries['parents'][0]['id'] == parent_id:
                json_info.remove({'title': file_name})
                try:
                    drive_service.files().delete(fileId=file_id).execute()
                except errors.HttpError, error:
                    print 'An error occurred: %s' % error
        else:
            json_info.remove({'title': file_name})
            try:
                drive_service.files().delete(fileId=file_id).execute()
                write_str = time.strftime("%m.%d.%y %H:%M ", time.localtime())
                write_str += 'Deleted: ' + file_name + '\n'
                log_file.write(write_str)
            except errors.HttpError, error:
                print 'An error occured: %s' % error

