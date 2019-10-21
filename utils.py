import pytz
import datetime as dt
__tz__ = pytz.timezone("Asia/Singapore")


def get_singapore_time_now():
    now = dt.datetime.utcnow()
    offset = __tz__.utcoffset(now)
    return now + offset


def equal_hour_minute(time1, time2):
    return time1.hour == time2.hour and time1.minute == time2.minute


def time_shifted_back_hours(t, hour_offset):
    new_hour = t.hour - hour_offset
    if new_hour < 0:
        new_hour = 24 + new_hour
    return t.replace(hour=new_hour)