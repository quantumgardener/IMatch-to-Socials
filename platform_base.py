from imatch_image import IMatchImage
from pprint import pprint
import logging


class PlatformController():

    def __init__(self) -> None:
        self.images = set()
        self.images_to_add = set()
        self.images_to_delete = set()
        self.images_to_update = set()
        self.invalid_images = set()
        self.api = None  # Holds the platform api connection once active
        self.logname = "x"

    def connect(self):
        """Upload and add image to platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def add_image(self, image):
        image.controller = self
        self.images.add(image)
      
    def add(self):
        """Upload and add image to platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def classify_images(self):
        for image in self.images:
            match image.operation:
                case IMatchImage.OP_ADD:
                    self.images_to_add.add(image)
                case IMatchImage.OP_UPDATE:
                    self.images_to_update.add(image)
                case IMatchImage.OP_DELETE:
                    self.images_to_delete.add(image)
                case IMatchImage.OP_INVALID:
                    self.invalid_images.add(image)
                case other:
                    pass

    def delete(self):
        """Delete image from platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def list_errors(self):
        """List information about all images that are invalid and were not processed"""
        if len(self.invalid_images) > 0:
            logging.error( "--------------------------------------------------------------------------------------")
            logging.error(f"{self.logname}: The following images had errors are were tagged invalid for processing.")
            for image in sorted(self.invalid_images, key=lambda x: x.name):
                logging.error(image.name)
                for error in image.errors:
                    logging.error(error)

    def summarise(self):
        """Output summary of images processed"""
        stats = self.stats
        logging.info( "--------------------------------------------------------------------------------------")
        logging.info(f"{self.logname}: Summary of images processed")
        for val in stats.keys():
            logging.info(f"-- {stats[val]} {val} images")

    def update(self):
        """Update image on platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")   

    @property
    def stats(self):
        return {
            "total" : len(self.images),
            "added" : len(self.images_to_add),
            "deleted" : len(self.images_to_delete),
            "updated" : len(self.images_to_update),
            "invalid" : len(self.invalid_images),
            "ignored" : len(self.images)
                        - len(self.images_to_add)
                        - len(self.images_to_delete)
                        - len(self.images_to_update)
                        - len(self.invalid_images)
        }