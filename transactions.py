import datetime
from math import ceil, floor


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
