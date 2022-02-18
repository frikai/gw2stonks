import datetime
from functools import total_ordering
from math import ceil

from jsonpickle import encode

from api_handler import ItemListingsJson, ItemPricesJson, ItemJson, BuysSellsItemListingsJson, ApiHandler
# class to hold various trading statistics of the item
from db import Jsonizable


class TradingStats(Jsonizable):
    # any stats described as "weighted" are stats which consist of a sum of the recorded values where the older
    # components of the sum are weighted less and less as newer updates are added. these weighted values are not
    # exact numbers for each stat, but instead scores designed to take both the track record and recent development
    # of the stat into account to represent the trend of the stat. These scores will asymptotically tend towards the
    # latest <stat>/<refresh_time>, a derivative of sorts that takes into account history as well
    def __init__(self, stats_period: int):
        self.stats_period: int = stats_period
        self.buy_price_delta: float = 0.0
        self.sell_price_delta: float = 0.0
        self.buys: float = 0.0  # weighted stat of filled buy orders
        self.sells: float = 0.0  # weighted stat of filled sell listings within stats_period
        self.demand_delta: float = 0.0  # weighted stat of demand trend
        self.supply_delta: float = 0.0  # weighted stat of supply trend

    @classmethod
    def from_json(cls, data):
        s: cls = cls(data["stats_period"])
        s.buy_price_delta = data["buy_price_delta"]
        s.sell_price_delta = data["sell_price_delta"]
        s.buys = data["buys"]
        s.sells = data["sells"]
        s.demand_delta = data["demand_delta"]
        s.supply_delta = data["supply_delta"]
        return s

    def to_json(self):
        return self.__dict__


class SharedTradingStats(Jsonizable):
    STATS_PERIOD: list[int] = [5400, 10800, 21600, 43200,
                               64800]  # 86400  # relevant time period for TradingStats in seconds
    MAX_LISTINGS: int = 8

    def __init__(self, vendor_value: int,
                 prices_json: ItemPricesJson, listings_json: ItemListingsJson,
                 prices_timestamp: str = datetime.datetime.now().isoformat(),
                 listings_timestamp: str = datetime.datetime.now().isoformat()):
        self.buy_price: int = prices_json['buys']['unit_price']
        self.sell_price: int = prices_json['sells']['unit_price']
        listings_sum = sum(listing["listings"] for listing in listings_json['sells'])
        self.offer_size: float = 0 if listings_sum == 0 else \
            sum(listing["quantity"] for listing in listings_json['sells']) / listings_sum  # average number of items
        # per sell listing across the offers with the lowest n
        # prices, where n is the cutoff specified in ApiHandler._cut_listing
        listings_sum: int = sum(listing["listings"] for listing in listings_json['buys'])
        self.bid_size: float = 0 if listings_sum == 0 else \
            sum(listing["quantity"] for listing in listings_json['buys']) / listings_sum  # average number of items
        # per buy order across the bids with the highest n prices ,
        # where n is the cutoff specified in ApiHandler._cut_listing
        self.supply: int = prices_json['sells']['quantity']  # total supply (sum of sell listings) of the item
        self.demand: int = prices_json['buys']['quantity']  # total demand (sum of buy orders) of the item
        self.last_prices: ItemPricesJson = prices_json  # prices api data from last refresh
        self.prices_timestamp: datetime.datetime = datetime.datetime.fromisoformat(
            prices_timestamp)  # timestamp for the latest prices api data
        self.last_listings: ItemListingsJson = listings_json  # listings api data from last refresh
        self.listings_timestamp: datetime.datetime = datetime.datetime.fromisoformat(
            listings_timestamp)  # timestamp for the latest listings api
        # data
        self.vendor_value = vendor_value

    @classmethod
    def from_json(cls, data):
        return cls(**data)

    def to_json(self):
        return {
            "prices_json": self.last_prices,
            "listings_json": self.last_listings,
            "prices_timestamp": self.prices_timestamp.isoformat(),
            "listings_timestamp": self.listings_timestamp.isoformat(),
            "vendor_value": self.vendor_value
        }


# a class to hold the calculated suggested "flip" to perform on the item pertaining to the stonkscore
@total_ordering
class Flip(object):
    def __init__(self, item_id: int, target_trade_duration: int, quantity: int, buy_price: int,
                 expected_sell_price: int, expected_profit: int, buy_time: int, sell_time: int):
        self.id: int = item_id
        self.target_trade_duration: int = target_trade_duration
        self.quantity: int = quantity
        self.buy_price: int = buy_price
        self.expected_sell_price: int = expected_sell_price
        self.expected_profit: int = expected_profit
        self.expected_pph: int = 0 if target_trade_duration == 0 else round(expected_profit * 3600 / target_trade_duration)
        self.buy_time: int = buy_time
        self.sell_time: int = sell_time

    # TODO isinstance
    def __eq__(self, other):
        return self.id == other.id and self.expected_profit == other.expected_profit

    def __lt__(self, other):
        return self.expected_profit < other.expected_profit


# class to contain every relevant information about a given item tradable on the trading post
class Item(Jsonizable):
    def __init__(self, item_json: ItemJson, prices_json: ItemPricesJson = None, listings_json: ItemListingsJson = None,
                 trading_stats: tuple[TradingStats] = None, shared_trading_stats: SharedTradingStats = None):
        assert item_json is not None
        if prices_json is None or listings_json is None:
            assert shared_trading_stats is not None
        self.id: int = item_json['id']  # api id of the item
        self.name: str = item_json['name']  # in game name of the item
        self.shared_trading_stats: SharedTradingStats = SharedTradingStats(vendor_value=item_json['vendor_value'],
                                                                           prices_json=prices_json,
                                                                           listings_json=listings_json) if \
            shared_trading_stats is None else shared_trading_stats
        self.trading_stats: tuple[TradingStats] = tuple(TradingStats(self.shared_trading_stats.STATS_PERIOD[i])
                                                        for i in range(5)) if trading_stats is None else trading_stats

    @classmethod
    def from_json(cls, data):
        shared_trading_stats: SharedTradingStats = SharedTradingStats.from_json(data["shared_trading_stats"])
        return cls(
            data["item_json"],
            trading_stats=tuple(TradingStats.from_json(ts) for ts in data["trading_stats"]),
            shared_trading_stats=shared_trading_stats)

    def get_flips(self, params: list[tuple[int, float, int]]) -> tuple[Flip]:
        return tuple(self._get_flip(*param) for param in params)

    def _get_flip(self, trade_type: int, out_bid_p: float, budget: int) -> Flip:
        sts: SharedTradingStats = self.shared_trading_stats
        ts: TradingStats = self.trading_stats[trade_type]
        min_price: int = ceil(sts.vendor_value / 0.85)
        target_trade_duration = int(ts.stats_period / (3 * ApiHandler.REFRESH_TIME))
        # time_until_outbid_p_reached: float = min( target_trade_duration / 2 if ts.buy_price_delta <= 0 else
        # ApiHandler.REFRESH_TIME * out_bid_p / ts.buy_price_delta, target_trade_duration / 2) /
        # ApiHandler.REFRESH_TIME
        time_until_outbid_p_reached: float = target_trade_duration if ts.buy_price_delta <= 0 else out_bid_p / ts.buy_price_delta
        time_until_undercut_p_reached: float = target_trade_duration if ts.sell_price_delta >= 0 else out_bid_p / -ts.sell_price_delta
        buy_time: float = min(time_until_outbid_p_reached,
                              0 if ts.sells == 0 else target_trade_duration * ts.sells / (ts.buys + ts.sells))
        sell_time: float = min(time_until_undercut_p_reached, target_trade_duration - buy_time)
        expected_sell_change: float = ts.sell_price_delta * buy_time
        buys_fillable: float = ts.buys * buy_time
        # sells_fillable: float = ts.sells * (
        #         target_trade_duration / ApiHandler.REFRESH_TIME - time_until_outbid_p_reached)
        sells_fillable: float = ts.sells * sell_time
        price_to_buy_at: int = max(min_price, sts.buy_price + 1)
        expected_sell_price: int = max(min_price, sts.sell_price + round(expected_sell_change) - 1)
        amount_to_buy: int = min(int(min(buys_fillable, sells_fillable, sts.MAX_LISTINGS * 250)),
                                 int(budget / (price_to_buy_at + 0.05 * expected_sell_price)))
        expected_profit: int = amount_to_buy * int(expected_sell_price * 0.85 - price_to_buy_at)
        return Flip(self.id, round((buy_time+sell_time) * ApiHandler.REFRESH_TIME), amount_to_buy, price_to_buy_at, expected_sell_price,
                    expected_profit, round(buy_time * ApiHandler.REFRESH_TIME),
                    round(sell_time * ApiHandler.REFRESH_TIME))

    def update_prices(self, prices_json: ItemPricesJson) -> None:
        if prices_json is None:
            return
        assert prices_json['id'] == self.id
        for ts in self.trading_stats:
            self._update_prices(prices_json, ts)
        sts: SharedTradingStats = self.shared_trading_stats
        sts.demand = prices_json['buys']['quantity']
        sts.supply = prices_json['sells']['quantity']
        sts.buy_price = prices_json['buys']['unit_price']
        sts.sell_price = prices_json['sells']['unit_price']
        sts.last_prices = prices_json
        sts.prices_timestamp = datetime.datetime.now()

    # method to update all trading-relevant stats of the item given fresh prices data from the api
    def _update_prices(self, prices_json: ItemPricesJson, ts: TradingStats) -> None:
        sts: SharedTradingStats = self.shared_trading_stats
        time_now: datetime.datetime = datetime.datetime.now()

        # trading stats need to be updated even if nothing has changed about the item (as the lack of activity is
        # information in and of itself)

        new_demand: int = prices_json['buys']['quantity']
        new_supply: int = prices_json['sells']['quantity']

        new_buy_price: int = prices_json['buys']['unit_price']
        new_sell_price: int = prices_json['sells']['unit_price']

        # calculate the weight to be used to update the weighted scores
        time_since_update: float = (time_now - sts.prices_timestamp).total_seconds()
        weight: float = min(1, time_since_update / ts.stats_period)
        normalize_factor: float = ApiHandler.REFRESH_TIME / time_since_update

        # adjust weighted trends based on changes (or lack thereof) in the latest update
        ts.demand_delta = (1 - weight) * ts.demand_delta \
                          + weight * normalize_factor * (new_demand - sts.demand)
        ts.supply_delta = (1 - weight) * ts.supply_delta \
                          + weight * normalize_factor * (new_supply - sts.supply)
        ts.buy_price_delta = (1 - weight) * ts.buy_price_delta + weight * normalize_factor * (
                new_buy_price - sts.buy_price)
        ts.sell_price_delta = (1 - weight) * ts.sell_price_delta + weight * normalize_factor * (
                new_sell_price - sts.sell_price)

    def update_listings(self, listings_json: ItemListingsJson) -> None:
        if listings_json is None:
            return
        assert listings_json['id'] == self.id
        for ts in self.trading_stats:
            self._update_listings(listings_json, ts)

        sts: SharedTradingStats = self.shared_trading_stats

        # get average buy offer size
        listings_sum: int = sum(listing["listings"] for listing in listings_json['buys'])
        sts.bid_size = 0 if listings_sum == 0 else sum(
            listing["quantity"] for listing in listings_json['buys']) / listings_sum

        # get average sell listing size
        listings_sum = sum(listing["listings"] for listing in listings_json['sells'])
        sts.offer_size = 0 if listings_sum == 0 else sum(
            listing["quantity"] for listing in listings_json['sells']) / listings_sum

        sts.last_listings = listings_json
        sts.listings_timestamp = datetime.datetime.now()

    # method to update all trading-relevant stats of the item given fresh listings data from the api
    def _update_listings(self, listings_json: ItemListingsJson, ts: TradingStats) -> None:
        sts: SharedTradingStats = self.shared_trading_stats
        # calculate the weight to be used to update the weighted scores
        time_now: datetime.datetime = datetime.datetime.now()
        time_since_update: float = (time_now - sts.listings_timestamp).seconds
        weight: float = min(1, time_since_update / ts.stats_period)
        normalize_factor: float = ApiHandler.REFRESH_TIME / time_since_update

        old_buys: list[BuysSellsItemListingsJson] = sts.last_listings['buys']
        new_buys: list[BuysSellsItemListingsJson] = listings_json['buys']

        # calculate stat for buy orders filled since last update
        sold: int = 0

        # we compare the listings for each price point between the previous update and this one by iterating over both
        # at the same time, incrementing the indexes as we go to compare the correct price points with each other
        # as we sum up the recorded changes (which are interpreted as filled buy orders, but could also include false
        # positives in the shape of cancelled buy orders)
        i: int = 0
        j: int = 0
        while i < len(new_buys) and j < len(old_buys):
            if new_buys[i] == old_buys[j]:
                break
            elif new_buys[i]['unit_price'] > old_buys[j]['unit_price']:
                i += 1
            elif new_buys[i]['unit_price'] == old_buys[j]['unit_price']:
                sold += max(0, old_buys[j]['quantity'] - new_buys[i]['quantity'])
                i += 1
                j += 1
            elif new_buys[i]['unit_price'] < old_buys[j]['unit_price']:
                sold += old_buys[j]['quantity']
                j += 1

        # update the relevant stats using the calculated sum with appropriate weight
        ts.buys = (1 - weight) * ts.buys + weight * normalize_factor * sold  # TODO: switch buys/sells everywhere else in the function to make naming consistent

        old_sells: list[BuysSellsItemListingsJson] = sts.last_listings['sells']
        new_sells: list[BuysSellsItemListingsJson] = listings_json['sells']

        # calculate stat for sell listings filled since last update
        bought: int = 0

        # we compare the listings for each price point between the previous update and this one by iterating over both
        # at the same time, incrementing the indexes as we go to compare the correct price points with each other
        # as we sum up the recorded changes (which are interpreted as filled sell listings, but could also include false
        # positives in the shape of cancelled sell listings)
        i: int = 0
        j: int = 0
        while i < len(new_sells) and j < len(old_sells):
            if new_sells[i] == old_sells[j]:
                break
            elif new_sells[i]['unit_price'] > old_sells[j]['unit_price']:
                bought += old_sells[j]['quantity']
                j += 1
            elif new_sells[i]['unit_price'] == old_sells[j]['unit_price']:
                bought += max(0, old_sells[j]['quantity'] - new_sells[i]['quantity'])
                i += 1
                j += 1
            elif new_sells[i]['unit_price'] < old_sells[j]['unit_price']:
                i += 1

        # update the relevant stats using the calculated sum with appropriate weight
        ts.sells = (1 - weight) * ts.sells + weight * normalize_factor * bought  # TODO: switch buys/sells everywhere else in the function to make naming consistent

    def to_json(self) -> dict:
        return {
            "item_json": {
                "id": self.id,
                "name": self.name,
                "vendor_value": self.shared_trading_stats.vendor_value
            },
            "shared_trading_stats": self.shared_trading_stats.to_json(),
            "trading_stats": [ts.to_json() for ts in self.trading_stats]
        }


def main():
    api: ApiHandler = ApiHandler()
    item_tuple: (ItemJson, ItemListingsJson, ItemPricesJson) = (
        api.get_items_by_id_list(id_list=[19700])[0],
        api.get_item_listings_by_id_list(id_list=[19700])[0],
        api.get_item_prices_by_id_list(id_list=[19700])[0]
    )
    item: Item = Item(*item_tuple)
    print(encode(item))


if __name__ == '__main__':
    main()
