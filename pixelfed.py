## Pre-requisites
# pip3 install Mastodon.py

from imatch_image import IMatchImage
from platform_base import PlatformController
import mastodon
from IMatchAPI import IMatchAPI
from pprint import pprint
import sys
import logging


MB_SIZE = 1048576
TESTING = False

class PixelfedImage(IMatchImage):

    __MAX_SIZE = 15 * MB_SIZE

    def __init__(self, id, platform) -> None:
        super().__init__(id, platform)
        self.alt_text = None

    def prepare_for_upload(self) -> None:
        """Build variables ready for uploading."""
        super().prepare_for_upload()

        tmp_description = [f"{self.title} -- {self.description} (Taken {self.date_time.strftime("%#d %B %Y")})"]
        tmp_description.append('')
        if len(self.keywords) > 0:
            tmp_description.append(" ".join(["#" + keyword for keyword in self.keywords]))  # Ensure pixelfed keywords are hashtags
            tmp_description.append('')

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
        for attribute in ['headline']:
            try:
                if getattr(self, attribute).strip() == '':
                    self.errors.append(f"-- missing '{attribute}'")
            except AttributeError:
                self.errors.append(f"-- missing '{attribute}'")
        if self.size > PixelfedImage.__MAX_SIZE:
            logging.error(f'Skipping: {self.name} is too large to upload: {self.size/MB_SIZE:2.1f} MB. Max is {PixelfedImage.__MAX_SIZE/MB_SIZE:2.1f} MB.')
            self.errors.append(f"-- {self.size/MB_SIZE:2.1f} MB exceeds max {PixelfedImage.__MAX_SIZE/MB_SIZE:2.1f} MB")
        return len(self.errors) == 0 and result

    @property
    def is_on_platform(self) -> bool:
        res = IMatchAPI.get_attributes("pixelfed", self.id)
        return len(res) != 0

class PixelfedController(PlatformController):
    
    def __init__(self, platform) -> None:
        super().__init__(platform)

    def connect(self):
        if self.api is not None:
            return
        else:
            # Create a Mastodon instance. Get secrets from IMatch
            # https://www.photools.com/help/imatch/index.html#var_basics.htm
            try:
                logging.info(f"{self.name}: Connecting to platform.")
                pixelfed = mastodon.Mastodon(
                    access_token = IMatchAPI.get_application_variable("pixelfed_token"),
                    api_base_url = IMatchAPI.get_application_variable("pixelfed_url")
                )
            except mastodon.MastodonUnauthorizedError:
                logging.error(f"{self.name} unauthorised for connection.")
                sys.exit()

            # Fetch my account details. Serves as a good check of connection details
            # before bothering to upload images. If it fails here, nothing else will work.
            try:
                logging.info(f"{self.name}: Verifying pixelfed account credentials.")
                account = pixelfed.account_verify_credentials()
                logging.info(f"{self.name}: Verified. Connected to {account['url']}.")
            except mastodon.MastodonNetworkError as mne:
                logging.error(f"{self.name}: Unable to obtain account details. Check URL {IMatchAPI.get_application_variable("pixelfed_url")}.")
                print (mne)
                sys.exit()
            except mastodon.MastodonAPIError:
                logging.error(f"{self.name}: Unable to access credentials. Check token.")
                sys.exit()
            except Exception as e:
                print(f"{self.name}: An unexpected error occurred: {e}")
                sys.exit()

            ## Get the default visibility for posts. Can be one of:
            # public = Visible to everyone, shown in public timelines.
            # unlisted = Visible to public, but not included in public timelines.
            # private = Visible to followers only, and to any mentioned users.
            # direct = Visible only to mentioned users.

            self._visibility = IMatchAPI.get_application_variable("pixelfed_visibility")
            self.api = pixelfed

    def add(self):

        if len(self.images_to_add) == 0:
            return  # Nothing to see here
        
        if TESTING:
            logging.info(f'{self.name}: (TEST) Adding "{image.title}"')
            return
        
        if not TESTING:        
            self.connect()

        progress_counter = 1
        progress_end = len(self.images_to_add)
        for image in self.images_to_add:
            image.prepare_for_upload()
            try:
                # Prepare the image for attaching to the status. In Mastodon, "posts/toots" are all status
                # Upload the media, then the status with the media attached. 
                if TESTING:
                    logging.info(f"{self.name}: **TEST** Adding {image.filename} ({image.size/MB_SIZE:2.1f} MB) ({progress_counter}/{progress_end})")
                    break                            
                logging.info(f'{self.name}: Adding ({progress_counter}/{progress_end}) "{image.title}" from "{image.filename}"')
                media = self.api.media_post(  
                    media_file = image.filename,
                    description= image.headline
                )

                # Create a new status with the uploaded image                   
                status = self.api.status_post(
                    status = image.full_description,
                    media_ids = media, 
                    visibility = self._visibility
                )

                #Update the image in IMatch by adding the attributes below.
                IMatchAPI().set_attributes("pixelfed", image.id, data = {
                    'posted' : status['created_at'].isoformat()[:10],
                    'media_id' : media['id'],
                    'status_id' : status['id'],
                    'url' : status['url']
                    })
            except KeyError:
                logging.error(f"{self.name}: Missed validating an image field somewhere.")
                sys.exit()
            except mastodon.MastodonAPIError as mae:
                logging.error(f"{self.name}: An API error occurred: {mae}.")
                sys.exit()
            except Exception as e:
                logging.error(f"{self.name}: An unexpected error occurred: {e}")
                sys.exit()
            progress_counter += 1


    def delete(self):
        if len(self.images_to_delete) == 0:
            return  # Nothing to see here
        
        if not TESTING:
            self.connect()

        progress_counter = 1
        progress_end = len(self.images_to_delete)
        for image in self.images_to_delete:
            try:
                attributes = IMatchAPI().get_attributes("pixelfed", image.id)
                status_id = attributes[0]['data'][0]['status_id']
                if TESTING:
                    logging.info(f'{self.name}: **TEST** Deleting ({progress_counter}/{progress_end}) "{image.title}" status id: {status_id}')
                    break    
                logging.info(f'{self.name}: Deleting ({progress_counter}/{progress_end}) "{image.title}" status id: {status_id}')

                # Update the status with new text
                status = self.api.status_delete(
                    id = status_id,
                )

                # Clear the update flag in IMatch. It doesn't matter that
                # another PlatformController may have already done this because
                # we pre-load all controllers before getting here. 
                # IMatchAPI().set_collections(
                #     collection=IMatchImage.DELETE_INDICATOR, 
                #     filelist=image.id,
                #     op = "remove")
            except KeyError:
                logging.error(f"{self.name}: Missed validating an image field somewhere.")
                sys.exit()
            except mastodon.MastodonAPIError as mae:
                logging.error(f"{self.name}: An API error occurred: {mae}.")
                sys.exit()
            except Exception as e:
                logging.error(f"{self.name}: An unexpected error occurred: {e}")
                sys.exit()
            progress_counter += 1       

    def update(self):
        if len(self.images_to_update) == 0:
            return  # Nothing to see here
        
        if not TESTING:
            self.connect()

        progress_counter = 1
        progress_end = len(self.images_to_update)
        for image in self.images_to_update:
            image.prepare_for_upload()
            try:


                # Prepare the image for attaching to the status. In Mastodon, "posts/toots" are all status
                # Upload the media, then the status with the media attached. 
                attributes = IMatchAPI().get_attributes("pixelfed", image.id)
                media_id = attributes[0]['data'][0]['media_id']
                status_id = attributes[0]['data'][0]['status_id']
                if TESTING:
                    logging.info(f'{self.name}: **TEST** Updating ({progress_counter}/{progress_end}) "{image.title}" status_id: {status_id}')
                    break
                logging.info(f'{self.name}: Updating ({progress_counter}/{progress_end}) "{image.title}" status_id: {status_id}')
                media = self.api.media_update(
                    id = media_id,  
                    description= image.headline
                )

                # Update the status with new text
                status = self.api.status_update(
                    id = status_id,
                    status = image.full_description,
                    media_ids = media, 
                )

                # Clear the update flag in IMatch. It doesn't matter that
                # another PlatformController may have already done this because
                # we pre-load all controllers before getting here. 
                IMatchAPI().set_collections(
                    collection=IMatchImage.UPDATE_INDICATOR, 
                    filelist=image.id,
                    op = "remove")
            except KeyError:
                logging.error(f"{self.name}: validating an image field somewhere.")
                sys.exit()
            except mastodon.MastodonAPIError as mae:
                logging.error(f"{self.name}: API error occurred: {mae}.")
                sys.exit()
            except Exception as e:
                logging.error(f"{self.name}: unexpected error occurred: {e}")
                sys.exit()
            progress_counter += 1       

