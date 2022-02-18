import atexit
import datetime
import json
import time
from operator import itemgetter
from typing import List, TypedDict, Iterable

import jsonpickle
import requests

import api_handler
from api_handler import ApiHandler, ItemPricesJson, ItemJson, ItemListingsJson
from item import Item, Flip, TradingStats


class FlipListItem(TypedDict):
    id: int
    name: str
    max_profit: float
    flip_tuple: tuple[Flip]


def write_json(file_path: str, json_data: str):
    with open(file_path, "w+") as outfile:
        outfile.write(json_data)


def save_items(item_list: list[Item]):
    write_json("item_data.txt", jsonpickle.encode(item_list))


def get_and_save_flips(item_list: list[Item]):
    flip_tuple_list: Iterable[tuple[Item, tuple[Flip]]] = (
        (item, item.get_flips([(i, 0.5, 2_000_000) for i in range(5)])) for item in item_list)
    flip_list: list[FlipListItem] = [{
        "id": item.id,
        "name": item.name,
        "max_profit_flip": max(flip for flip in flip_tuple),
        "flip_tuple": flip_tuple
    } for item, flip_tuple in flip_tuple_list]
    # TODO
    flip_list = sorted(flip_list, key=itemgetter("max_profit_flip"), reverse=True)
    write_json("flip_data.txt", jsonpickle.encode(flip_list[:500]))


def save_json(item_list: list[Item]):
    with open("item_data_2.txt", "w+") as file:
        json.dump(item_list, file, default=lambda o: o.to_json(), sort_keys=False)


def load_item_list() -> list[Item]:
    with open("item_data_2.txt", "r+") as file:
        item_list: list[Item] = [Item.from_json(data) for data in json.load(file)]
    return item_list


def save_state(item_list: list[Item]):
    print("saving...")
    save_json(item_list)
    get_and_save_flips(item_list)
    print("done")


def exit_stuff(item_list: list[Item]):
    print("exiting, gimme a sec...")
    save_state(item_list)
    print(f"{datetime.datetime.now()}: saved items, saved flips, exiting for real now")


def main():
    api: ApiHandler = ApiHandler()
    id_list: list[int]
    item_list: list[Item]
    prices_list: list[ItemPricesJson]
    listings_list: list[ItemListingsJson]
    print("looking for data files...")
    try:
        item_list = load_item_list()
        id_list = [item.id for item in item_list]
        print("loaded previous item history from file")
    except FileNotFoundError:
        print("no previous data found, starting from scratch")
        id_list = list(set(requests.get("https://api.guildwars2.com/v2/commerce/listings").json())
                       & set(requests.get("https://api.guildwars2.com/v2/items").json()))

        item_json_list: list[ItemJson] = api.get_items_by_id_list(id_list)
        prices_list = api.get_item_prices_by_id_list(id_list)
        listings_list = api.get_item_listings_by_id_list(id_list)
        item_list: list[Item] = [Item(*args) for args in zip(item_json_list, prices_list, listings_list)]
        time.sleep(120)
    atexit.register(exit_stuff, item_list)
    id_to_index_map: dict[int:int] = {id_list[i]: i for i in range(len(id_list))}
    print("starting")
    i: int = 0
    while True:
        start_time = datetime.datetime.now()
        print(start_time)
        prices_list = api.get_item_prices_by_id_list(id_list)
        listings_list = api.get_item_listings_by_id_list(id_list)
        assert len(item_list) == len(prices_list) == len(listings_list)
        for tuple in zip(item_list, prices_list, listings_list):
            tuple[0].update_prices(tuple[1])
            tuple[0].update_listings(tuple[2])
        # if i == 0:
        #     save_state(item_list)
        while (datetime.datetime.now() - start_time).seconds < 120:
            time.sleep(5)
        i %= 30
        if i == 0:
            save_state(item_list)
        i += 1


# def main():
# r = requests.get("https://api.guildwars2.com/v2/commerce/listings")
# print(len(r.json()))
# 26742
# r = requests.get("https://api.guildwars2.com/v2/items")
# args = {"ids":"", "lang":"en"}
# tradeable_items = set()
# i = 0
# while(True):
#     max_index = min((i+1)*200, len(r.json())-1)
#     args["ids"]=str(r.json()[i*200:max_index])[1:-1]
#     res = requests.get("https://api.guildwars2.com/v2/items", params=args)
#     tradeable_items |= set(item["id"] for item in res.json() if not any(x in item["flags"] for x in ["AccountBound", "SoulbindOnAcquire"]))
#     if(max_index<(i+1)*200):
#         break
#     print(i, res.elapsed, len(tradeable_items))
#     i+=1
#
# #print(tradeable_items)
# print(len(r.json()), len(tradeable_items))


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
