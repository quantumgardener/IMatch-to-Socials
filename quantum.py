## Pre-requisites
# pip3 install Mastodon.py
import datetime
import html
import logging
import os
import re
import subprocess
import sys

from PIL import Image

from imatch_image import IMatchImage
from platform_base import PlatformController
import IMatchAPI as im
import config

MASTER_WIDTH = 800
MASTER_FORMAT = "JPEG"
MASTER_QUALITY = 85
THUMBNAIL_WIDTH = 150
THUMBNAIL_FORMAT = "WEBP"

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
        image.target_master = f'{image.media_id}_{MASTER_WIDTH}.{MASTER_FORMAT.lower()}' 
        image.target_thumbnail = f'{image.media_id}_{THUMBNAIL_WIDTH}.{THUMBNAIL_FORMAT.lower()}'
        image.target_md = os.path.join(self.api, f'{image.media_id}.md')

    def write_markdown(self, image):
        template_values = {
            'aperture' : '{0:.3g}'.format(float(image.aperture)) if image.aperture != "" else "__unknown__",
            'camera' : image.model,
            'date_taken' : image.date_time.strftime('%Y-%m-%dT%H:%M:%S'),
            'description' : f'{image.headline} {image.description.replace("\n", " ")}',
            'focal_length' : image.focal_length if image.focal_length != "" else "__unknown__",
            'image_path' : image.target_master,
            'iso' : image.iso if image.iso != "" else "__unknown__",
            'lens' : image.lens if image.lens != "" else "__unknown__",
            'location' : image.location,
            'shutter_speed' : image.shutter_speed if image.shutter_speed != "" else "__unknown__",
            'title' : image.title,
            'thumbnail' : image.target_thumbnail
        }

        # OK to overwrite this every time
        md_content = self.template_content.format(**template_values)
        md_content = html.unescape(md_content)
        ## Clean out lines with "unknown"
        lines = md_content.split("\n")
        filtered_lines = [line for line in lines if "__unknown__" not in line]
        filtered_markdown = "\n".join(filtered_lines)

        with open(image.target_md, 'w') as file:
            file.write(filtered_markdown)

    def create_master(self, image):
        # Resize image
        with Image.open(image.filename) as img:
            width, height = img.size
            aspect_ratio = height / width
            new_height = int(MASTER_WIDTH * aspect_ratio)
            img = img.resize((MASTER_WIDTH, new_height), Image.LANCZOS)
            img.save(self.full_path(image.target_master), format=MASTER_FORMAT, quality=MASTER_QUALITY)

        # Now add back XMP information
        exiftool = r"C:\Program Files\photools.com\imatch6\exiftool.exe"
        exiftool = os.path.normpath(exiftool)
        command = [
            exiftool,
            '-TagsFromFile',
            image.filename,
            '-all:all',
            '-overwrite_original',
            self.full_path(image.target_master)
        ]

        try:
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode != 0:
                logging.error(f"Error copying metadata: {result.stderr}")
                sys.exit(1)
            else:
                logging.debug("Metadata copied successfully.")
        except FileNotFoundError:
            logging.error(f"ExifTool not found at {exiftool}")
            sys.exit(1)
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            sys.exit(1)

    def create_thumbnail(self, image):
        with Image.open(image.filename) as img:
            width, height = img.size
            aspect_ratio = height / width
            new_height = int(THUMBNAIL_WIDTH * aspect_ratio)
            img = img.resize((THUMBNAIL_WIDTH, new_height), Image.LANCZOS)
            img.save(self.full_path(image.target_thumbnail), format=THUMBNAIL_FORMAT)


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

    def full_path(self, path):
        return os.path.join(self.api, path)
    
    def commit_add(self, image):
        """Make the api call to commit the image to the platform, and update IMatch with reference details"""
        try:
            self.prepare_file_information(image)
            
            if not os.path.exists(self.full_path(image.target_master)):
                # Add only if not there. We use update flags to replace an existing file
                self.create_master(image)
                self.create_thumbnail(image)

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

            if os.path.exists(self.full_path(image.target_master)):
                os.remove(self.full_path(image.target_master))
            if os.path.exists(self.full_path(image.target_thumbnail)):
                os.remove(self.full_path(image.target_thumbnail))
            if os.path.exists(self.full_path(image.target_md)):
                os.remove(self.full_path(image.target_md))

        except Exception as e:
            logging.error(f"{self.name}: An unexpected error occurred: {e}")
            sys.exit()

    def commit_update(self, image):
        """Make the api call to update the image on the platform"""
        try:
            self.prepare_file_information(image)

            if image.operation == IMatchImage.OP_UPDATE:
                if os.path.exists(self.full_path(image.target_master)):
                    os.remove(self.full_path(image.target_master))
                self.create_master(image)

                if os.path.exists(self.full_path(image.target_thumbnail)):
                    os.remove(self.full_path(image.target_thumbnail))
                self.create_thumbnail(image)


            self.write_markdown(image)

            # Update the image in IMatch by adding the attributes below.
            im.IMatchAPI().set_attributes(self.name, image.id, data = {
                'posted' : datetime.datetime.now().isoformat()[:10],
                'media_id' : image.media_id,
                'url' : f'https://quantumgardener.info/photos/{image.media_id}'
                })
        except KeyError:
            logging.error(f"{self.name}: validating an image field somewhere.")
            sys.exit()
        except Exception as e:
            logging.error(f"{self.name}: unexpected error occurred: {e}")
            sys.exit()
    

