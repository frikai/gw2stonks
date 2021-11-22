import datetime

from api_handler import ItemListingsJson, ItemPricesJson, ItemJson, BuysSellsItemListingsJson


# class to hold various trading statistics of the item
class VolumeStats:
    STATS_PERIOD: int = 86400  # relevant time period for VolumeStats in seconds

    # any stats described as "weighted" are stats which consist of a sum of the recorded values where the older
    # components of the sum are weighted less and less as newer updates are added.
    # these weighted values are not exact numbers for each stat, but instead scores designed to take both the track
    # record and recent development of the stat into account to represent the trend of the stat.
    # These scores will asymptotically tend towards the most recent developments, as older values are weighed less

    # weighted stats can be considered a sort of "derivative" of the stat (conceptually)
    def __init__(self):
        self.buys: float = 0.0  # weighted stat of filled buy orders within STATS_PERIOD
        self.sells: float = 0.0  # weighted stat of filled sell listings within STATS_PERIOD
        self.offer_size: float = 0.0  # average number of items per sell listing across the offers with the lowest n
        # prices, where n is the cutoff specified in ApiHandler._cut_listing
        self.bid_size: float = 0.0  # average number of items per buy order across the bids with the highest n prices ,
        # where n is the cutoff specified in ApiHandler._cut_listing
        self.supply: int = 0  # total supply (sum of sell listings) of the item
        self.demand: int = 0  # total demand (sum of buy orders) of the item
        self.demand_delta: float = 0.0  # weighted stat of demand trend
        self.supply_delta: float = 0.0  # weighted stat of supply trend


# a class to hold the calculated suggested "flip" to perform on the item pertaining to the stonkscore
class SuggestedFlip:
    def __init__(self):
        self.quantity: int = 0  # number of items to buy
        self.buy_price: int = 0  # price to buy at
        self.expected_sell_price: int = 0  # sell price used in the stonkscore calculation
        self.abort_at_outbid_quantity: int = 0  # cancel buy orders if there is at least this number of items being
        # bid for by other players with higher bids


# class to contain every relevant information about a given item tradeable on the trading post
class Item:
    def __init__(self, item_json: ItemJson, prices_json: ItemPricesJson, listings_json: ItemListingsJson):
        self.id: int = item_json['id']  # api id of the item
        self.name: str = item_json['name']  # in game name of the item
        self.volume_stats = VolumeStats()  # see VolumeStats documentation
        self.last_prices: ItemPricesJson = prices_json  # prices api data from last refresh
        self.prices_timestamp: datetime.datetime = datetime.datetime.now()  # timestamp for the latest prices api data
        self.last_listings: ItemListingsJson = listings_json  # listings api data from last refresh
        self.listings_timestamp: datetime.datetime = datetime.datetime.now()  # timestamp for the latest listings api
        # data
        self.stonkscore: float = 0.  # aggregated score indicating how well flipping this item should go using the suggested flip, used as a priority ranking
        self.suggested_flip: SuggestedFlip = None  # see SuggestedFlip documentation
        self.stonksify()  # TODO see _stonksify

    def _stonksify(self) -> None:  # TODO develop stonks formula, create a SuggestedFlip from it
        self.stonkscore = 0
        self.suggested_flip = SuggestedFlip()

    # method to update all relevant stats of the item given fresh prices data from the api
    def update_prices(self, prices_json: ItemPricesJson) -> bool:
        time_now: datetime.datetime = datetime.datetime.now()
        # check if anything has changed since the last update
        something_changed: bool = self.last_prices == prices_json

        # volume stats need to be updated even if nothing has changed about the item (as the lack of activity is information in and of itself)

        new_demand: int = prices_json['buys']['quantity']
        new_supply: int = prices_json['sells']['quantity']

        # calculate the weight to be used to update the weighted scores
        time_since_update: float = (time_now - self.prices_timestamp).total_seconds()
        weight: float = time_since_update / self.volume_stats.STATS_PERIOD

        # adjust supply and demand trends based on changes (or lack thereof) in the latest update
        self.volume_stats.demand_delta = (1 - weight) * self.volume_stats.demand_delta \
                                         + weight * (new_demand - self.volume_stats.demand)
        self.volume_stats.supply_delta = (1 - weight) * self.volume_stats.supply_delta \
                                         + weight * (new_supply - self.volume_stats.supply)

        # store the data of this update as the most recent data
        self.volume_stats.demand = new_demand
        self.volume_stats.supply = new_supply
        self.last_prices = prices_json
        self.prices_timestamp = time_now

        # we return if there were any differences from the last update to this one, we may want to use this to decide
        # on whether we want to poll further data such as listings data on this item for this refresh cycle
        return something_changed

    # method to update all relevant stats of the item given fresh listings data from the api
    def update_listings(self, listings_json: ItemListingsJson) -> None:
        # calculate the weight to be used to update the weighted scores
        time_now: datetime.datetime = datetime.datetime.now()
        time_since_update: float = (time_now - self.listings_timestamp).total_seconds()
        weight: float = time_since_update / self.volume_stats.STATS_PERIOD

        old_buys: list[BuysSellsItemListingsJson] = self.last_listings['buys']
        new_buys: list[BuysSellsItemListingsJson] = listings_json['buys']

        # get average buy offer size
        self.volume_stats.bid_size = sum(listing["quantity"] for listing in new_buys) / sum(
            listing["listings"] for listing in new_buys)

        # calculate stat for buy orders filled since last update
        sold: int = 0

        # we compare the listings for each price point between the previous update and this one by iterating over both
        # at the same time, incrementing the indexes as we go to compare the correct price points with each other
        # as we sum up the recorded changes (which are interpreted as filled buy orders, but could also include false
        # positives in the shape of cancelled buy orders)
        i: int = 0
        j: int = 0
        while i < len(new_buys) and j < len(old_buys):
            if new_buys[i]['unit_price'] > old_buys[j]['unit_price']:
                i += 1
            elif new_buys[i]['unit_price'] == old_buys[j]['unit_price']:
                sold += max(0, new_buys[i]['quantity'] - old_buys[j]['quantity'])
                i += 1
                j += 1
            elif new_buys[i]['unit_price'] < old_buys[j]['unit_price']:
                sold += old_buys[j]['quantity']
                j += 1

        # update the relevant stats using the calculated sum with appropriate weight
        self.volume_stats.sells = (1 - weight) * self.volume_stats.sells + weight * sold

        old_sells: list[BuysSellsItemListingsJson] = self.last_listings['sells']
        new_sells: list[BuysSellsItemListingsJson] = listings_json['sells']

        # get average sell listing size
        self.volume_stats.offer_size = sum(listing["quantity"] for listing in new_sells) / sum(
            listing["listings"] for listing in new_sells)

        # calculate stat for sell listings filled since last update
        bought: int = 0

        # we compare the listings for each price point between the previous update and this one by iterating over both
        # at the same time, incrementing the indexes as we go to compare the correct price points with each other
        # as we sum up the recorded changes (which are interpreted as filled sell listings, but could also include false
        # positives in the shape of cancelled sell listings)
        i: int = 0
        j: int = 0
        while i < len(new_sells) and j < len(old_sells):
            if new_sells[i]['unit_price'] > old_sells[j]['unit_price']:
                bought += old_sells[j]['quantity']
                j += 1
            elif new_sells[i]['unit_price'] == old_sells[j]['unit_price']:
                bought += max(0, old_sells[i]['quantity'] - new_sells[j]['quantity'])
                i += 1
                j += 1
            elif new_sells[i]['unit_price'] < old_sells[j]['unit_price']:
                i += 1

        # update the relevant stats using the calculated sum with appropriate weight
        self.volume_stats.buys = (1 - weight) * self.volume_stats.buys + weight * bought

        # store the data of this update as the most recent data
        self.last_listings = listings_json
        self.listings_timestamp = time_now


def main():
    pass


if __name__ == '__main__':
    main()
