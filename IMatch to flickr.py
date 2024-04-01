#!/usr/bin/env python

# https://stuvel.eu/flickrapi-doc/


import os         # For Windows stuff
import json       # json library
import requests   # See: http://docs.python-requests.org/en/master/
import sys
from IMatchAPI import IMatchAPI, IMatchUtility
from flickrapi import FlickrAPI, FlickrError
import flickr_support
import pprint
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('requests_oauthlib').setLevel(logging.INFO)
logging.getLogger('oauthlib').setLevel(logging.INFO)
logging.getLogger("flickrapi.core").setLevel(logging.WARN)
pp = pprint.PrettyPrinter(width=120)

MB = 1048576

# ------------------------------------------------------------------------------
# Gather evertyhing we need from IMatch for local processing
im = flickr_support.getIMatchInfo()

# ------------------------------------------------------------------------------
# Connect to flickr
api = FlickrAPI(im['api'].getAppVar("flickr_apikey"), im['api'].getAppVar("flickr_apisecret"), cache=True)

api.authenticate_via_browser(perms='delete')
logging.info("flickr: Authenticated.")

flickr = flickr_support.getFlickrInfo(api, refresh=False)  # True to force reload

# ------------------------------------------------------------------------------
# Upload missing photos first

count = 1
for id in im['missing']:
    logging.info(f"Uploading: {im['data'][id]['filename']} ({im['data'][id]['size']/MB:2.1f} MB) ({count}/{len(im['missing'])})")
  
    resp = api.upload(
        im['data'][id]['filename'],
        title = im['data'][id]['title'] if im['data'][id]['title'] != '' else im['data'][id]['filename'],
        description = im['data'][id]['description'],
        is_public=1, # 0 for hidden and testing, 1 for public
        is_friend=0,
        is_family=0
    )
    from xml.etree import ElementTree as ET
    photo_id = resp.findtext('photoid')
    
    for album in im['data'][id]['albums']:
        resp = api.photosets_addPhoto(photoset_id=album, photo_id=photo_id)

    # Update the image in IMatch by adding the attributes below.
    im['api'].setAttributes("flickr", [id], data = {
        #'posted' : status['created_at'].isoformat()[:10],
        'photo_id' : photo_id,
    })
    count += 1
    

# ------------------------------------------------------------------------------
# print('Step 2: Upload photo')
# resp = flickr.upload('tests/photo.jpg', is_public=0, is_friend=0, is_family=0)


# # ------------------------------------------------------------------------------
# print('Step 3: Replace photo')
# # flickr.replace('jaguar.jpg', photo_id=photo_id)

# x = input("Waiting")

# # ------------------------------------------------------------------------------
# print('Step 4: Delete photo')
# flickr.photos.delete(photo_id=photo_id)

print( "Done." )