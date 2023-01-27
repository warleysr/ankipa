import json
import time
import os

stats = None
addonpath = None


def load_stats(addon):
    global stats, addonpath
    addonpath = addon

    path = os.path.join(addon, "stats.json")

    try:
        with open(path, "r") as fp:
            stats = json.load(fp)
    except FileNotFoundError:
        stats = dict()


def get_stat(key: str) -> float:
    date = time.strftime("%d/%m/%Y")
    return stats[date][key]


def update_stat(key: str, increment: float, set_value=False):

    date = time.strftime("%d/%m/%Y")

    if date not in stats:
        stats[date] = dict(
            assessments=0.0,
            words=0.0,
            avg_accuracy=0.0,
            avg_fluency=0.0,
            avg_pronunciation=0.0,
            pronunciation_time=0.0,
        )

    if not set_value:
        stats[date][key] += increment
    else:
        stats[date][key] = increment


def update_avg_stat(key: str, new_score: float, assessments: float):
    new_avg = (get_stat(key) * (assessments - 1) + new_score) / assessments
    new_avg = round(new_avg, 2)

    update_stat(key, new_avg, set_value=True)


def save_stats():
    with open(os.path.join(addonpath, "stats.json"), "w+") as fp:
        json.dump(stats, fp, indent=4)
