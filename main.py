from math import ceil, floor

import requests
from typing import List
import datetime
from dataclasses import dataclass
from typing import List

@dataclass
class SimpleListingsJson:
    unit_price: int  # price at which the items are listed
    quantity: int  # number of individual items listed at unit_price

@dataclass
class ListingJson(SimpleListingsJson):
    listings: int  # number of sellers/individual listings at given price

@dataclass
class ItemListingsJson:
    id: int
    buys: List[ListingJson]
    sells: List[ListingJson]

@dataclass
class ItemPricesJson:
    id: int
    whitelisted: bool # TODO: or str, not sure
    buys: List[SimpleListingsJson]
    sells: List[SimpleListingsJson]


class BuyOrder:
    def __init__(self, quantity: int, listing_price: int):
        self.quantity: int = quantity
        self.listing_price: int = listing_price
        self.listing_time: datetime.datetime = datetime.datetime.now()

    def relist(self, price: int):
        assert price > self.listing_price, "tried to decrease price when relisting a buy order :kekwait:"
        self.listing_price = price
        self.listing_time = datetime.datetime.now()

    def fill(self, amount: int):
        assert amount <= self.quantity, "apparently received more than I bought :monkaS:"
        self.quantity -= amount


class SellOrder:
    def __init__(self, quantity: int, buy_price: int, listing_price: int):
        self.quantity: int = quantity
        self.buy_price: int = buy_price
        self.listing_price: int = listing_price
        self.tax_paid: int = 0
        self.listing_time: datetime.datetime = datetime.datetime.now()

    def relist(self, price: int):
        assert price < self.listing_price, "tried to increase price when relisting a sell order :kekwait:"
        self.listing_price = price
        self.tax_paid += ceil(0.05 * price)
        self.listing_time = datetime.datetime.now()

    def fill(self, amount: int):
        assert amount <= self.quantity, "apparently sold more than I have :monkaS:"
        self.quantity -= amount
        profit: int = floor(amount * (0.9 * self.listing_price - self.tax_paid - self.buy_price))
        return profit


class Transaction:
    def __init__(self):
        self.start_time: datetime.datetime = datetime.datetime.now()
        self.status: str = "buying"  # buying, mixed, selling, completed
        self.buy_order: BuyOrder
        self.sell_order: SellOrder
        pass


class ItemHistory():
    def __init__(self):
        pass

    def update(self, listings_json: ItemListingsJson):
        pass


class Item:
    def __init__(self, item_json):
        self.id: int = 0  # id of the item
        self.history: ItemHistory = None  # history of the item on the TP (global)
        self.transaction_list: List[Transaction] = None  # history of local transactions (if self.active,
        # transaction_list[-1] will contain active transaction)
        self.last_update: ItemPricesJson = None  # current instant sell price and quantity of the item
        self.current_profit_percent: float = 0  # profit from flipping the item (after tax)
        self.active: bool = False  # True if there is an active transaction for this item
        self.stonkscore: float = 0

    def __lt__(self, other):
        assert isinstance(other, Item), f"tried to compare an Item with {type(other)}"
        return self.stonkscore < other.stonkscore

    # call this when fresh listings data is available, returns true if any apparent changes are detected
    def check_update(self, prices_json: ItemPricesJson):
        # compare updated values with old, return True if there is a difference
        return prices_json != self.last_update

    # calculates updated investment stonks score
    def _update_stonkscore(self):
        pass  # TODO

    def update_transaction(self):
        pass # TODO

class ApiHandler():
    def __init__(self):
        pass

    def update_all(self):

class TradingPost():
    def __init__(self):
        self.liquid_gold: int = 0
        self.current_orders: List[Transaction] = None
        self.item_list: List[Item] = None
        self.api_handler: ApiHandler = None


def main():
    r = requests.get("https://api.guildwars2.com/v2/commerce/listings")
    print(len(r.json()))
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
