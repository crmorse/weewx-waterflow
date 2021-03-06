# -*- coding: utf-8 -*-
#
#    Copyright (c) 2011, 2012 Tom Keffer <tkeffer@gmail.com>
#
#    See the file LICENSE.txt for your full rights.
#
#    $Revision$
#    $Author$
#    $Date$
#
"""Unit test module weewx.stats"""

from __future__ import with_statement
import os
import sys
import syslog
import time
import unittest
import math

import configobj

import weeutil.weeutil
import weewx.stats
import gen_fake_data
import user.schemas

config_path = "testgen.conf"
cwd = None

class Common(unittest.TestCase):
    
    def setUp(self):
        global config_path
        global cwd
        
        weewx.debug = 1

        syslog.openlog('test_stats', syslog.LOG_CONS)
        syslog.setlogmask(syslog.LOG_UPTO(syslog.LOG_DEBUG))

        # Save and set the current working directory in case some service changes it.
        if not cwd:
            cwd = os.getcwd()
        else:
            os.chdir(cwd)

        try :
            config_dict = configobj.ConfigObj(config_path, file_error=True)
        except IOError:
            sys.stderr.write("Unable to open configuration file %s" % self.config_path)
            # Reraise the exception (this will eventually cause the program to exit)
            raise
        except configobj.ConfigObjError:
            sys.stderr.write("Error while parsing configuration file %s" % config_path)
            raise

        self.archive_db_dict = config_dict['Databases'][self.archive_db]        
        self.stats_db_dict   = config_dict['Databases'][self.stats_db]

        # This will generate the test databases if necessary:
        gen_fake_data.configDatabases(self.archive_db_dict, self.stats_db_dict)
        
    def tearDown(self):
        pass
    
    def test_create_stats(self):
        with weewx.stats.StatsDb.open(self.stats_db_dict) as stats:
            self.assertItemsEqual(sorted(stats.statsTypes), sorted([stat_tuple[0] for stat_tuple in user.schemas.defaultStatsSchema]))
            self.assertEqual(stats.connection.columnsOf('barometer'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count'])
            self.assertEqual(stats.connection.columnsOf('wind'), ['dateTime', 'min', 'mintime', 'max', 'maxtime', 'sum', 'count', 'gustdir', 'xsum', 'ysum', 'squaresum', 'squarecount'])
        
    def testScalarTally(self):
        with weewx.stats.StatsDb.open(self.stats_db_dict) as stats:
            with weewx.archive.Archive.open(self.archive_db_dict) as archive:
                # Pick a random day, say 15 March:
                start_ts = int(time.mktime((2010,3,15,0,0,0,0,0,-1)))
                stop_ts  = int(time.mktime((2010,3,16,0,0,0,0,0,-1)))
                # Sanity check that this is truly the start of day:
                self.assertEqual(start_ts, weeutil.weeutil.startOfDay(start_ts))
        
                allStats = stats._getDayStats(start_ts)
        
                # Test it against some types
                # Should also test monthly, yearly summaries
                for stats_type in ['barometer', 'outTemp', 'rain']:
        
                    # Now test all the aggregates:
                    for aggregate in ['min', 'max', 'sum', 'count', 'avg']:
                        # Compare to the main archive:
                        res = archive.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type), (start_ts, stop_ts))
                        # From StatsDb:
                        allStats_res  = getattr(allStats[stats_type], aggregate)
                        self.assertAlmostEqual(allStats_res, res[0], msg="Value check. Failing type %s, aggregate: %s" % (stats_type, aggregate))
                        
                        # Check the times of min and max as well:
                        if aggregate in ['min','max']:
                            res2 = archive.getSql("SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (stats_type,), (res[0], start_ts, stop_ts))
                            stats_time =  getattr(allStats[stats_type], aggregate+'time')
                            self.assertEqual(stats_time, res2[0], "Time check. Failing type %s, aggregate: %s" % (stats_type, aggregate))
    
    def testWindTally(self):
        with weewx.stats.StatsDb.open(self.stats_db_dict) as stats:
            with weewx.archive.Archive.open(self.archive_db_dict) as archive:
                # Pick a random day, say 15 March:
                start_ts = int(time.mktime((2010,3,15,0,0,0,0,0,-1)))
                stop_ts  = int(time.mktime((2010,3,16,0,0,0,0,0,-1)))
                # Sanity check that this is truly the start of day:
                self.assertEqual(start_ts, weeutil.weeutil.startOfDay(start_ts))
        
                allStats = stats._getDayStats(start_ts)
        
                # Test all the aggregates:
                for aggregate in ['min', 'max', 'sum', 'count', 'avg']:
                    if aggregate == 'max':
                        res = archive.getSql("SELECT MAX(windGust) FROM archive WHERE dateTime>? AND dateTime <=?;", (start_ts, stop_ts))
                    else:
                        res = archive.getSql("SELECT %s(windSpeed) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, ), (start_ts, stop_ts))
        
                    # From StatsDb:
                    allStats_res  = getattr(allStats['wind'], aggregate)
                    self.assertAlmostEqual(allStats_res, res[0])
                    
                    # Check the times of min and max as well:
                    if aggregate == 'min':
                        resmin = archive.getSql("SELECT dateTime FROM archive WHERE windSpeed = ? AND dateTime>? AND dateTime <=?", (res[0], start_ts, stop_ts))
                        self.assertEqual(allStats['wind'].mintime, resmin[0])
                    elif aggregate == 'max':
                        resmax = archive.getSql("SELECT dateTime FROM archive WHERE windGust = ?  AND dateTime>? AND dateTime <=?", (res[0], start_ts, stop_ts))
                        self.assertEqual(allStats['wind'].maxtime, resmax[0])
        
                # Check RMS:
                (squaresum, count) = archive.getSql("SELECT SUM(windSpeed*windSpeed), COUNT(windSpeed) from archive where dateTime>? AND dateTime<=?;", (start_ts, stop_ts))
                rms = math.sqrt(squaresum/count) if count else None
                self.assertAlmostEqual(allStats['wind'].rms, rms)

    def testTags(self):
        with weewx.stats.StatsDb.open(self.stats_db_dict) as stats:
            with weewx.archive.Archive.open(self.archive_db_dict) as archive:

                spans = {'day'  : weeutil.weeutil.TimeSpan(time.mktime((2010,3,15,0,0,0,0,0,-1)),
                                                           time.mktime((2010,3,16,0,0,0,0,0,-1))),
                         'week' : weeutil.weeutil.TimeSpan(time.mktime((2010,3,14,0,0,0,0,0,-1)),
                                                           time.mktime((2010,3,21,0,0,0,0,0,-1))),
                         'month': weeutil.weeutil.TimeSpan(time.mktime((2010,3,01,0,0,0,0,0,-1)),
                                                           time.mktime((2010,4,01,0,0,0,0,0,-1))),
                         'year' : weeutil.weeutil.TimeSpan(time.mktime((2010,1,01,0,0,0,0,0,-1)),
                                                           time.mktime((2011,1,01,0,0,0,0,0,-1)))}
        
                # This may not necessarily execute in the order specified above:
                for span in spans:
                    
                    start_ts = spans[span].start
                    stop_ts  = spans[span].stop
                    tagStats = weewx.stats.TaggedStats(stats, stop_ts,
                                                       rain_year_start=1, 
                                                       heatbase=(65.0, 'degree_F', 'group_temperature'),
                                                       coolbase=(65.0, 'degree_F', 'group_temperature'))
                    
                    # Cycle over the statistical types:
                    for stats_type in ('barometer', 'outTemp', 'rain'):
                    
                        # Now test all the aggregates:
                        for aggregate in ('min', 'max', 'sum', 'count', 'avg'):
                            # Compare to the main archive:
                            res = archive.getSql("SELECT %s(%s) FROM archive WHERE dateTime>? AND dateTime <=?;" % (aggregate, stats_type), (start_ts, stop_ts))
                            archive_result = res[0]
                            # This is how you form a tag such as tagStats.month.barometer.avg when
                            # all you have is strings holding the attributes:
                            value_helper = getattr(getattr(getattr(tagStats, span), stats_type), aggregate)
                            self.assertAlmostEqual(float(str(value_helper.formatted)), archive_result, places=1)
                            
                            # Check the times of min and max as well:
                            if aggregate in ('min','max'):
                                res2 = archive.getSql("SELECT dateTime FROM archive WHERE %s = ? AND dateTime>? AND dateTime <=?" % (stats_type,), (archive_result, start_ts, stop_ts))
                                stats_value_helper = getattr(getattr(getattr(tagStats, span), stats_type), aggregate +'time')
                                self.assertEqual(stats_value_helper.raw, res2[0])
        
                self.assertEqual(str(tagStats.day.barometer.avg), "30.675 inHg")
                self.assertEqual(str(tagStats.day.barometer.min), "30.065 inHg")
                self.assertEqual(str(tagStats.day.barometer.max), "31.000 inHg")
                self.assertEqual(str(tagStats.day.barometer.mintime), "00:00")
                self.assertEqual(str(tagStats.day.barometer.maxtime), "01:00")
                self.assertEqual(str(tagStats.week.barometer.avg), "29.904 inHg")
                self.assertEqual(str(tagStats.week.barometer.min), "29.000 inHg")
                self.assertEqual(str(tagStats.week.barometer.max), "31.000 inHg")
                self.assertEqual(str(tagStats.week.barometer.mintime), "01:00 on Monday")
                self.assertEqual(str(tagStats.week.barometer.maxtime), "01:00 on Wednesday")
                self.assertEqual(str(tagStats.month.barometer.avg), "30.021 inHg")
                self.assertEqual(str(tagStats.month.barometer.min), "29.000 inHg")
                self.assertEqual(str(tagStats.month.barometer.max), "31.000 inHg")
                self.assertEqual(str(tagStats.month.barometer.mintime), "05-Mar-2010 00:00")
                self.assertEqual(str(tagStats.month.barometer.maxtime), "03-Mar-2010 00:00")
                self.assertEqual(str(tagStats.year.barometer.avg), "30.002 inHg")
                self.assertEqual(str(tagStats.year.barometer.min), "29.000 inHg")
                self.assertEqual(str(tagStats.year.barometer.max), "31.000 inHg")
                self.assertEqual(str(tagStats.year.barometer.mintime), "04-Jan-2010 00:00")
                self.assertEqual(str(tagStats.year.barometer.maxtime), "02-Jan-2010 00:00")
                self.assertEqual(str(tagStats.day.outTemp.avg), "38.8°F")
                self.assertEqual(str(tagStats.day.outTemp.min), "18.6°F")
                self.assertEqual(str(tagStats.day.outTemp.max), "59.0°F")
                self.assertEqual(str(tagStats.day.outTemp.mintime), "07:00")
                self.assertEqual(str(tagStats.day.outTemp.maxtime), "19:00")
                self.assertEqual(str(tagStats.week.outTemp.avg), "38.8°F")
                self.assertEqual(str(tagStats.week.outTemp.min), "16.6°F")
                self.assertEqual(str(tagStats.week.outTemp.max), "61.0°F")
                self.assertEqual(str(tagStats.week.outTemp.mintime), "07:00 on Sunday")
                self.assertEqual(str(tagStats.week.outTemp.maxtime), "19:00 on Saturday")
                self.assertEqual(str(tagStats.month.outTemp.avg), "28.7°F")
                self.assertEqual(str(tagStats.month.outTemp.min), "-0.9°F")
                self.assertEqual(str(tagStats.month.outTemp.max), "59.0°F")
                self.assertEqual(str(tagStats.month.outTemp.mintime), "01-Mar-2010 06:00")
                self.assertEqual(str(tagStats.month.outTemp.maxtime), "31-Mar-2010 19:00")
                self.assertEqual(str(tagStats.year.outTemp.avg), "40.0°F")
                self.assertEqual(str(tagStats.year.outTemp.min), "-20.0°F")
                self.assertEqual(str(tagStats.year.outTemp.max), "100.0°F")
                self.assertEqual(str(tagStats.year.outTemp.mintime), "01-Jan-2010 06:00")
                self.assertEqual(str(tagStats.year.outTemp.maxtime), "02-Jul-2010 19:00")
                
                # Check the special aggregate types "exists" and "has_data":
                self.assertTrue(tagStats.year.barometer.exists)
                self.assertTrue(tagStats.year.barometer.has_data)
                self.assertFalse(tagStats.year.bar.exists)
                self.assertFalse(tagStats.year.bar.has_data)
                self.assertTrue(tagStats.year.inHumidity.exists)
                self.assertFalse(tagStats.year.inHumidity.has_data)

    def test_rainYear(self):
        with weewx.stats.StatsDb.open(self.stats_db_dict) as stats:
            stop_ts = time.mktime((2011,1,01,0,0,0,0,0,-1))
            # Check for a rain year starting 1-Jan
            tagStats = weewx.stats.TaggedStats(stats, stop_ts,
                                               rain_year_start=1)
                
            self.assertEqual(str(tagStats.rainyear.rain.sum), "86.59 in")
    
            # Do it again, for starting 1-Oct:
            tagStats = weewx.stats.TaggedStats(stats, stop_ts,
                                               rain_year_start=10)
            self.assertEqual(str(tagStats.rainyear.rain.sum), "21.89 in")


    def test_heatcool(self):
        with weewx.stats.StatsDb.open(self.stats_db_dict) as stats:
            #Test heating and cooling degree days:
            stop_ts = time.mktime((2011,1,01,0,0,0,0,0,-1))
    
            tagStats = weewx.stats.TaggedStats(stats, stop_ts,
                                               heatbase=(65.0, 'degree_F', 'group_temperature'),
                                               coolbase=(65.0, 'degree_F', 'group_temperature'))
                
            self.assertEqual(str(tagStats.year.heatdeg.sum), "10150.7°F-day")
            self.assertEqual(str(tagStats.year.cooldeg.sum), "1026.2°F-day")
    




class TestSqlite(Common):

    def __init__(self, *args, **kwargs):
        self.archive_db = "archive_sqlite"
        self.stats_db   = "stats_sqlite"
        super(TestSqlite, self).__init__(*args, **kwargs)
        
class TestMySQL(Common):
    
    def __init__(self, *args, **kwargs):
        self.archive_db = "archive_mysql"
        self.stats_db   = "stats_mysql"
        super(TestMySQL, self).__init__(*args, **kwargs)
        
    
def suite():
    tests = ['test_create_stats', 'testScalarTally', 'testWindTally', 
             'testTags', 'test_rainYear', 'test_heatcool']
    return unittest.TestSuite(map(TestSqlite, tests) + map(TestMySQL, tests))

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(suite())
