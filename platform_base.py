from imatch_image import IMatchImage
from pprint import pprint
import logging
logging.basicConfig(level=logging.INFO)

class PlatformController():

    def __init__(self) -> None:
        self.images = set()
        self.images_to_add = set()
        self.images_to_delete = set()
        self.images_to_update = set()
        self.invalid_images = set()
        self.api = None  # Holds the platform api connection once active

    def connect(self):
        """Upload and add image to platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def add_image(self, image):
        image.controller = self
        self.images.add(image)
      
    def add(self):
        """Upload and add image to platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def delete(self):
        """Delete image from platform"""
        raise NotImplementedError("Subclasses must implement this for their specific platnform.")

    def update(self):
        """Update image on platform"""
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

    @property
    def stats(self):
        return {
            "platform" : type(self).__name__,
            "total" : len(self.images),
            "adds" : len(self.images_to_add),
            "deletes" : len(self.images_to_delete),
            "updates" : len(self.images_to_update),
            "invalid" : len(self.invalid_images),
            "ignores" : len(self.images)
                        - len(self.images_to_add)
                        - len(self.images_to_delete)
                        - len(self.images_to_update)
                        - len(self.invalid_images)
        }