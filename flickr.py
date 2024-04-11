from datetime import datetime
import sys
import logging

from flickrapi import FlickrAPI
from imatch_image import IMatchImage
from IMatchAPI import IMatchAPI
from platform_base import PlatformController
import config

logging.getLogger("flickrapi.core").setLevel(logging.WARN)  # Hide basic info messages

MB_SIZE = 1048576

class FlickrImage(IMatchImage):

    __MAX_SIZE = 200 * MB_SIZE

    def __init__(self, id, platform) -> None:
        super().__init__(id, platform)

        if self.size > FlickrImage.__MAX_SIZE:
            logging.warning(f'{self.name}: {self.filename} may be too large to upload: {self.size/MB_SIZE:2.1f} MB. Max is {FlickrImage.__MAX_SIZE/MB_SIZE:2.1f} MB.')

    def prepare_for_upload(self) -> None:
        """Build variables ready for uploading."""
        super().prepare_for_upload()

        #Set up the text items

        tmp_description = [self.description]
        tmp_description.append('')

        self.albums = []
        self.groups = []

        for category in self.categories:
            splits = category['path'].split("|")
            match splits[0]:
                case "Socials":
                    if splits[1] == "flickr":
                        # Need to grab any albums and groups
                        try:
                            if splits[2] == "albums":
                                # Code is in the description
                                self.albums.append(category['description'])
                            if splits[2] == "groups":
                                # Code is in the description due to the presence of @ being illegal in the name
                                self.groups.append(category['description'])
                        except IndexError:
                            pass #no groups or albums found

        shooting_info = self.shooting_info
        if shooting_info != '':
            tmp_description.append(shooting_info)
        
        camera_info = self.camera_info
        if camera_info != '':
            tmp_description.append(camera_info)

        self.full_description = "\n".join(tmp_description)       
        return None
    
    @property
    def is_valid(self) -> bool:
        result = super().is_valid
        if self.size > FlickrImage.__MAX_SIZE:
            logging.error(f'Skipping: {self.name} is too large to upload: {self.size/MB_SIZE:2.1f} MB. Max is {FlickrImage.__MAX_SIZE/MB_SIZE:2.1f} MB.')
            self.errors.append(f"-- {self.size/MB_SIZE:2.1f} MB exceeds max {FlickrImage.__MAX_SIZE/MB_SIZE:2.1f} MB")
        return len(self.errors) == 0 and result

    @property
    def is_on_platform(self) -> bool:
        res = IMatchAPI.get_attributes("flickr", self.id)
        return len(res) != 0
    
class FlickrController(PlatformController):

    def __init__(self, platform) -> None:
        super().__init__(platform)
        self.privacy = {
            'is_public' : IMatchAPI().get_application_variable("flickr_is_public"),
            'is_family' : IMatchAPI().get_application_variable('flickr_is_family'),
            'is_friend' : IMatchAPI().get_application_variable('flickr_is_friend')
        }

    def connect(self):
        if self.api is not None:
            return
        else:
            try:
                logging.info(f"{self.name}: Connecting to platform.")
                flickr = FlickrAPI(
                    IMatchAPI().get_application_variable("flickr_apikey"),
                    IMatchAPI().get_application_variable("flickr_apisecret"),
                    cache=True
                    )
                flickr.authenticate_via_browser(
                    perms = 'delete'
                    )
                logging.info(f"{self.name}: Authenticated.")
            except Exception as ex:
                logging.error(f"{self.name}: {ex}")
                sys.exit()
            
            self.api = flickr


    def add(self):
        if len(self.images_to_add) == 0:
            return  # Nothing to see here

        if not config.TESTING:        
            self.connect()

        progress_counter = 1
        progress_end = len(self.images_to_add)
        for image in self.images_to_add:
            image.prepare_for_upload()
            if config.TESTING:
                logging.info(f"{self.name}: **TEST** Adding {image.filename} ({image.size/MB_SIZE:2.1f} MB) ({progress_counter}/{progress_end})")
                break    
            logging.info(f"{self.name}: Adding {image.filename} ({image.size/MB_SIZE:2.1f} MB) ({progress_counter}/{progress_end})")
          
            response = self.api.upload(
                image.filename,
                title = image.title if image.title != '' else image.name,
                description = image.full_description,
                is_public = self.privacy['is_public'],
                is_friend = self.privacy['is_friend'],
                is_family = self.privacy['is_family'],
                )
            
            photo_id = response.findtext('photoid')
            
            # Since we expect no EXIF data in the file, flickr will take the upload time from the last modified date of the file
            # and ignore XMP::EXIF fields. Fix that by setting the time ourselves. The format we have is 
            response = self.api.photos.setDates(photo_id=photo_id, date_taken=str(image.date_time), date_taken_granularity=0)

            for album in image.albums:
                response = self.api.photosets_addPhoto(photoset_id=album, photo_id=photo_id)

            for group in image.groups:
                response = self.api.groups_pools_add(group_id=group, photo_id=photo_id)

            # flickr will bring in hierarchical keywords not under our control as level|level|level
            # which frankly is stupid. Easiest way is to delete them all. We don't know quite what
            # it will have loaded.
            ### THIS CODE IS NOT WORKING AND I CAN"T WORK OUT WHY. Does not delete, ALWAYS returns "ok"
            # resp = self.api.photos.getInfo(photo_id = photo_id, format = "parsed-json")
            # for badtag in resp['photo']['tags']['tag']:
            #     resp = self.api.photos.removeTag(tag=badtag['id'])
            #     
            
            # Now add back the "Approved" tags. If added on upload, they combine with IPTC weirdly
            resp = self.api.photos.addTags(tags=",".join(image.keywords), photo_id=photo_id)


            # Update the image in IMatch by adding the attributes below.
            posted = datetime.now().isoformat()[:10]
            IMatchAPI().set_attributes("flickr", image.id, data = {
                'posted' : posted,
                'photo_id' : photo_id,
                'url' : f"https://www.flickr.com/photos/dcbuchan/{photo_id}"
                })
                                
            progress_counter += 1

    def delete(self):
        if len(self.images_to_delete) == 0:
            return  # Nothing to see here
        
        if not config.TESTING:
            self.connect()

        progress_counter = 1
        progress_end = len(self.images_to_delete)
        for image in self.images_to_delete:
            if config.TESTING:
                logging.info(f'{self.name}: **TEST** Deleting ({progress_counter}/{progress_end}) "{image.title}" from "{image.filename}"')
                break    
            logging.info(f'{self.name}: FAKE Deleting ({progress_counter}/{progress_end}) "{image.title}" from "{image.filename}"')

            # IMatchAPI().set_collections(
            #     collection=IMatchImage.DELETE_INDICATOR, 
            #     filelist=image.id,
            #     op = "remove")
            progress_counter += 1        

    def update(self):
        if len(self.images_to_update) == 0:
            return  # Nothing to see here
        
        if not config.TESTING:
            self.connect()

        progress_counter = 1
        progress_end = len(self.images_to_update)
        for image in self.images_to_update:
            image.prepare_for_upload()
            if config.TESTING:
                logging.info(f'{self.name}: **TEST** Updating ({progress_counter}/{progress_end}) "{image.title}" from "{image.filename}"')
                break
            logging.info(f'{self.name}: Updating ({progress_counter}/{progress_end}) "{image.title}" from "{image.filename}"')

            # response = self.api.upload(
            #     image.filename,
            #     title = image.title if image.title != '' else image.name,
            #     description = image.full_description,
            #     is_public = self.privacy['is_public'],
            #     is_friend = self.privacy['is_friend'],
            #     is_family = self.privacy['is_family'],
            #     )
            
            # photo_id = response.findtext('photoid')
            
            # # Since we expect no EXIF data in the file, flickr will take the upload time from the last modified date of the file
            # # and ignore XMP::EXIF fields. Fix that by setting the time ourselves. The format we have is 
            # response = self.api.photos.setDates(photo_id=photo_id, date_taken=str(image.date_time), date_taken_granularity=0)

            # for album in image.albums:
            #     response = self.api.photosets_addPhoto(photoset_id=album, photo_id=photo_id)

            # for group in image.groups:
            #     response = self.api.groups_pools_add(group_id=group, photo_id=photo_id)

            # # flickr will bring in hierarchical keywords not under our control as level|level|level
            # # which frankly is stupid. Easiest way is to delete them all. We don't know quite what
            # # it will have loaded.
            # ### THIS CODE IS NOT WORKING AND I CAN"T WORK OUT WHY. Does not delete, ALWAYS returns "ok"
            # # resp = self.api.photos.getInfo(photo_id = photo_id, format = "parsed-json")
            # # for badtag in resp['photo']['tags']['tag']:
            # #     resp = self.api.photos.removeTag(tag=badtag['id'])
            # #     
            
            # # Now add back the "Approved" tags. If added on upload, they combine with IPTC weirdly
            # resp = self.api.photos.addTags(tags=",".join(image.keywords), photo_id=photo_id)

            # IMatchAPI().set_collections(
            #     collection=IMatchImage.UPDATE_INDICATOR, 
            #     filelist=image.id,
            #     op = "remove")

            progress_counter += 1
