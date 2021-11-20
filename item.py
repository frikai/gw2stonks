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
        pass  # TODO


class ItemHistory():
    def __init__(self):
        pass

    def update(self, listings_json: ItemListingsJson):
        pass
