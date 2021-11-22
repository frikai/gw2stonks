import datetime

from api_handler import ItemListingsJson, ItemPricesJson, ItemJson, BuysSellsItemListingsJson


class VolumeStats:
    STATS_PERIOD: int = 86400  # seconds in a day

    def __init__(self):
        self.buys: float = 0.0
        self.sells: float = 0.0
        self.offer_size: float = 0.0
        self.bid_size: float = 0
        self.supply: int = 0
        self.demand: int = 0
        self.demand_delta: float = 0
        self.supply_delta: float = 0


class SuggestedFlip:
    def __init__(self):
        self.quantity: int = 0
        self.buy_price: int = 0
        self.expected_sell_price: int = 0
        self.abort_at_quantity_sold_at_same_or_less: int = 0


class Item:
    def __init__(self, item_json: ItemJson, prices_json: ItemPricesJson, listings_json: ItemListingsJson):
        self.id: int = item_json['id']
        self.name: str = item_json['name']
        self.volume_stats = VolumeStats()
        self.last_prices: ItemPricesJson = prices_json
        self.prices_timestamp: datetime.datetime = datetime.datetime.now()
        self.last_listings: ItemListingsJson = listings_json
        self.listings_timestamp: datetime.datetime = datetime.datetime.now()
        self.stonkscore: float = 0.0
        self.suggested_flip: SuggestedFlip = None
        self.stonksify()

    def _stonksify(self) -> None:
        self.stonkscore = 0
        self.suggested_flip = SuggestedFlip()

    def update_prices(self, prices_json: ItemPricesJson) -> bool:
        time_now: datetime.datetime = datetime.datetime.now()
        something_changed: bool = self.last_prices == prices_json

        new_demand: int = prices_json['buys']['quantity']
        new_supply: int = prices_json['sells']['quantity']

        time_since_update: float = (time_now - self.prices_timestamp).total_seconds()
        weight: float = time_since_update / self.volume_stats.STATS_PERIOD

        self.volume_stats.demand_delta = (1 - weight) * self.volume_stats.demand_delta \
                                         + weight * (new_demand - self.volume_stats.demand)
        self.volume_stats.supply_delta = (1 - weight) * self.volume_stats.supply_delta \
                                         + weight * (new_supply - self.volume_stats.supply)

        self.volume_stats.demand = new_demand
        self.volume_stats.supply = new_supply
        self.last_prices = prices_json
        self.prices_timestamp = time_now

        return something_changed

    def update_listings(self, listings_json: ItemListingsJson) -> None:
        time_now: datetime.datetime = datetime.datetime.now()
        time_since_update: float = (time_now - self.listings_timestamp).total_seconds()
        weight: float = time_since_update / self.volume_stats.STATS_PERIOD

        old_buys: list[BuysSellsItemListingsJson] = self.last_listings['buys']
        new_buys: list[BuysSellsItemListingsJson] = listings_json['buys']

        self.volume_stats.bid_size = sum(listing["quantity"] for listing in new_buys) / sum(
            listing["listings"] for listing in new_buys)

        sold: int = 0

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

        self.volume_stats.sells = (1 - weight) * self.volume_stats.sells + weight * sold

        old_sells: list[BuysSellsItemListingsJson] = self.last_listings['sells']
        new_sells: list[BuysSellsItemListingsJson] = listings_json['sells']

        self.volume_stats.offer_size = sum(listing["quantity"] for listing in new_sells) / sum(
            listing["listings"] for listing in new_sells)

        bought: int = 0

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

        self.volume_stats.buys = (1 - weight) * self.volume_stats.buys + weight * bought

        self.last_listings = listings_json
        self.listings_timestamp = time_now
