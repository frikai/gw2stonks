import json
from typing import List


def write_ad_list_to_json(new: List[Ad]):
    data = {"ads": [ad.to_dict() for ad in new]}
    with open('seen_ads.txt', 'w', encoding="utf-8") as outfile:
        json.dump(data, outfile, ensure_ascii=False)


def load_json_to_ad_list() -> List[Ad]:
    try:
        print("loading json data of previous scans")
        with open('seen_ads.txt') as json_file:
            data: dict = json.load(json_file)
    except FileNotFoundError:
        print("Cannot find any previous records, looks like this is the first time you're running this.\n"
              "If that is not the case, the file I was storing seen ads in somehow got lost or moved :(\n"
              "Anyway, I'm making a new one ¯\\_(ツ)_/¯")
        print("creating \"seen_ads.txt\"\n")
        create_file()

        with open('seen_ads.txt') as json_file:
            data: dict = json.load(json_file)

    return [Ad(ad) for ad in data["ads"]]


def create_file():
    f = open("seen_ads.txt", "x")
    f.close()
    data = {"ads": []}
    with open('seen_ads.txt', 'w') as outfile:
        json.dump(data, outfile)
