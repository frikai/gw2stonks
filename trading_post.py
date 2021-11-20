class TradingPost:
    def __init__(self, api_hander: ApiHandler):
        self.api_handler: ApiHandler = api_hander
        self.item_list: List[Item] = None

    def update(self):
