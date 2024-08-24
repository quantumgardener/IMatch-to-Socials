import requests
from requests.exceptions import HTTPError
import logging

import IMatchAPI as im

key = "Q4MYU6HM"

latitude = -37.572077
longitude = 143.956598

class What3Words:

    __api_key = None
    
    @classmethod
    def getAPIKey(cls) -> None:
        """Get the what3words apikey from IMatch"""

        if cls.__api_key is not None:
            pass
        else:
            logging.debug("Fetching what3words_apikey application variable")
            res = im.IMatchAPI.get_application_variable("what3words_apikey")
            cls.__api_key = res
        return cls.__api_key

    @classmethod
    def getWords(cls, latitude, longitude) -> str:
        try:
            response = requests.get(f"https://api.what3words.com/v3/convert-to-3wa?key={What3Words.getAPIKey()}&coordinates={latitude},{longitude}&language=en&format=json")
            response.raise_for_status()
        except HTTPError as http_err:
            print(f"HTTP error occurred: {http_err}")
        except Exception as err:
            print(f"Other error occurred: {err}")
        else:
            return response.json()['words']
