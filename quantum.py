## Pre-requisites
# pip3 install Mastodon.py
import datetime
import logging
import os
import re
import shutil
import sys

from imatch_image import IMatchImage
from platform_base import PlatformController
import IMatchAPI as im
import config

class QuantumImage(IMatchImage):

    __MAX_SIZE = 25 * config.MB_SIZE

    def __init__(self, id, platform) -> None:
        super().__init__(id, platform)
        self.alt_text = None

    def prepare_for_upload(self) -> None:
        """Build variables ready for uploading."""
        super().prepare_for_upload()

        # Remove spaces from keywords
        self.keywords = [item.replace(" ","") for item in self.keywords]
        self.keywords = [item.replace("-","") for item in self.keywords]
        self.keywords.append("photography")

        if self.circadatecreated != "":
            circa = "ca. "
        else:
            circa = ""
        tmp_description = [f"{self.title} -- {self.headline} (Taken {circa}{self.date_time.strftime("%#d %B %Y")})"]
        tmp_description.append('')
        if len(self.keywords) > 0:
            tmp_description.append(" ".join(["#" + keyword for keyword in self.keywords]))  # Ensure keywords are hashtags
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
        for attribute in []:
            try:
                if getattr(self, attribute).strip() == '':
                    self.errors.append(f"missing {attribute}")
            except AttributeError:
                self.errors.append(f"missing {attribute}")
        if self.size > QuantumImage.__MAX_SIZE:
            self.errors.append(f"file too large")
        return len(self.errors) == 0 and result

    @property
    def is_on_platform(self) -> bool:
        res = im.IMatchAPI.get_attributes("quantum", self.id)
        return len(res) != 0

class QuantumController(PlatformController):
    
    def __init__(self, platform) -> None:
        super().__init__(platform)
        self.preferred_format = im.IMatchAPI.FORMAT_WEBP
        self.allowed_formats = [im.IMatchAPI.FORMAT_WEBP, im.IMatchAPI.FORMAT_JPEG]
        self.template_content = None

    def prepare_file_information(self, image):
        """Gather information in a consitent format for writing files and add to image"""
        match = re.search(r'\[(\d+)\]', image.filename)
        if not match:
            raise ValueError(f'{self.name}: Unable to extract digits from filename')
        image.media_id = match.group(1)
        image.short_filename = f'{image.media_id}.{image.format.lower()}'
        image.target_filename = os.path.join(self.api, image.short_filename)
        image.target_md = os.path.join(self.api,f'{image.media_id}.md')
        logging.debug(f'{self.name}: Target file is {image.target_filename}')

    def write_markdown(self, image):
        template_values = {
            'aperture' : '{0:.3g}'.format(float(image.aperture)),
            'camera' : image.model,
            'date_taken' : image.date_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'description' : f'{image.headline} {image.description}',
            'focal_length' : image.focal_length,
            'image_path' : image.short_filename,
            'iso' : image.iso,
            'lens' : image.lens,
            'location' : image.location,
            'shutter_speed' : image.shutter_speed,
            'title' : image.title,
        }

        # OK to overwrite this every time
        md_content = self.template_content.format(**template_values)
        with open(image.target_md, 'w') as file:
            file.write(md_content)

    def connect(self):
        if self.api is not None:
            return
        else:
            # Not sure what we return here, but check for the existence of the file path
            quantum_path = im.IMatchAPI.get_application_variable("quantum_path")
            if os.path.exists(quantum_path) and os.path.isdir(quantum_path):
                logging.debug(f'{self.name}: Connected. Path is {quantum_path}')
                self.api = quantum_path

                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'quantum.md'), 'r') as file:
                    self.template_content = file.read()

            else:
                raise FileNotFoundError(f'Connection error: {quantum_path} not found.')

    def commit_add(self, image):
        """Make the api call to commit the image to the platform, and update IMatch with reference details"""
        try:
            self.prepare_file_information(image)
            
            if not os.path.exists(image.target_filename):
                # Add only if not there. We use update flags to replace an existing file
                shutil.copy(image.filename, image.target_filename)

            self.write_markdown(image)
            
            # Update the image in IMatch by adding the attributes below.
            im.IMatchAPI().set_attributes(self.name, image.id, data = {
                'posted' : datetime.datetime.now().isoformat()[:10],
                'media_id' : image.media_id,
                'url' : f'https://quantumgardener.info/photos/{image.media_id}'
                })
        except KeyError:
            logging.error(f"{self.name}: Missed validating an image field somewhere.")
            sys.exit()
        except Exception as e:
            logging.error(f"{self.name}: An unexpected error occurred: {e}")
            sys.exit()

    def commit_delete(self, image):
        """Make the api call to delete the image from the platform. We assume the file is not linked anywhere else."""
        try:
            self.prepare_file_information(image)

            if os.path.exists(image.target_filename):
                os.remove(image.target_filename)
            if os.path.exists(image.target_md):
                os.remove(image.target_md)

        except Exception as e:
            logging.error(f"{self.name}: An unexpected error occurred: {e}")
            sys.exit()

    def commit_update(self, image):
        """Make the api call to update the image on the platform"""
        try:
            self.prepare_file_information(image)
            
            shutil.copy(image.filename, image.target_filename)

            self.write_markdown(image)
        except KeyError:
            logging.error(f"{self.name}: validating an image field somewhere.")
            sys.exit()
        except Exception as e:
            logging.error(f"{self.name}: unexpected error occurred: {e}")
            sys.exit()
    

