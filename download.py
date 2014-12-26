import os


def download_dir(path, drive_service, json_info, mongo_id):
    json_info.update({'_id': mongo_id}, {"$set": {'path': path}})
    if not os.path.exists(path):
        print 'Making directory: ' + path
        os.makedirs(path)
    return json_info


def download_file(path, drive_service, json_info, file_id, parent_id=None):
    try:
        file = drive_service.files().get(fileId=file_id).execute()
    except errors.HttpError, error:
        print 'An error occured: %s' % error
    download_url = file.get('downloadUrl')
    # In case the directory structure doesn't exist
    print path
    if not os.path.exists(path):
        if parent_id is not None:
            mongo_id = json_info.find_one({'id': parent_id})['_id']
            download_dir(path, drive_service, json_info, mongo_id)
    title = path + '/' + file.get('title')
    if download_url:
        resp, content = drive_service._http.request(download_url)
        if resp.status == 200:
            # need to set path properly
            print 'Downloading: ' + title
            f = open(title, 'w')
            f.write(content)
            f.close()
            json_info.update({'id': file_id}, {"$set": {'path': path}})
            return json_info
        else:
            print 'An error occurred: %s' % resp
            return json_info
    else:
        # The file doesn't have any content stored on drive
        return json_info

