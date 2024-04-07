import os         # For Windows stuff
import json       # json library
import requests   # See: http://docs.python-requests.org/en/master/
from pprint import pprint
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger('urllib3').setLevel(logging.INFO) # Don't want this debug level to cloud ours


## Utility class to make the main IMatchAPI class a little less complex
class IMatchUtility:

    @classmethod
    def file_id_list(cls, fileids):
        """ Turn a list of file id numbers into a string for passing to a function """
        return ",".join(map(str, fileids))

    @classmethod       
    def getID(cls, x):
        """ Pull the file id from a {} record where ID is a field"""
        return x['id']

    @classmethod
    def listIDs(cls, x):
        """ Given a list of items where one record in the field is ID, return the list of IDs"""
        return list(map(cls.getID, x))
    

class IMatchAPI:
    """Connect to an active IMatch database. Implemented as a Singleton Design pattern."""
    COLLECTION_WRITE_BACK_PENDING = 5
    COLLECTION_BOOKMARKS = 2
    COLLECTION_FLAGS = 10
    COLLECTION_FLAGS_SET = 11               # Checquered flag
    COLLECTION_FLAGS_UNSET = 12             # Red flag
    COLLECTION_FLAGS_NONE = 13
    COLLECTION_DOTS = 30
    COLLECTION_DOTS_RED = 31
    COLLECTION_DOTS_GREEN = 32
    COLLECTION_DOTS_BLUE = 33
    COLLECTION_DOTS_NONE = 34
    COLLECTION_PINS = 50
    COLLECTION_PINS_RED = 51
    COLLECTION_PINS_GREEN = 52
    COLLECTION_PINS_BLUE = 53
    COLLECTION_PINS_NONE = 54
    REQUEST_TIMEOUT = 10                    # Request timeout in seconds

    __auth_token = None # This stores the IMWS authentication token after authenticate() has been called
    __host_url = None
    collection_values = {
        COLLECTION_FLAGS : "Flags",
        COLLECTION_FLAGS_SET : "Flags|Set",
        COLLECTION_FLAGS_UNSET : "Flags|Unset",
        COLLECTION_FLAGS_NONE : "Flags|None",
        COLLECTION_DOTS : "Dots",
        COLLECTION_DOTS_RED : "Dots|Red",
        COLLECTION_DOTS_GREEN : "Dots|Green",
        COLLECTION_DOTS_BLUE : "Dots|Blue",
        COLLECTION_DOTS_NONE : "Dots|None",
        COLLECTION_PINS : "Pins",
        COLLECTION_PINS_RED : "Pins|Red",
        COLLECTION_PINS_GREEN : "Pins|Green",
        COLLECTION_PINS_BLUE : "Pins|Blue",
        COLLECTION_PINS_NONE : "Pins|None",
        }   

    def __init__(self, host_port=50519) -> None:
        """ Authenticate against IMWS and set the __auth_token variable
            to the returned authentication token. We need this for all other endpoints. """
        if IMatchAPI.__auth_token is not None:
            pass
        else:
            # We need to connect to IMatch
            IMatchAPI.__host_url = f"http://127.0.0.1:{host_port}"

            try:
                logging.info(f"IMatchAPI: Attempting connection to IMatch on port {host_port}")
                req = requests.post(IMatchAPI.__host_url + '/v1/authenticate', params={
                    'id': os.getlogin(),
                    'password': '',
                    'appid': ''},
                    timeout=IMatchAPI.REQUEST_TIMEOUT)

                response = json.loads(req.text)

                # If we're OK, store the auth_token in the global variable
                if req.status_code == requests.codes.ok:
                    IMatchAPI.__auth_token = response["auth_token"]
                else:
                    # Raise the exception matching the HTTP status code
                    req.raise_for_status()

                logging.info(f"IMatchAPI: Authenticated to {IMatchAPI.__host_url}")
                return
            except requests.exceptions.ConnectionError as ce:
                logging.info(f"IMatchAPI: Unable to connect to IMatch on port {host_port}. Please check IMatch is running and the port is correct.\n\nThe full error was {ce}")
                sys.exit()
            except requests.exceptions.RequestException as re:
                print(re)
                sys.exit()
            except Exception as ex:
                print(ex)
                sys.exit()

    @classmethod
    def get_imatch(cls, endpoint, params):
        """ Generic get function to IMatch. Other functions call this so there is no need for them to repeat
         the main control loop. Ensures the auth_token is not missed as a parameter. """

        params['auth_token'] = cls.__auth_token

        # Easy to miss the leading / so add it as a courtesy
        if endpoint[:1] != "/":
            endpoint = "/" + endpoint

        try:
            req = requests.get(IMatchAPI.__host_url + endpoint, params, timeout=cls.REQUEST_TIMEOUT)
            response = json.loads(req.text)
            if req.status_code == requests.codes.ok:
                return response
            else:
                req.raise_for_status()
        except requests.exceptions.RequestException as re:
            print(re)
            print(response)
        except Exception as ex:
            print(ex)

    @classmethod
    def post_imatch(cls, endpoint, params):
        """ Generic post function to IMatch. Other functions call this so there is no need for them to repeat
         the main control loop. Ensures the auth_token is not missed as a parameter. """

        params['auth_token'] = cls.__auth_token

        # Easy to miss the leading / so add it as a courtesy
        if endpoint[:1] != "/":
            endpoint = "/" + endpoint

        try:
            req = requests.post(cls.__host_url + endpoint, params, timeout=cls.REQUEST_TIMEOUT)
            response = json.loads(req.text)
            if req.status_code == requests.codes.ok:
                return response
            else:
                req.raise_for_status()
            return
        except requests.exceptions.RequestException as re:
            print(re)
            print(response)
        except Exception as ex:
            print(ex)

    @classmethod
    def get_application_variable(cls, variable):
        """ Retrieve the named application variable from IMatch (Edit|Preferences|Variables)"""
        params = {}
        params['name'] = variable

        response = cls.get_imatch( '/v1/imatch/appvar', params)
        return response['value']

    @classmethod
    def get_attributes(cls, set, id, params={}):
        """ Return all attributes for a list of file ids. filelist is an array. """

        params['set'] = set
        params['id'] = f"{id}"

        logging.debug(f"Retreivving attributes for {params['id']}")
        response = cls.get_imatch( '/v1/attributes', params)

        # Strip away the wrapping from the result
        results = []
        for attributes in response['result']:
            logging.debug(attributes)
            results.append(attributes)
        logging.debug(f"{len(results)} attribute instances retrieved.")
        return results

    @classmethod
    def get_files_in_category(cls, path):
        """ Return the requested information all files in the specified category """

        params={}
        params['path'] = path
        params['fields'] = 'files'

        logging.debug(f'Retrieving list of files in the {path} category.')
        response = cls.get_imatch( '/v1/categories', params)
        if len(response['categories']) == 0:
            logging.debug("0 files found.")
            return []
        else:
            # Get straight to the data if present
            logging.debug(f"{len(response['categories'][0]['files'])} files found.")
            return response['categories'][0]['files']

    @classmethod
    def get_file_categories(cls, filelist, params={}):
        """ Return the categories for the list of files """

        params['id'] = IMatchUtility().file_id_list(filelist)

        response = cls.get_imatch( '/v1/files/categories', params)
        results = {}
        for file in response['files']:
            logging.debug(file)
            results[file['id']] = file['categories']
        logging.debug(f"{len(results)} images with categories.")
        return results

    @classmethod
    def get_file_metadata(cls, filelist, params={}):
        """ Return details list of file ids """

        params['id'] = IMatchUtility().file_id_list(filelist)
        response = cls.get_imatch( '/v1/files', params)
        return response['files']
    
    @classmethod
    def get_master_id(cls, id):
        """ Return the number of the master if one exists """

        params = {}
        params["id"] = id
        params["type"] = "masters"

        response = cls.get_imatch( '/v1/files/relations', params)

        if len(response['files'][0]['masters']) == 1:
            return response['files'][0]['masters'][0]['files'][0]['id']
        else:
            return None


    @classmethod
    def files_for_selection(cls, params={'fields': 'id,filename'}):
        """ Return the requested information all selected files in the active file window. """

        params['idlist'] = '@imatch.filewindow.active.selection'
        response = cls.get_imatch("/v1/files", params)
        return response['files']
 

    @classmethod
    def list_file_names(cls):
        """ Print the id and name of all selected files in the active file window. """

        try:
            req = requests.get(cls.hostURL + '/v1/files', params={
            'auth_token': cls.token(),
            'idlist': '@imatch.filewindow.active.selection',
            'fields': 'id,filename'
            }, timeout=cls.REQUEST_TIMEOUT)

            response = json.loads(req.text)

            if req.status_code == requests.codes.ok:
                print(response['files'])
                for f in response['files']:
                    print(f['id'],' ',f['fileName'])
            else:
                req.raise_for_status()
            return
        except requests.exceptions.RequestException as re:
            print(re)
            print(response)
        except Exception as ex:
            print(ex)

    @classmethod
    def file_collections(cls, image_id) -> bool:
        """ Returns the collections a file belongs to """

        params = {}
        params["id"] = image_id

        try:       
            response = cls.get_imatch( '/v1/files/collections', params)
            return response['files'][0]['collections']
        except requests.exceptions.RequestException as re:
            print(re)
            print(response)
        except Exception as ex:
            print(ex)

    @classmethod
    def set_attributes(cls, set, id, params={}, data={}):
        """ Set attributes for image with id. Assumes attributes only exist once. Will either add or update as needed.
         (modification required if multiple instances of attribute sets are to be managed) """

        params['set'] = set
        params['id'] = f"{id}"

        # Can neither assume no attribute instance, or an existing attribute instance. 
        # Check first

        if len(cls.get_attributes(set, id)) == 0:
            # No existing attributes, do an add
            op = 'add'
            logging.debug("Adding attribute row.")
        else:
            op = 'update'
            logging.debug("Updating existing attribute row.")

        tasks = [{
            'op' : op,
            'instanceid': [1],
            'data' : data
        }]

        params['tasks'] = json.dumps(tasks)  # Necessary to stringify the tasks array before sending

        logging.debug(f"Sending instructions : {params}")

        response = cls.post_imatch( '/v1/attributes', params)

        if response['result'] == "ok":
            logging.debug("Success")
        else:
            logging.error("There was an error updating attributes.")
            pprint(response)
            sys.exit()

    @classmethod
    def set_collections(cls, collection, filelist, op="add", params={}):
        """ Set collections for files."""
        if isinstance(collection, int):
            path = cls.collection_values[collection]
        else:
            path = collection

        if isinstance(filelist, list):
            params['id'] = IMatchUtility().file_id_list(filelist)
        else:
            if isinstance(filelist, int):
                params['id'] = f"{filelist}"
            else:
                raise TypeError("Filelist argument must be single integer or list of integers.")      
            
        tasks = [{
            'op' : op,
            'path' : path
        }]

        params['tasks'] = json.dumps(tasks)  # Necessary to stringify the tasks array before sending

        response = cls.post_imatch( '/v1/collections', params)
        if response is not None:
            if response['result'] == "ok":
                logging.debug("Success")
                return
        else:
            print("There was an error updating the collection. Please see message above.")
            sys.exit()
