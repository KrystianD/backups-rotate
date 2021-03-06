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

def get_date_from_filename(filename):
    m = re.match("^(\d\d\d\d)-(\d\d)-(\d\d)_(\d\d)(\d\d)(\d\d)", filename)
    if m is not None:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        seconds = int(m.group(6))
        return datetime.datetime(year, month, day, hour, minute, seconds)
    m = re.match("^(\d\d\d\d)-(\d\d)-(\d\d)_(\d\d)(\d\d)", filename)
    if m is not None:
        year = int(m.group(1))
        month = int(m.group(2))
        day = int(m.group(3))
        hour = int(m.group(4))
        minute = int(m.group(5))
        return datetime.datetime(year, month, day, hour, minute, 0)
    return None


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

def is_valid_filename_char(x):
    if x.isalnum():
        return True
    if x == '_':
        return True
    return False

def get_valid_filename(s):
    s = s.replace(" ", "_")
    return "".join(x for x in s if is_valid_filename_char(x))
