import os
from concurrent.futures._base import Future  # TODO: accessing protected member...? idk it works
from concurrent.futures.thread import ThreadPoolExecutor
from math import ceil
from typing import Iterator, TypedDict

import requests
from requests import Response


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


# handler for interacting with the gw2 api
class ApiHandler:
    # some base constants
    BASE_URL: str = "https://api.guildwars2.com/v2/"
    API_KEY: str = os.getenv("api_key")
    MAX_PAGE_SIZE: int = 200
    DEFAULT_ARGS: dict[str, str] = {"lang": "en"}

    def __init__(self):
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor()  # we use this executer to execute bulk requests in
        # parallel

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
        with self.executor as executor:
            # spawn threads for individual requests
            future_list: list[Future] = [executor.submit(self._request_thread, path, args) for args in args_iterator]
            # join on each thread in order and append the responses to the return list
            for future in future_list:
                response_list.append(future.result())  # waits for the respective thread to finish
        return response_list

    # function to request "commerce/prices" for a list of provided id's
    # TODO: behaviour is undefined if list contains invalid IDs or if requests fail due to rate limiting or other causes
    def get_item_prices_by_id_list(self, id_list: list[int] = []) -> list[ItemPricesJson]:
        path: str = self.BASE_URL + "commerce/prices"
        # split bulk request into requests with <=200 ids (maximum size allowed by api)
        # create an iterator of respective args for each of the bundles of <= 200 ids
        # to be passed to _bulk_request()
        args_iterator: Iterator[dict] = (
            {"ids": str(id_list[i * self.MAX_PAGE_SIZE:min((i + 1) * self.MAX_PAGE_SIZE, len(id_list))])[1:-1]}
            for i in range(ceil(len(id_list) / self.MAX_PAGE_SIZE)))
        # execute requests in threaded fashion
        response_list: list[Response] = self._bulk_request(path, args_iterator)

        return [item for r in response_list for item in r.json()]


# for testing purposes
def main():
    apihandler = ApiHandler()
    r = requests.get("https://api.guildwars2.com/v2/commerce/prices")
    prices_list = apihandler.get_item_prices_by_id_list(id_list=r.json())
    print(prices_list[0]["whitelisted"])


if __name__ == '__main__':
    main()
