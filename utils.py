import re
import sys
import os
import datetime


options_list = [
    [ 'src', 'source' ],
    [ 'dst', 'dest', 'destination' ],
]

def get_option(section, config, value):
    if config.has_option(section, value):
        return config.get(section, value)
    lists = list(filter(lambda x: value in x, options_list))
    if len(lists) > 0:
        lists = lists[0]
        for opt in lists:
            if config.has_option(section, opt):
                return config.get(section, opt)
    return None

def get_interval_from_str(txt):
    if txt is None:
        return None
    secs = 0
    unitMap = {"d": 24 * 60 * 60, "h": 60 * 60, "m": 60, "s": 1}

    for k, v in unitMap.items():
        m = re.match("^(\d+)" + k + "$", txt)
        if m is not None:
            secs += int(m.group(1)) * v

    return secs

# 0 error 1 warn 2 info
LOG_ERROR = 0
LOG_WARN = 1
LOG_INFO = 2


def log(type, category, txt):
    if type == 0:
        sys.stdout.write("\033[1;31m")
    if type == 1:
        sys.stdout.write("\033[1;33m")
    if type == 2:
        sys.stdout.write("\033[1;32m")

    sys.stdout.write("[{0}] {1}\033[0m\n".format(category, txt))


def get_date_from_filename(filename):
    m = re.match("^(\d\d\d\d)-(\d\d)-(\d\d)_(\d\d)(\d\d)", filename)
    if m is None:
        return None
    year = int(m.group(1))
    month = int(m.group(2))
    day = int(m.group(3))
    hour = int(m.group(4))
    minute = int(m.group(5))
    return datetime.datetime(year, month, day, hour, minute, 0)


def get_last_date_in_dir(dir):
    lastDate = datetime.datetime.min
    for filename in os.listdir(dir):
        if filename.endswith(".tmp") or filename.endswith("_tmp"):
            continue
        date = get_date_from_filename(filename)
        if date is None:
            continue

        if lastDate < date:
            lastDate = date

    if lastDate == datetime.datetime.min:
        return None
    else:
        return lastDate


def get_date_diff_in_seconds(date, base_date):
    diff = base_date - date
    return (diff.microseconds + (diff.seconds + diff.days * 24 * 3600) * 10**6) / 10**6
