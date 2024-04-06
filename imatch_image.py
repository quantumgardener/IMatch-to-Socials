from IMatchAPI import IMatchAPI
from pprint import pprint
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO) # Don't want this debug level to cloud ours

COLLECTION_WRITE_BACK_PENDING = 5
COLLECTION_FLAGS_SET = 11           # Checquered flag
COLLECTION_FLAGS_UNSET = 12         # Red flag
MB_SIZE = 1048576

class IMatchImage():

    def __init__(self, id) -> None:
        self.id = id
        self.errors = []    # hold any errors raised during the process
        self._controller = None
        
        # -----------------------------------------------------------------------------
        # Now begins the process of collating the information to be posted alongside 
        # the image itself. This is the information we want from the version to be be 
        # posted, and later the master. Certain camera and shooting information is not
        # propogated through the versions, so we will need to walk back up the version
        # > master tree to obtain it.
        params = {
            "fields"           : "filename,name,size",
            }
        
        image_info = IMatchAPI().get_file_metadata([self.id], params=params)[0]
        try:
            for attribute in image_info.keys():
                # fileName is a special case. Ask for filename, get fileName in results
                if attribute == "fileName":
                    setattr(self, 'filename', image_info[attribute])
                else:      
                    setattr(self, attribute, image_info[attribute])  
        except KeyError:
            print(f"Attribute {attribute} not returned from get_file_metadata() call")
            sys.exit()

        # Now grab the information from the master. This also protects us if the
        # metadata has not yet been propogated.
        master_params = {
            "fields" : "", # Setting to "" stops retrieval of more than we need
            "tagtitle" : "title",
            "tagdescription" : "description",
            "taghierarchical_keywords" : "hierarchicalkeywords",
            "varaperture" : "{File.MD.aperture}",
            "varfocal_length" : "{File.MD.focallength|value:formatted}",
            "varheadline" : "{File.MD.headline}",
            "variso" : "{File.MD.iso|value:formatted}", 
            "varlens" : "{File.MD.lens}",
            "varmodel" : "{File.MD.model}",
            "varshutter_speed" : "{File.MD.shutterspeed|value:formatted}"   
            }

        self.master_id = IMatchAPI().get_master_id(self.id)
        if self.master_id == None:
            # We are the master, use original id
            self.master_id = id
        image_info = IMatchAPI().get_file_metadata([self.master_id],master_params)[0]
        try:
            for attribute in image_info.keys():
                setattr(self, attribute, image_info[attribute])  # remove prefix for our purposes
        except KeyError:
            print(f"Attribute {attribute} not returned from get_file_metadata() call")
            sys.exit()
        
        # Retrieve the list of categories the image belongs to.
        self.categories = IMatchAPI().get_file_categories([self.id], params={'fields' : 'path,description'})[self.id]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(id: {self.id}, filename: {self.filename}, size: {self.size})"

    def __str__(self) -> str:
        return f"I'm a {type(self).__name__}"
    
    def prepare_for_upload(self) -> None:
        # print(f"prepare_for_upload() not implemented for {type(self).__name__}")
        # raise NotImplementedError
        """Build variables ready for uploading."""
        self.keywords = []  # These are the keywords to output. self.hierachy_keywords is what comes in
        for keyword in self.hierarchical_keywords:
            splits = keyword.split("|")
            match splits[0]:
                case 'genre':
                    # Genre is tagged with itself and with "photography appended"
                    for genre in splits[1:]:
                        self.keywords.append(genre)
                        if genre != 'astrophotography':
                            self.add_keyword(genre+"photography")
                case 'Location':
                    try:
                        self.add_keyword(splits[3]) # town
                        self.add_keyword(splits[4]) # location
                    except IndexError:
                        pass
                case 'nature':
                    for nature in splits[1:]:
                        self.add_keyword(nature) # Get the leaf

        # Add certain categories as keywords
        for categories in self.categories:
            splits = categories['path'].split("|")
            match splits[0]:
                case 'Image Characteristics':
                    self.add_keyword(splits.pop()) # Get the leaf

    def add_keyword(self, keyword) -> str:
        """Ensure all keywords are added without spaces"""
        no_spaces_keyword = keyword.replace(" ","")
        self.keywords.append(no_spaces_keyword)
        return no_spaces_keyword
    
    @property
    def is_master(self) -> bool:
        return self.id == self.master_id
    
    @property
    def is_version(self) -> bool:
        return not self.is_master()
    
    def list_errors(self) -> None:
        print(f"Errors were found with {type(self).__name__}(name: {self.name}). Please update the master file's metadata.")
        IMatchAPI().set_collections(IMatchAPI.COLLECTION_DOTS_RED, self.id)
        for error in self.errors:
            print(error)

    @property
    def is_on_platform(self) -> bool:
        raise NotImplementedError("Subclasses must implement is_on_platform()")

    @property
    def camera_info(self) -> str:
        """Standardise a basic way of presenting camera information on a single line"""
        camera_info = []
        try:
            match self.model:
                case "UltraFractal":
                    camera_info.append("Digital image generated in Ultrafractal.")
                case "ScanSnap S1300":
                    camera_info.append("Digitised from a print scanned using a Fujitsu ScanSnap S1300.")
                case other:
                    camera_info.append(self.model)
        except AttributeError:
            pass
        if self.lens.strip() != '':
            camera_info.append(self.lens)

        return " | ".join(camera_info) if len(camera_info) > 0 else ''

    @property
    def shooting_info(self) -> str:
        """Standardise a basic way of presenting shooting information on a single line"""
        shooting_info = []

        try:
            if self.iso != '':
                shooting_info.append(f"ISO {self.iso}")
        except AttributeError:
            pass

        try:
            if self.shutter_speed != '':
                shooting_info.append(f"{self.shutter_speed} sec")
        except AttributeError:
            pass

        try:
            shooting_info.append('f/{0:.3g}'.format(float(self.aperture)))
        except (AttributeError, ValueError):
            pass

        try:
            shooting_info.append(f"{self.focal_length}") 
        except AttributeError:
            pass
           
        return " | ".join(shooting_info) if len(shooting_info) > 0 else ''

    @property
    def is_final(self) -> bool:
        return COLLECTION_FLAGS_SET in IMatchAPI().file_collections(self.id)
    
    @property
    def is_valid(self) -> bool:
        raise NotImplementedError("Subclasses should implement this for their platform's needs")

    @property
    def controller(self):
        if self._controller is None:
            raise ValueError ("Controller has not been set")
        else:
            return self._controller

    @controller.setter
    def controller(self, controller):
        self._controller = controller
        
        
        

