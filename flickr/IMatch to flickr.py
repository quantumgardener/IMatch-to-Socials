#!/usr/bin/env python

# https://stuvel.eu/flickrapi-doc/


import os         # For Windows stuff
import json       # json library
import requests   # See: http://docs.python-requests.org/en/master/
import sys
from api.IMatchAPI import IMatchAPI, IMatchUtility
from flickrapi import FlickrAPI, FlickrError
from datetime import datetime
import flickr.flickr_support as flickr_support
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

flickr = flickr_support.getFlickrInfo(api, refresh=False, albums=im['albums'], groups=im['groups'])  # True to force reload

pp.pprint(flickr)
# ------------------------------------------------------------------------------
# Upload missing photos first

count = 1
for id in im['missing']:
    image = im['data'][id]
    logging.info(f"Uploading: {image['filename']} ({image['size']/MB:2.1f} MB) ({count}/{len(im['missing'])})")

    pp.pprint(image)
  
    resp = api.upload(
        image['filename'],
        title = image['title'] if image['title'] != '' else image['filename'].split("/")[-1:],
        description = image['description'],
        is_public=0, # 0 for hidden and testing, 1 for public
        is_friend=0,
        is_family=0
    )
    from xml.etree import ElementTree as ET
    photo_id = resp.findtext('photoid')
    
    for album in image['albums']:
        resp = api.photosets_addPhoto(photoset_id=album, photo_id=photo_id)

    for group in image['groups']:
        resp = api.groups_pools_add(group_id=group, photo_id=photo_id)

    # flickr will bring in hierarchical keywords not under our control as level|level|level
    # which frankly is stupid. Easiest way is to delete them all. We don't know quite what
    # it will have loaded.
    resp = api.photos.getInfo(photo_id = photo_id, format = "parsed-json")
    for badtag in resp['photo']['tags']['tag']:
        resp = api.photos.removeTag(tag=badtag['id'], format="parsed-json")
    
    # Now add back the "Approved" tags
    resp = api.photos.addTags(tags=",".join(image['keywords']), photo_id=photo_id)

    # ---------------------------------------------------------------------------------
    # Start the clean up now
        
    # Update the image in IMatch by adding the attributes below.
    posted = datetime.now().isoformat()[:10]
    im['api'].setAttributes("flickr", [id], data = {
        'posted' : posted,
        'photo_id' : photo_id,
        'url' : f"https://www.flickr.com/photos/dcbuchan/{photo_id}"
    })

    # Add image into the flickr construct for caching next time.
    flickr['data']["{photo_id}"] = {
        "title"  : im['data'][id]['title'],
        "albums" : im['data'][id]['albums'],
        "groups" : im['data'][id]['groups'],
        "posted" : posted
    }
    flickr_support.saveFlickrInfo(flickr)

    count += 1



# # ------------------------------------------------------------------------------
# print('Step 3: Replace photo')
# # flickr.replace('jaguar.jpg', photo_id=photo_id)

# x = input("Waiting")

# # ------------------------------------------------------------------------------
# print('Step 4: Delete photo')
# flickr.photos.delete(photo_id=photo_id)

print( "Done." )