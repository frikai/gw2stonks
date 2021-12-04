import os
import time
from concurrent.futures import Future
from concurrent.futures.thread import ThreadPoolExecutor
from math import ceil
from typing import TypedDict

import requests
from requests import Response


class ItemJson(TypedDict):
    """typed dict to represent a simplified api response to a /items request"""

    id: int
    name: str
    vendor_value: int


class BuysSellsItemPricesJson(TypedDict):
    """typed dict to represent a buys/sells value in an api response to a /prices request"""

    quantity: int
    unit_price: int


class ItemPricesJson(TypedDict):
    """typed dict to represent an api response to a /prices request"""

    id: int
    buys: BuysSellsItemPricesJson
    sells: BuysSellsItemPricesJson


class BuysSellsItemListingsJson(BuysSellsItemPricesJson):
    """typed dict to represent a buys/sells value in an api response to a /listings request"""

    listings: int


class ItemListingsJson(TypedDict):
    """typed dict to represent an api response to a /listings request"""

    id: int
    buys: list[BuysSellsItemListingsJson]  # descending by unit_price
    sells: list[BuysSellsItemListingsJson]  # ascending by unit_price


class ApiHandler(object):
    """handler for interacting with the gw2 api. executes bulk request in threaded fashion"""

    # some base constants
    BASE_URL: str = "https://api.guildwars2.com/v2/"
    API_KEY: str = os.getenv("api_key")
    MAX_PAGE_SIZE: int = 200
    DEFAULT_ARGS: dict[str, str] = {"lang": "en"}
    REFRESH_TIME: int = 120  # refresh all api data every x seconds (must be initiated externally)
    MAX_RETRY_COUNT: int = 10

    def _request_thread(self, path: str, args: dict[str, str]) -> requests.models.Response:
        """a basic thread to execute a single request to the api. is used by _bulk_request"""

        # merge default args with provided args. provided args will overwrite default ones if different
        # values are specified for the same keys
        args: dict = self.DEFAULT_ARGS | args
        return requests.get(path, params=args)

    def _bulk_request(self, path: str, arg_list: list[dict]) -> list[requests.models.Response]:
        # see <_bulk_request_by_id_list>
        # TODO: make status code handling more robust
        assert len(arg_list) <= self.MAX_PAGE_SIZE

        response_list: list[Response] = []

        with ThreadPoolExecutor() as executor:
            # number of retries before we fall back onto Null
            max_try_count: int = self.MAX_RETRY_COUNT

            # spawn threads for individual requests
            future_list: list[Future] = [executor.submit(self._request_thread, path, args) for args in arg_list]

            # join on each thread in order and append the responses to the return list
            for j in range(len(future_list)):
                success: bool = False
                future = future_list[j]
                response: Response = future.result()
                try_count: int = 0
                while not success and try_count < max_try_count:
                    if try_count > 0:
                        # previous response has been deemed invalid
                        print("sending request again...")
                        response = executor.submit(self._request_thread, path, arg_list[j]).result()

                    if response.status_code in [500, 504, 429]:
                        # Timeout errors for the most part
                        print(f"got status code {response.status_code}. Will try to repeat the request")
                        if response.status_code == 429:
                            # Too Many Requests. Wait 30s before retrying, should be enough for 600/min rate-limiting.
                            time.sleep(30)
                        else:
                            # give the server a bit of time to get things in order
                            time.sleep(5)

                    elif response.status_code == 206:
                        # sometimes returned if invalid ids were provided. sometimes for other stuff, not sure
                        response_warning_split: list[str] = response.headers["warning"].split()
                        print(response_warning_split)
                        print(f"got status code 206, request was partial success. Got headers:\n {response.headers}\n"
                              f"warning: {response.headers['warning']}\n"
                              "list of invalid id's:", [int(response_warning_split[i + 1][:-1]) for i in
                                                        range(len(response_warning_split))
                                                        if response_warning_split[i] == "id"])

                    elif response.status_code != 200:
                        # catch-all
                        print(f"got code {response.status_code} for request with\n "
                              f"url:\n"
                              f"{response.request.url}\n"
                              f"headers:\n"
                              f"{response.headers}")
                    else:
                        # status code 200
                        success = True

                    if try_count == max_try_count - 1:
                        print("couldn't get a proper response. returning None and hoping that nothing breaks")
                        response_list.append([None] * len(arg_list[j]["id"].split(",")))
                    try_count += 1

                response_list.append(response)

        return response_list

    def _bulk_request_by_id_list(self, path: str, id_list: list[int]) -> list[Response]:
        """This will execute bulk requests in threaded fashion by submitting <_request_thread>s to a ThreadPoolExecutor.
        The id list is split into chunks of <=200 ids each, which are then passed as arguments to an individual request.

        The responses in the returned list are in the same order as the respective arguments provided by the iterator.
        If requests fail, they are handled using a mixture of console outputs, retries and giving up. If a valid
        response can not be obtained, Null will be returned in its place"""

        # create a list of arguments to be passed to _bulk_request
        args_iterator: list[dict] = [
            {"ids": str(id_list[i * self.MAX_PAGE_SIZE:min((i + 1) * self.MAX_PAGE_SIZE, len(id_list))])[1:-1]}
            for i in range(ceil(len(id_list) / self.MAX_PAGE_SIZE))]

        return self._bulk_request(path, args_iterator)

    @staticmethod
    def _cut_listing(listing: ItemListingsJson) -> ItemListingsJson:
        """This method creates a new ItemListingsJson containing only the first 10 buy and sell listings to reduce
        computational effort which would for the most part be false positives anyway (namely relists/cancels instead of
        actual buys or sells)"""

        listing_cutoff: int = 10

        return {
            "id": listing['id'],
            "buys": listing['buys'][:listing_cutoff],
            "sells": listing['sells'][:listing_cutoff]
        }

    @staticmethod
    def _cut_item(api_item) -> ItemJson:
        """This method creates a new ItemJson from a full /items response of the api, since we only need id and name and
        don't care about the rest"""

        return {
            "id": api_item["id"],
            "name": api_item["name"],
            "vendor_value": api_item["vendor_value"] if "NoSell" not in api_item["flags"] else 0
        }

    def get_item_listings_by_id_list(self, id_list: list[int] = []) -> list[ItemListingsJson]:
        """This method can be used to request "commerce/listings?ids=<id_list>" for a list of provided id's. The
        returned list[ItemListingsJson] follows the ordering of the provided ids.
        If no list or an empty list is provided, an empty list is returned.
        Individual ItemListingsJsons in the list may be Null if their respective id was considered invalid by the api"""

        path: str = self.BASE_URL + "commerce/listings"

        # get list of bulk responses, it into individual ItemListingsJsons
        return [(item_listings if item_listings is None else self._cut_listing(item_listings))
                for response in self._bulk_request_by_id_list(path, id_list)
                for item_listings in
                (response if (type(response) == list and response.contains(None)) else response.json())]
        # TODO check if this works (in prices and items too)

    @staticmethod
    def _cut_prices(response_json) -> ItemPricesJson:
        """This method removes the item 'whitelisted' from an ItemPricesJson returned by the api, as we never use it"""

        del response_json["whitelisted"]
        return response_json

    def get_item_prices_by_id_list(self, id_list: list[int] = []) -> list[ItemPricesJson]:
        """This method can be used to request "commerce/prices?ids=<id_list>" for a list of provided id's. The
        returned list[ItemPricesJson] follows the ordering of the provided ids.
        If no list or an empty list is provided, an empty list is returned.
        Individual ItemPricesJsons in the list may be Null if their respective id was considered invalid by the api"""

        path: str = self.BASE_URL + "commerce/prices"

        # get list of bulk responses, it into individual ItemPricesJsons
        return [(item_prices if item_prices is None else self._cut_prices(item_prices)) for response in
                self._bulk_request_by_id_list(path, id_list) for
                item_prices in (response if (type(response) == list and response.contains(None)) else response.json())]

    def get_items_by_id_list(self, id_list: list[int] = []) -> list[ItemJson]:
        """This method can be used to request "commerce/items?ids=<id_list>" for a list of provided id's. The
        returned list[ItemJson] follows the ordering of the provided ids.
        If no list or an empty list is provided, an empty list is returned.
        Individual ItemJson in the list may be Null if their respective id was considered invalid by the api"""

        path: str = self.BASE_URL + "items"

        # get list of bulk responses, it into individual ItemJsons
        return [(item if item is None else self._cut_item(item)) for response in
                self._bulk_request_by_id_list(path, id_list) for
                item in (response if (type(response) == list and response.contains(None)) else response.json())]
