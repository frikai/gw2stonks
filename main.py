from typing import List

from dotenv import load_dotenv

load_dotenv()


def main():
    tp: TradingPost = TradingPost()
    api: ApiHandler = ApiHandler()
    traders: List[Trader] = [Trader(0, 300, tp, api)]


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
