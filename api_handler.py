import datetime
import os
import time
from concurrent.futures._base import Future  # TODO: accessing protected member...? idk it works
from concurrent.futures.thread import ThreadPoolExecutor
from math import ceil
from typing import Iterator, TypedDict

import requests
from requests import Response


# typed dict for an item in a items request json
class ItemJson(TypedDict):
    id: int
    name: str


# typed dict for buys/sells in a prices request json
class BuysSellsItemPricesJson(TypedDict):
    quantity: int
    unit_price: int


# typed dict for a prices request json
class ItemPricesJson(TypedDict):
    id: int
    whitelisted: bool
    buys: BuysSellsItemPricesJson
    sells: BuysSellsItemPricesJson


# typed dict for buys/sells in a listings request json
class BuysSellsItemListingsJson(BuysSellsItemPricesJson):
    listings: int


# typed dict for a listings request json
class ItemListingsJson(TypedDict):
    id: int
    buys: list[BuysSellsItemListingsJson]  # descending by unit_price
    sells: list[BuysSellsItemListingsJson]  # ascending by unit_price


# handler for interacting with the gw2 api
class ApiHandler:
    # some base constants
    BASE_URL: str = "https://api.guildwars2.com/v2/"
    API_KEY: str = os.getenv("api_key")
    MAX_PAGE_SIZE: int = 200
    DEFAULT_ARGS: dict[str, str] = {"lang": "en"}

    def __init__(self):
        pass

    # a basic thread to execute a single request to the api
    def _request_thread(self, path: str, args: dict[str, str]) -> requests.models.Response:
        # this will merge default args with provided args, provided args will overwrite default ones if different
        # values are specified for the same keys
        args: dict = self.DEFAULT_ARGS | args
        return requests.get(path, params=args)

    # this will execute bulk requests in threaded fashion using a ThreadPoolExecutor
    # note that an iterator over args to be used as parameters for the requests by the individual threads must be
    # provided. this iterator is used to spawn the threads. empty args are allowed.
    # the responses in the returned list are in the same order as the respective arguments provided by the iterator
    def _bulk_request(self, path: str, args_iterator: Iterator[dict]) -> list[requests.models.Response]:
        response_list: list[Response] = []
        with ThreadPoolExecutor() as executor:
            # spawn threads for individual requests
            future_list: list[Future] = [executor.submit(self._request_thread, path, args) for args in args_iterator]
            # join on each thread in order and append the responses to the return list
            for future in future_list:
                response: Response = future.result()
                if response.status_code != 200:
                    print(f"got code {response.status_code} for request with\n "
                          f"path:\n"
                          f"{path}\n"
                          f"headers:\n"
                          f"{response.headers}")
                response_list.append(response)
                # waits for the respective thread to finish
        return response_list

    # function to return a list of bulk responses with <=200 ids each given an api path and a list of id_s
    # TODO:
    #  behaviour is currently undefined if list contains invalid IDs or if requests fail due to rate limiting or
    #  other causes
    def _bulk_request_by_id_list(self, path: str, id_list: list[int]) -> list[Response]:
        args_iterator: Iterator[dict] = (
            {"ids": str(id_list[i * self.MAX_PAGE_SIZE:min((i + 1) * self.MAX_PAGE_SIZE, len(id_list))])[1:-1]}
            for i in range(ceil(len(id_list) / self.MAX_PAGE_SIZE)))
        return self._bulk_request(path, args_iterator)

    # create a new ItemListingsJson using only the first 10 buy and sell listings to eliminate computations that would
    # for the most part be false positives (namely relists instead of actual buys or sells)
    @staticmethod
    def _cut_listing(listing: ItemListingsJson) -> ItemListingsJson:
        listing_cutoff: int = 10
        return {
            "id": listing['id'],
            "buys": listing['buys'][:listing_cutoff],
            "sells": listing['sells'][:listing_cutoff]
        }

    # function to request "commerce/listings" for a list of provided id's. the returned price list follows the ordering
    # of the provided ids. if no list or an empty list is provided, an empty list is returned
    def get_item_listings_by_id_list(self, id_list: list[int] = []) -> list[ItemListingsJson]:
        path: str = self.BASE_URL + "commerce/listings"
        # get list of bulk responses, split into jsons of individual items
        return [self._cut_listing(item_listings) for response in self._bulk_request_by_id_list(path, id_list) for
                item_listings in response.json()]

    # function to request "commerce/prices" for a list of provided id's. the returned price list follows the ordering
    # of the provided ids. if no list or an empty list is provided, an empty list is returned
    def get_item_prices_by_id_list(self, id_list: list[int] = []) -> list[ItemPricesJson]:
        path: str = self.BASE_URL + "commerce/prices"
        # get list of bulk responses, split into jsons of individual items
        return [item_prices for response in self._bulk_request_by_id_list(path, id_list) for
                item_prices in response.json()]


# for testing purposes
def main():
    api_handler = ApiHandler()
    r = requests.get("https://api.guildwars2.com/v2/commerce/prices")
    old_list = api_handler.get_item_listings_by_id_list(id_list=[19700])
    oldtime = datetime.datetime.now()
    while True:
        prices_list = api_handler.get_item_listings_by_id_list(id_list=[19700])
        if old_list != prices_list:
            print(old_list)
            print(prices_list)
            print(datetime.datetime.now() - oldtime)
            oldtime = datetime.datetime.now()
            old_list = prices_list
            print(datetime.datetime.now())
        time.sleep(1)


if __name__ == '__main__':
    main()
