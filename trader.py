class Trader:
    def __init__(self, trader_id: int, starting_capital: int, tp: TradingPost, api: ApiHandler):
        self.tp: TradingPost = tp
        self.api: ApiHandler = api
        self.history: TraderHistory = TraderHistory()
        self.id: int = trader_id
        self.starting_capital: int = starting_capital
        self.liquidity: int = starting_capital
        self.profit: int = 0


class TraderHistory(object):
    pass
