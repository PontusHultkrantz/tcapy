"""Tests functions for downloading data from New Change FX (NCFX) - an external data source and also dumping to disk
"""

__author__ = 'saeedamen'  # Saeed Amen / saeed@cuemacro.com

#
# Copyright 2017 Cuemacro Ltd. - http//www.cuemacro.com / @cuemacro
#
# See the License for the specific language governing permissions and limitations under the License.
#

import pytz

import pandas as pd

try:
    from pandas.testing import assert_frame_equal
except:
    from pandas.util.testing import assert_frame_equal

import glob
import os

from tcapy.conf.constants import Constants
from tcapy.util.loggermanager import LoggerManager
from tcapy.util.utilfunc import UtilFunc

from tcapy.data.databasepopulator import DatabasePopulatorNCFX, DatabasePopulatorDukascopy
from tcapy.data.databasesource import DatabaseSourceNCFX, DatabaseSourceDukascopy

from collections import OrderedDict

logger = LoggerManager().getLogger(__name__)

constants = Constants()
util_func = UtilFunc()

# check that your database has market and trade data for these before running the test
# check that you have created appropriate folders for storing data

logger.info('Make sure you have created folder ' + constants.csv_folder + ' & ' + constants.temp_data_folder +
            ' otherwise tests will fail')

########################################################################################################################
# YOU MAY NEED TO CHANGE THESE

# market_data_store = 'arctic-ncfx'
# trade_data_store = 'ms_sql_server'

start_date = '26 Apr 2017'
finish_date = '05 Jun 2017'
ticker = 'EURUSD'

# mainly just to speed up tests - note: you will need to generate the HDF5 files using convert_csv_to_h5.py from the CSVs
use_hdf5_market_files = True

test_harness_data_store = 'arctic-testharness'
test_harness_sql_trade_data_database_name = 'trade_database_test_harness'
read_cached_from_disk = False # generally want to download from the data vendor to test

# can test web proxies (can run a pure Python proxy server https://pypi.org/project/pproxy/)
# or alternatively use web proxy provided by your internal IT team (more realistic environment, also to help test
# firewall issues)
web_proxies = {'https' : None}

# web_proxies = {
#     'http' : "http://127.0.0.1:8080",
#     'https' : "https://127.0.0.1:7000",
# }

chunk_int_min_dict = {'dukascopy' : None, 'ncfx' : 60} # number of minutes to download from data vendor (eg. 5 minutes)

########################################################################################################################
folder = Constants().test_data_harness_folder

#### change for your data vendor
data_vendor_name_list = ['ncfx', 'dukascopy']

database_populator_dict = {'dukascopy' : DatabasePopulatorDukascopy(), 'ncfx' : DatabasePopulatorNCFX()}
database_source_dict = {'dukascopy' : DatabaseSourceDukascopy(), 'ncfx' : DatabaseSourceNCFX()}

if constants.ncfx_url is None:
    data_vendor_name_list.remove('ncfx')

####

trade_order_list = ['trade_df', 'order_df']

sql_trade_order_mapping = OrderedDict(
    [('trade_df', '[dbo].[trade]'),  # name of table which has broker messages to client
     ('order_df', '[dbo].[order]')])  # name of table which has orders from client

eps = 10 ** -5

invalid_start_date = '01 Jan 1999'
invalid_finish_date = '01 Feb 1999'

if use_hdf5_market_files:
    csv_market_data_store = os.path.join(folder, 'small_test_market_df.h5')
    csv_reverse_market_data_store = os.path.join(folder, 'small_test_market_df_reverse.h5')
else:
    csv_market_data_store = os.path.join(folder, 'small_test_market_df.csv.gz')
    csv_reverse_market_data_store = os.path.join(folder, 'small_test_market_df_reverse.csv.gz')

csv_trade_order_mapping = OrderedDict([('trade_df', os.path.join(folder, 'small_test_trade_df.csv')),
                                       ('order_df', os.path.join(folder, 'small_test_order_df.csv'))])

use_multithreading = False

def test_fetch_market_data_from_data_vendor():
    """Test the various downloaders (low level one, high level one - also with invalid dates, to test error messages)
    """

    # test for every data vendor
    for data_vendor_name in data_vendor_name_list:

        database_source = database_source_dict[data_vendor_name]
        database_populator = database_populator_dict[data_vendor_name]
        chunk_int_min = chunk_int_min_dict[data_vendor_name]

        # test the low level downloader (to download in one chunk) - DatabaseSource
        start_date = '04 Dec 2017 10:00'; finish_date = '04 Dec 2017 10:05'

        df_low_level = database_source.fetch_market_data(start_date, finish_date, 'EURUSD', web_proxies=web_proxies)

        start_date = pd.Timestamp(start_date).tz_localize('utc')
        finish_date = pd.Timestamp(finish_date).tz_localize('utc')

        assert not(df_low_level.empty) and df_low_level.index[0] >= start_date \
                       and df_low_level.index[-1] <= finish_date

        # test the high level downloader, which can download multiple chunks (don't write anything to disk) - DatabasePopulator
        start_date = '04 Dec 2017 10:00'; finish_date = '04 Dec 2017 10:20'

        msg, df_high_level_dict = database_populator.download_from_external_source(
            remove_duplicates=True,
            number_of_days=30 * 7, chunk_int_min=chunk_int_min,
            start_date=start_date, finish_date=finish_date, delete_cached_files=False, tickers='EURUSD',
            write_to_disk_db=False, read_cached_from_disk=read_cached_from_disk, return_df=True, web_proxies=web_proxies)

        start_date = pd.Timestamp(start_date).tz_localize('utc')
        finish_date = pd.Timestamp(finish_date).tz_localize('utc')

        df_high_level = df_high_level_dict[ticker]

        # check to make sure the start/finish dates are within bounds and also no error messages returned
        assert not(df_high_level.empty) and df_high_level.index[0] >= start_date \
                        and df_high_level.index[-1] <= finish_date and msg == []

        # now try dates with no data in the weekend, which should return back a None and also an error message, which
        # can be collected and returned to the user
        start_date = '03 Dec 2017 10:00';
        finish_date = '03 Dec 2017 10:20'

        msg, df_invalid = database_populator.download_from_external_source(remove_duplicates=True,
                                                                           number_of_days=30 * 7,
                                                                           chunk_int_min=chunk_int_min,
                                                                           start_date=start_date,
                                                                           finish_date=finish_date,
                                                                           delete_cached_files=False, tickers='EURUSD',
                                                                           write_to_disk_db=False,
                                                                           read_cached_from_disk=read_cached_from_disk,
                                                                           web_proxies=web_proxies)

        # check to make sure the start/finish dates are within bounds and also no error messages returned
        assert df_invalid == {} and "No downloaded data" in msg[0]

def test_write_csv_from_data_vendor():
    """Tests downloading market data from the data vendor and dumping to CSV. Checks written CSV against what is loaded
    in memory. Also checks data is available in each 'usual' market hour.

    Note, that we use cached data from disk, as we want to download relatively large sections of data, and doing
    this externally can cause the test to run very slowly.
    """

    for data_vendor_name in data_vendor_name_list:

        # database_source = database_source_dict[data_vendor_name]
        database_populator = database_populator_dict[data_vendor_name]
        chunk_int_min = chunk_int_min_dict[data_vendor_name]

        # specifically choose dates which straddle the weekend boundary
        start_date = '27 Apr 2018'; finish_date = '03 May 2018'; expected_csv_files = 5    # during British Summer Time in London
        # start_date = '02 Feb 2018'; finish_date = '07 Feb 2018'; expected_csv_files = 4    # during GMT time in London
        split_size = 'daily'
        write_csv = False

        # prepare the CSV folder first
        csv_folder = os.path.join(constants.test_data_harness_folder, 'csv_' + data_vendor_name + '_dump')

        # empty the CSV test harness folder
        UtilFunc().forcibly_create_empty_folder(csv_folder)

        msg, df_dict = database_populator.download_to_csv(
            start_date, finish_date, ['EURUSD'], chunk_int_min=chunk_int_min, split_size=split_size, csv_folder=csv_folder,
            return_df=True, write_large_csv=write_csv, remove_duplicates=False, web_proxies=web_proxies)

        df_read_direct_from_data_vendor = df_dict['EURUSD']

        # check it has data for every market hour (eg. ignoring Saturdays)
        assert util_func.check_data_frame_points_in_every_hour(df_read_direct_from_data_vendor, start_date, finish_date)

        if write_csv:
            # read back the CSVs dumped on disk in the test harness CSV folder
            csv_file_list = glob.glob(csv_folder + '/EURUSD*.csv')

            assert len(csv_file_list) == expected_csv_files

            df_list = []

            for c in csv_file_list:
                df = pd.read_csv(c, index_col=0)
                df.index = pd.to_datetime(df.index)
                df_list.append(df)

            # now compare the CSVs on disk versus those read directly
            df_read_from_csv = pd.concat(df_list).tz_localize(pytz.utc)

            assert_frame_equal(df_read_from_csv, df_read_direct_from_data_vendor)

def test_daily_download_boundary_from_data_vendor():
    """Tests that data over a daily boundary still downloads correctly from the data vendor
    """

    for data_vendor_name in data_vendor_name_list:

        database_populator = database_populator_dict[data_vendor_name]
        chunk_int_min = chunk_int_min_dict[data_vendor_name]

        start_date = '29 Apr 2018 21:00'; # Saturday
        finish_date = '30 Apr 2018 01:00'; # Monday

        msg, df = database_populator.download_from_external_source(remove_duplicates=False,
                                                                chunk_int_min=chunk_int_min,
                                                                start_date=start_date,
                                                                finish_date=finish_date,
                                                                delete_cached_files=False, tickers='EURUSD',
                                                                write_to_disk_db=False,
                                                                read_cached_from_disk=read_cached_from_disk,
                                                                return_df=True, web_proxies=web_proxies)

        assert util_func.check_data_frame_points_in_every_hour(df['EURUSD'], start_date, finish_date)

def test_weekend_download_boundary_from_data_vendor():
    """Tests that data over a weekend boundary still works from the data vendor (note: shouldn't have any data on Saturday)
    """

    for data_vendor_name in data_vendor_name_list:

        database_populator = database_populator_dict[data_vendor_name]
        chunk_int_min = chunk_int_min_dict[data_vendor_name]

        # start_date = '12 Jan 2018 19:00';
        # finish_date = '15 Jan 2018 05:00';

        start_date = '12 Jan 2018 21:00';
        finish_date = '15 Jan 2018 01:00';

        msg, df = database_populator.download_from_external_source(remove_duplicates=False,
                                                                    chunk_int_min=chunk_int_min,
                                                                    start_date=start_date,
                                                                    finish_date=finish_date,
                                                                    delete_cached_files=False, tickers='EURUSD',
                                                                    write_to_disk_db=False,
                                                                    read_cached_from_disk=read_cached_from_disk,
                                                                    return_df=True, web_proxies=web_proxies)

        # note: this will exclude data when FX market is not trading, eg. Saturday
        assert util_func.check_data_frame_points_in_every_hour(df['EURUSD'], start_date, finish_date)

if __name__ == '__main__':

    # test_write_csv_from_data_vendor()
    # test_fetch_market_data_from_data_vendor()

    test_daily_download_boundary_from_data_vendor()
    test_weekend_download_boundary_from_data_vendor()

    # import pytest; pytest.main()
