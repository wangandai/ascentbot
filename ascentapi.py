import requests

url = "https://script.google.com/macros/s/AKfycbybFe3g9Kf8fjFz-DDQCsaGURhRSnjc0jtiM-2MVXY2W6raox8/exec"


def url_with_action(action):
    return "{}?action={}".format(url, action)


def get_fort_roster():
    r = requests.get(url=url_with_action("getFortRoster"))
    return r.json()