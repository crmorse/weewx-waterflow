#
#    Copyright (c) 2009, 2010 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Various handy utilities that don't belong anywhere else."""

import StringIO
import calendar
import datetime
import math
import syslog
import time
import traceback

import configobj

import Sun

def convertToFloat(seq):
    """Convert a sequence with strings to floats, honoring 'Nones'"""
    
    if seq is None: return None
    res = [None if s in ('None', 'none') else float(s) for s in seq]
    return res

def accumulateLeaves(d):
    """Merges leaf options above a ConfigObj section with itself, accumulating the results.
    
    This routine is useful for specifying defaults near the root node, 
    then having them overridden in the leaf nodes of a ConfigObj.
    
    d: instance of a configobj.Section (i.e., a section of a ConfigObj)
    """
    
    # Use recursion. If I am the root object, then there is nothing above 
    # me to accumulate. Start with a virgin ConfigObj
    if d.parent is d :
        cum_dict = configobj.ConfigObj()
    else :
        # Otherwise, recursively accumulate scalars above me
        cum_dict = accumulateLeaves(d.parent)
        
    # Now merge my scalars into the results:
    merge_dict = {}
    for k in d.scalars :
        merge_dict[k] = d[k]
    cum_dict.merge(merge_dict)
    return cum_dict

def option_as_list(option):
    if option is None: return None
    if hasattr(option, '__iter__'):
        return option
    return [option]

def stampgen(startstamp, stopstamp, interval):
    """Generator function yielding a sequence of timestamps, spaced interval apart.
    
    The sequence will fall on the same local time boundary as startstamp. 

    Example:
    
    >>> startstamp = 1236560400
    >>> print timestamp_to_string(startstamp)
    2009-03-08 18:00:00 PDT (1236560400)
    >>> stopstamp = 1236607200
    >>> print timestamp_to_string(stopstamp)
    2009-03-09 07:00:00 PDT (1236607200)
    
    >>> for stamp in stampgen(startstamp, stopstamp, 10800):
    ...     print timestamp_to_string(stamp)
    2009-03-08 18:00:00 PDT (1236560400)
    2009-03-08 21:00:00 PDT (1236571200)
    2009-03-09 00:00:00 PDT (1236582000)
    2009-03-09 03:00:00 PDT (1236592800)
    2009-03-09 06:00:00 PDT (1236603600)

    Note that DST started in the middle of the sequence and that therefore the
    actual time deltas between stamps is not necessarily 3 hours.
    
    startstamp: The start of the sequence in unix epoch time.
    
    stopstamp: The end of the sequence in unix epoch time. 
    
    interval: The time length of an interval in seconds.
    
    yields a sequence of timestamps between startstamp and endstamp, inclusive.
    """
    dt = datetime.datetime.fromtimestamp(startstamp)
    stop_dt = datetime.datetime.fromtimestamp(stopstamp)
    if interval == 365.25 / 12 * 24 * 3600 :
        # Interval is a nominal month. This algorithm is 
        # necessary because not all months have the same length.
        while dt <= stop_dt :
            t_tuple = dt.timetuple()
            yield time.mktime(t_tuple)
            year = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12 :
                month -= 12
                year += 1
            dt = dt.replace(year=year, month=month)
    else :
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval
        delta = datetime.timedelta(seconds=interval)
        while dt <= stop_dt :
            yield int(time.mktime(dt.timetuple()))
            dt += delta

def intervalgen(start_ts, stop_ts, interval):
    """Generator function yielding a sequence of time intervals.
    
    Yields a sequence of intervals. First interval is (start_ts, start_ts+interval),
    second is (start_ts+interval, start_ts+2*interval), etc. The last interval
    will end at or before stop_ts. It is up to the consumer to interpret whether
    the end points of any given interval is inclusive or exclusive to the
    interval.
    
    Example:
    
    >>> startstamp = 1236560400
    >>> print timestamp_to_string(startstamp)
    2009-03-08 18:00:00 PDT (1236560400)
    >>> stopstamp = 1236607200
    >>> print timestamp_to_string(stopstamp)
    2009-03-09 07:00:00 PDT (1236607200)
    
    >>> for start,stop in intervalgen(startstamp, stopstamp, 10800):
    ...     print timestamp_to_string(start), timestamp_to_string(stop)
    2009-03-08 18:00:00 PDT (1236560400) 2009-03-08 21:00:00 PDT (1236571200)
    2009-03-08 21:00:00 PDT (1236571200) 2009-03-09 00:00:00 PDT (1236582000)
    2009-03-09 00:00:00 PDT (1236582000) 2009-03-09 03:00:00 PDT (1236592800)
    2009-03-09 03:00:00 PDT (1236592800) 2009-03-09 06:00:00 PDT (1236603600)
    2009-03-09 06:00:00 PDT (1236603600) 2009-03-09 07:00:00 PDT (1236607200)

    start_ts: The start of the first interval in unix epoch time.
    
    stop_ts: The end of the last interval will be equal to or less than this.
    In unix epoch time.
    
    interval: The time length of an interval in seconds.
    
    yields: A sequence of 2-tuples. First value is start of the interval, second 
    is the end. Both the start and end will be on the same time boundary as
    start_ts"""  

    dt1 = datetime.datetime.fromtimestamp(start_ts)
    stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    if interval == 365.25 / 12 * 24 * 3600 :
        # Interval is a nominal month. This algorithm is 
        # necessary because not all months have the same length.
        while dt1 < stop_dt :
            t_tuple = dt1.timetuple()
            year = t_tuple[0]
            month = t_tuple[1]
            month += 1
            if month > 12 :
                month -= 12
                year += 1
            dt2 = min(dt1.replace(year=year, month=month), stop_dt)
            stamp1 = time.mktime(t_tuple)
            stamp2 = time.mktime(dt2.timetuple())
            yield (stamp1, stamp2)
            dt1 = dt2
    else :
        # This rather complicated algorithm is necessary (rather than just
        # doing some time stamp arithmetic) because of the possibility that DST
        # changes in the middle of an interval
        delta = datetime.timedelta(seconds=interval)
        while dt1 < stop_dt :
            dt2 = min(dt1 + delta, stop_dt)
            stamp1 = time.mktime(dt1.timetuple())
            stamp2 = time.mktime(dt2.timetuple())
            yield (stamp1, stamp2)
            dt1 = dt2

def startOfInterval(time_ts, interval, grace=1):
    """Find the start time of an interval.
    
    This algorithm assumes the day is divided up into
    intervals of 'interval' length. Given a timestamp, it
    figures out which interval it lies in, returning the start
    time.
    
    Examples (human readable times shown instead of timestamps):
    
      time_ts     interval    returns
      01:57:35       300      01:55:00
      01:57:35       600      01:50:00
      01:57:35       900      01:45:00
      01:57:35      3600      01:00:00
      01:57:35      7200      00:00:00
      01:00:00       300      00:55:00
    
    time_ts: A timestamp. The start of the interval containing this
    timestamp will be returned.
    
    interval: An interval length in seconds.
    
    grace: A time this many seconds into an interval is still
    included in the last interval. Set to zero to have an
    inclusive start of an interval. [Optional. Default is 1 second.]
    
    Returns: A timestamp with the start of the interval."""

    interval_m = interval/60
    interval_h = interval/3600
    time_tt = time.localtime(time_ts - grace)
    m = time_tt.tm_min  // interval_m * interval_m
    h = time_tt.tm_hour // interval_h * interval_h if interval_h > 1 else time_tt.tm_hour

    # Replace the hour, minute, and seconds with the start of the interval.
    # Everything else gets retained:
    start_interval_ts = time.mktime((time_tt.tm_year,
                                     time_tt.tm_mon,
                                     time_tt.tm_mday,
                                     h, m, 0,
                                     0, 0, time_tt.tm_isdst))
    return int(start_interval_ts)

def _ord_to_ts(_ord):
    d = datetime.date.fromordinal(_ord)
    t = int(time.mktime(d.timetuple()))
    return t

#===============================================================================
# What follows is a bunch of "time span" routines. Generally, time spans
# are used when start and stop times fall on calendar boundaries
# such as days, months, years.  So, it makes sense to talk of "daySpans",
# "weekSpans", etc. They are generally not used between two random times. 
#===============================================================================

class TimeSpan(object):
    '''
    Represents a time span, exclusive on the left, inclusive on the right.
    '''

    def __init__(self, start_ts, stop_ts):
        '''
        Initialize a new instance of TimeSpan to the interval start_ts, stop_ts.
        
        start_ts: The starting time stamp of the interval.
        
        stop_ts: The stopping time stamp of the interval
        '''
        
        self.start = int(start_ts)
        self.stop = int(stop_ts)
        if self.start > self.stop:
            raise ValueError, "start time (%d) is greater than stop time (%d)" % (self.start, self.stop)
        
    def includesArchiveTime(self, timestamp):
        """
        Returns True if the span includes the time timestamp, otherwise False.
        
        timestamp: The timestamp to be tested.
        """
        return self.start < timestamp <= self.stop
    
    def includes(self, span):
        
        return self.start <= span.start <= self.stop and self.start <= span.stop <= self.stop
    
    def __eq__(self, other):
        return self.start == other.start and self.stop == other.stop
    
    def __str__(self):
        return "[%s -> %s]" % (timestamp_to_string(self.start),
                               timestamp_to_string(self.stop))
        
    def __hash__(self):
        return hash(self.start) ^ hash(self.stop)
    
    def __cmp__(self, other):
        if self.start < other.start :
            return - 1
        return 0 if self.start == other.start else 1

def archiveDaySpan(time_ts, grace=1):
    """Returns a TimeSpan representing a day that includes a given time.
    
    Midnight is considered to actually belong in the previous day if
    grace is greater than zero.
    
    Examples: (Assume grace is 1; printed times are given below, but
    the variables are actually in unix epoch timestamps)
        2007-12-3 18:12:05 returns (2007-12-3 00:00:00 to 2007-12-4 00:00:00)
        2007-12-3 00:00:00 returns (2007-12-2 00:00:00 to 2007-12-3 00:00:00)
        2007-12-3 00:00:01 returns (2007-12-3 00:00:00 to 2007-12-4 00:00:00)
    
    time_ts: The day will include this timestamp. 
    
    grace: This many seconds past midnight marks the start of the next
    day. Set to zero to have midnight be included in the
    following day.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one day long that contains time_ts. It
    will begin and end at midnight.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _day_ord = _day_date.toordinal()
    return TimeSpan(_ord_to_ts(_day_ord), _ord_to_ts(_day_ord + 1))

def archiveWeekSpan(time_ts, startOfWeek=6, grace=1):
    """Returns a TimeSpan representing a week that includes a given time.
    
    The time at midnight at the end of the week is considered to
    actually belong in the previous week.
    
    time_ts: The week will include this timestamp. 
    
    startOfWeek: The start of the week (0=Monday, 1=Tues, ..., 6 = Sun).

    grace: This many seconds past midnight marks the start of the next
    week. Set to zero to have midnight be included in the
    following week.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one week long that contains time_ts. It will
    start at midnight of the day considered the start of the week, and be
    one week long.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _day_of_week = _day_date.weekday()
    _delta = _day_of_week - startOfWeek
    if _delta < 0: _delta += 7
    _sunday_date = _day_date - datetime.timedelta(days=_delta)
    _next_sunday_date = _sunday_date + datetime.timedelta(days=7)
    return TimeSpan(int(time.mktime(_sunday_date.timetuple())),
                             int(time.mktime(_next_sunday_date.timetuple())))

def archiveMonthSpan(time_ts, grace=1):
    """Returns a TimeSpan representing a month that includes a given time.
    
    Midnight of the 1st of the month is considered to actually belong
    in the previous month.
    
    time_ts: The month will include this timestamp. 
    
    grace: This many seconds past midnight marks the start of the next
    month. Set to zero to have midnight be included in the
    following month.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one month long that contains time_ts.
    It will start at midnight of the start of the month, and end at midnight
    of the start of the next month.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _month_date = _day_date.replace(day=1)
    _yr = _month_date.year
    _mo = _month_date.month + 1
    if _mo == 13:
        _mo = 1
        _yr += 1
    _next_month_date = datetime.date(_yr, _mo, 1)
    
    return TimeSpan(int(time.mktime(_month_date.timetuple())),
                             int(time.mktime(_next_month_date.timetuple())))

def archiveYearSpan(time_ts, grace=1):
    """Returns a TimeSpan representing a year that includes a given time.
    
    Midnight of the 1st of the January is considered to actually belong
    in the previous year.
    
    time_ts: The year will include this timestamp. 
    
    grace: This many seconds past midnight marks the start of the next
    year. Set to zero to have midnight be included in the
    following year.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one year long that contains time_ts. It will
    begin and end at midnight 1-Jan.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    return TimeSpan(int(time.mktime((_day_date.year, 1, 1, 0, 0, 0, 0, 0, -1))),
                             int(time.mktime((_day_date.year + 1, 1, 1, 0, 0, 0, 0, 0, -1))))

def archiveRainYearSpan(time_ts, sory_mon, grace=1):
    """Returns a TimeSpan representing a rain year that includes a given time.
    
    Midnight of the 1st of the month starting the rain year is considered to
    actually belong in the previous rain year.
    
    time_ts: The rain year will include this timestamp. 
    
    sory_mon: The month the rain year starts.
    
    grace: This many seconds past midnight marks the start of the next
    rain year. Set to zero to have midnight be included in the
    following rain year.  [Optional. Default is 1 second.]
    
    returns: A TimeSpan object one year long that contains time_ts. It will
    begin on the 1st of the month that starts the rain year.
    """
    if time_ts is None:
        return None
    time_ts -= grace
    _day_date = datetime.date.fromtimestamp(time_ts)
    _year = _day_date.year if _day_date.month >= sory_mon else _day_date.year - 1
    return TimeSpan(int(time.mktime((_year, sory_mon, 1, 0, 0, 0, 0, 0, -1))),
                             int(time.mktime((_year + 1, sory_mon, 1, 0, 0, 0, 0, 0, -1))))

def genDaySpans(start_ts, stop_ts):
    """Generator function that generates start/stop of days in an inclusive range.
    
    Example:
    
    >>> start_ts = 1204796460
    >>> stop_ts  = 1205265720
    
    >>> print timestamp_to_string(start_ts)
    2008-03-06 01:41:00 PST (1204796460)
    >>> print timestamp_to_string(stop_ts)
    2008-03-11 13:02:00 PDT (1205265720)
    
    >>> for span in genDaySpans(start_ts, stop_ts):
    ...   print span
    [2008-03-06 00:00:00 PST (1204790400) -> 2008-03-07 00:00:00 PST (1204876800)]
    [2008-03-07 00:00:00 PST (1204876800) -> 2008-03-08 00:00:00 PST (1204963200)]
    [2008-03-08 00:00:00 PST (1204963200) -> 2008-03-09 00:00:00 PST (1205049600)]
    [2008-03-09 00:00:00 PST (1205049600) -> 2008-03-10 00:00:00 PDT (1205132400)]
    [2008-03-10 00:00:00 PDT (1205132400) -> 2008-03-11 00:00:00 PDT (1205218800)]
    [2008-03-11 00:00:00 PDT (1205218800) -> 2008-03-12 00:00:00 PDT (1205305200)]
    
    Note that a daylight savings time change happened 8 March 2009.

    start_ts: A time stamp somewhere in the first day.
    
    stop_ts: A time stamp somewhere in the last day.
    
    yields: Instance of TimeSpan, where the start is the time stamp
    of the start of the day, the stop is the time stamp of the start
    of the next day.
    
    """
    _start_dt = datetime.datetime.fromtimestamp(start_ts)
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    _start_ord = _start_dt.toordinal()
    _stop_ord = _stop_dt.toordinal()
    if (_stop_dt.hour, _stop_dt.minute, _stop_dt.second) == (0, 0, 0):
        _stop_ord -= 1

    for _ord in range(_start_ord, _stop_ord + 1):
        yield TimeSpan(_ord_to_ts(_ord), _ord_to_ts(_ord + 1))
 
   
def genMonthSpans(start_ts, stop_ts):
    """Generator function that generates start/stop of months in an
    inclusive range.
    
    Example:
    
    >>> start_ts = 1196705700
    >>> stop_ts  = 1206101100
    >>> print "start time is", timestamp_to_string(start_ts)
    start time is 2007-12-03 10:15:00 PST (1196705700)
    >>> print "stop time is ", timestamp_to_string(stop_ts)
    stop time is  2008-03-21 05:05:00 PDT (1206101100)
    
    >>> for span in genMonthSpans(start_ts, stop_ts):
    ...   print span
    [2007-12-01 00:00:00 PST (1196496000) -> 2008-01-01 00:00:00 PST (1199174400)]
    [2008-01-01 00:00:00 PST (1199174400) -> 2008-02-01 00:00:00 PST (1201852800)]
    [2008-02-01 00:00:00 PST (1201852800) -> 2008-03-01 00:00:00 PST (1204358400)]
    [2008-03-01 00:00:00 PST (1204358400) -> 2008-04-01 00:00:00 PDT (1207033200)]
    
    Note that a daylight savings time change happened 8 March 2009.

    start_ts: A time stamp somewhere in the first month.
    
    stop_ts: A time stamp somewhere in the last month.
    
    yields: Instance of TimeSpan, where the start is the time stamp
    of the start of the month, the stop is the time stamp of the start
    of the next month.
    """
    if None in (start_ts, stop_ts):
        return
    _start_dt = datetime.date.fromtimestamp(start_ts)
    _stop_date = datetime.datetime.fromtimestamp(stop_ts)

    _start_month = 12 * _start_dt.year + _start_dt.month
    _stop_month = 12 * _stop_date.year + _stop_date.month

    if (_stop_date.day, _stop_date.hour, _stop_date.minute, _stop_date.second) == (1, 0, 0, 0):
        _stop_month -= 1

    for month in range(_start_month, _stop_month + 1):
        _this_yr, _this_mo = divmod(month, 12)
        _next_yr, _next_mo = divmod(month + 1, 12)
        yield TimeSpan(time.mktime((_this_yr, _this_mo, 1, 0, 0, 0, 0, 0, -1)),
                       time.mktime((_next_yr, _next_mo, 1, 0, 0, 0, 0, 0, -1)))

def genYearSpans(start_ts, stop_ts):
    if None in (start_ts, stop_ts):
        return
    _start_date = datetime.date.fromtimestamp(start_ts)
    _stop_dt = datetime.datetime.fromtimestamp(stop_ts)
    
    _start_year = _start_date.year
    _stop_year = _stop_dt.year
    
    if(_stop_dt.month, _stop_dt.day, _stop_dt.hour,
       _stop_dt.minute, _stop_dt.second) == (1, 1, 0, 0, 0):
        _stop_year -= 1
        
    for year in range(_start_year, _stop_year + 1):
        yield TimeSpan(time.mktime((year, 1, 1, 0, 0, 0, 0, 0, -1)),
                       time.mktime((year + 1, 1, 1, 0, 0, 0, 0, 0, -1)))
        
def startOfDay(time_ts):
    """Calculate the unix epoch time for the start of a (local time) day.
    
    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time.
    
    """
    _time_tt = time.localtime(time_ts)
    _bod_ts = time.mktime((_time_tt.tm_year,
                            _time_tt.tm_mon,
                            _time_tt.tm_mday,
                            0, 0, 0, 0, 0, -1))
    return int(_bod_ts)


def startOfArchiveDay(time_ts, grace=1):
    """Given an archive time stamp, calculate its start of day.
    
    similar to startOfDay(), except that an archive stamped at midnight
    actually belongs to the *previous* day.

    time_ts: A timestamp somewhere in the day for which the start-of-day
    is desired.
    
    grace: The number of seconds past midnight when the following
    day is considered to start [Optional. Default is 1 second]
    
    returns: The timestamp for the start-of-day (00:00) in unix epoch time."""
    
    return startOfDay(time_ts - grace)

def getDayNightTransitions(start_ts, end_ts, lat, lon):
    """Return the day-night transitions between the start and end times.

    start_ts: A timestamp indicating the beginning of the period

    end_ts: A timestamp indicating the end of the period

    returns: indication of whether the period from start to first transition
    is day or night, plus array of transitions.
    """
    first = 'day'
    values = []
    for t in range(start_ts, end_ts, 3600*24):
        x = startOfDay(t) + 7200 # avoid dst issues
        
        x_tt = time.gmtime(x)
        y, m, d = x_tt[:3]
        (sunrise_utc, sunset_utc) = Sun.sunRiseSet(y, m, d, lon, lat)

        # The above function returns its results in UTC hours. Convert
        # to a local time tuple, then to a timestamp.
        sunrise_tt = utc_to_local_tt(y, m, d, sunrise_utc)
        sunset_tt  = utc_to_local_tt(y, m, d, sunset_utc)
        sunrise_ts = time.mktime(sunrise_tt)
        sunset_ts  = time.mktime(sunset_tt)        

        if start_ts < sunrise_ts < end_ts:
            values.append(sunrise_ts)
        if start_ts < sunset_ts < end_ts:
            values.append(sunset_ts)
        if t == start_ts and (start_ts < sunrise_ts or sunset_ts < start_ts):
            first = 'night'
    return first, values
    
def secs_to_string(secs):
    """Convert seconds to a string with days, hours, and minutes"""
    str_list = []
    for (label, interval) in (('day', 86400), ('hour', 3600), ('minute', 60)):
        amt = int(secs / interval)
        plural = '' if amt == 1 else 's'
        str_list.append("%d %s%s" % (amt, label, plural))
        secs %= interval
    ans = ', '.join(str_list)
    return ans

def timestamp_to_string(ts):
    """Return a string formatted from the timestamp
    
    Example:

    >>> print timestamp_to_string(1196705700)
    2007-12-03 10:15:00 PST (1196705700)
    >>> print timestamp_to_string(None)
    ******* N/A *******     (    N/A   )
    """
    if ts:
        return "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime(ts)), ts)
    else:
        return "******* N/A *******     (    N/A   )"

def timestamp_to_gmtime(ts):
    """Return a string formatted for GMT
    
    >>> print timestamp_to_gmtime(1196705700)
    2007-12-03 18:15:00 UTC (1196705700)
    >>> print timestamp_to_gmtime(None)
    ******* N/A *******     (    N/A   )
    """
    if ts:
        return "%s (%d)" % (time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts)), ts)
    else:
        return "******* N/A *******     (    N/A   )"
        
    
def utcdatetime_to_timestamp(dt):
    """Convert from a datetime object holding a UTC time, to a unix timestamp.
    
    dt: An instance of datetime.datetime holding the time in UTC.
    
    Returns: A timestamp
    
    Example (using 17-Jan-2011 19:21:05 UTC):
    
        >>> dt_utc = datetime.datetime(2011, 1, 17, 19, 21, 5)
        >>> ts = utcdatetime_to_timestamp(dt_utc)
        >>> print "%s UTC (unix epoch time %.1f)" % (time.asctime(time.gmtime(ts)), ts)
        Mon Jan 17 19:21:05 2011 UTC (unix epoch time 1295292065.0)
    """
    # Amazingly, Python offers no easy way to do this. Here's the best
    # hack I can some up with:
    return time.mktime(dt.utctimetuple()) - time.timezone

def utc_to_local_tt(y, m, d,  hrs_utc):
    """Converts from a UTC time to a local time.
    
    y,m,d: The year, month, day for which the conversion is desired.
    
    hrs_tc: Floating point number with the number of hours since midnight in UTC.
    
    Returns: A timetuple with the local time."""
    # Construct a time tuple with the time at midnight, UTC:
    daystart_utc_tt = (y,m,d,0,0,0,0,0,-1)
    # Convert the time tuple to a time stamp and add on the number of seconds since midnight:
    time_ts = int(calendar.timegm(daystart_utc_tt) + hrs_utc * 3600.0 + 0.5)
    # Convert to local time:
    time_local_tt = time.localtime(time_ts)
    return time_local_tt

def latlon_string(ll, hemi, which):
    """Decimal degrees into a string for degrees, and one for minutes."""
    labs = abs(ll)
    (frac, deg) = math.modf(labs)
    minutes = frac * 60.0
    return (("%02d" if which == 'lat' else "%03d") % (deg,), "%05.2f" % (minutes,), hemi[0] if ll >= 0 else hemi[1])

def utf8_to_latin1(instring):
    """Convert from UTF-8 to Latin-1 encoding."""
    return unicode(instring, "utf8").encode("latin1")

def log_traceback(prefix=''):
    """Log the stack traceback into syslog."""
    sfd = StringIO.StringIO()
    traceback.print_exc(file=sfd)
    sfd.seek(0)
    for line in sfd:
        syslog.syslog(syslog.LOG_INFO, prefix + line)
    del sfd
    
def _get_object(module_class, *args, **kwargs):
    """Given a path to a class, instantiates an instance of the class with the given args and returns it."""
    # Split the path into its parts
    parts = module_class.split('.')
    # Strip off the classname:
    module = '.'.join(parts[:-1])
    # Import the top level module
    mod = __import__(module)
    # Then recursively work down from the top level module to the class name:
    for part in parts[1:]:
        mod = getattr(mod, part)
    # Instance 'mod' will now be a class. Instantiate an instance and return it:
    obj = mod(*args, **kwargs)
    return obj

class GenWithPeek(object):
    """Generator object which allows a peek at the next object to be returned.
    
    Sometimes Python solves a complicated problem with such elegance! This is
    one of them.
    
    Example of usage:
    >>> # Define a generator function:
    >>> def genfunc(N):
    ...     for i in range(N):
    ...        yield i
    >>>
    >>> # Now wrap it with the GenWithPeek object:
    >>> g_with_peek = GenWithPeek(genfunc(5))
    >>> # We can iterate through the object as normal:
    >>> for i in g_with_peek:
    ...    print i
    ...    # Every second object, let's take a peek ahead
    ...    if i%2:
    ...        # We can get a peek at the next object without disturbing the wrapped generator:
    ...        print "peeking ahead, the next object will be: ", g_with_peek.peek()
    0
    1
    peeking ahead, the next object will be:  2
    2
    3
    peeking ahead, the next object will be:  4
    4
    """
    
    def __init__(self, generator):
        """Initialize the generator object.
        
        generator: A generator object to be wrapped
        """
        self.generator = generator
        self.have_peek = False
        
    def __iter__(self):
        return self
    
    def next(self):  #@ReservedAssignment
        """Advance to the next object"""
        if self.have_peek:
            self.have_peek = False
            return self.peek_obj
        else:
            return self.generator.next()
        
    def peek(self):
        """Take a peek at the next object"""
        if not self.have_peek:
            self.peek_obj = self.generator.next()
            self.have_peek = True
        return self.peek_obj

def tobool(x):
    """Convert an object to boolean.
    
    Examples:
    >>> print tobool('TRUE')
    True
    >>> print tobool(True)
    True
    >>> print tobool(1)
    True
    >>> print tobool('FALSE')
    False
    >>> print tobool(False)
    False
    >>> print tobool(0)
    False
    >>> print tobool('Foo')
    Traceback (most recent call last):
    ValueError: Unknown boolean specifier: 'Foo'.
    >>> print tobool(None)
    Traceback (most recent call last):
    ValueError: Unknown boolean specifier: 'None'.
    """

    try:
        if x.lower() == 'true':
            return True
        elif x.lower() == 'false':
            return False
    except AttributeError:
        pass
    try:
        return bool(int(x))
    except (ValueError, TypeError):
        pass
    raise ValueError("Unknown boolean specifier: '%s'." % x)
    
if __name__ == '__main__':
    import doctest

    if not doctest.testmod().failed:
        print "PASSED"
