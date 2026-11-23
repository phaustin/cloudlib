"""
  module to read the wyoming upperair site and parse it into
  dataframes  -- see newsoundings.ipynb for an example
"""
import requests
from bs4 import BeautifulSoup
import re
import datetime
from  datetime import timezone as tz
import pandas as pd
from collections import OrderedDict
from ..thermo.thermfn import find_esat
from ..thermo.constants import constants as con
import numpy as np
import sys
from pathlib import Path
import shutil
import json
import pdb
import time
import pytz

# We need to parse a set of lines that look like this:

#                              Station number: 82965
#                            Observation time: 110201/0000
#                            Station latitude: -9.86
#                           Station longitude: -56.10
#                           Station elevation: 288.0
#                             Showalter index: -0.37
#                                Lifted index: -0.68

# Here's a regular expresion that does that:


re_text=r"""
           .*Station\snumber\:\s(.+?)\n
           \s+Observation\stime\:\s(.+?)\n
           \s+Station\slatitude\:\s(.+?)\n
           \s+Station\slongitude\:\s(.+?)\n
           \s+Station\selevation\:\s(.+?)\n
           .*
        """

#
# DOTALL says: make . include \n
# VERBOSE says: ignore whitespace and comments within the regular expression
#         to help make the expression more readable
#
header_re=re.compile(re_text,re.DOTALL|re.VERBOSE)

def parse_header(header_text):
    """
    Read a header returned by make_frames and
    return station information

    Parameters
    ----------

    header_text : str
                  string containing wyoming header read with make_frames

    Returns
    -------

    theDate : datetime
              date of sounding
                                  
    the_id  : int
              5 digit souding id

    lat     : float
              latitude (degrees North)

    lon     : float
              longitude (degrees east)
    
    elev    : float
              station elevation (meters)
    """
    header_text=header_text.strip()
    the_match = header_re.match(header_text)
    try:
        the_id,string_time,lat,lon,elev=the_match.groups()
    except AttributeError:
        print('parse failure with: \n',header_text)
    the_id,string_time,lat,lon,elev=the_match.groups()
    elev=elev.split('\n')[0]  #some soundings follow elev with Shoalwater, not Lifted
    lat=float(lat)
    lon=float(lon)
    elev=float(elev)
    day,hour = string_time.strip().split('/')
    print('here is the day: ',day)
    year=int(day[:2]) + 2000
    month=int(day[2:4])
    day=int(day[4:6])
    minute=int(hour[2:])
    hour=int(hour[:2])
    theDate=datetime.datetime(year,month,day,hour,minute,0,0,tz.utc)
    return theDate,the_id,lat,lon,elev

def parse_data(data_text):
    """
    Read a single sounding into a dataframe

    Parameters
    ----------

    data_text : str
                sounding text

    Returns
    -------

    df_out : dataframe
             11 column data frame with sounding values

    unit_name : list
                list of strings with name of units of each column
    """
    """

    Comments
    --------

    here is an example of the data_text::

        -----------------------------------------------------------------------------
           PRES   HGHT   TEMP   DWPT   RELH   MIXR   DRCT   SKNT   THTA   THTE   THTV
            hPa     m      C      C      %    g/kg    deg   knot     K      K      K 
        -----------------------------------------------------------------------------
         1000.0    100                                                               
          979.0    288   24.0   23.0     94  18.45      0      0  299.0  353.0  302.2
          974.0    333   25.2   21.1     78  16.46    348      0  300.6  349.1  303.6
          932.0    719   24.0   16.0     61  12.42    243      3  303.2  340.3  305.4
          925.0    785   23.4   15.4     61  12.03    225      3  303.2  339.2  305.4
    """
    all_lines=data_text.strip().split('\n')
    count=0
    theLine=all_lines[count]
    try:
        while theLine.find('PRES   HGHT   TEMP   DWPT') < 0:
            count += 1
            theLine = all_lines[count]
        header_names=all_lines[count].lower().split()
    except IndexError:
        raise RuntimeError("no column header line found in sounding")
    count += 1  #go to unit names
    unit_names=all_lines[count].split()
    count+=2  #skip a row of ------
    data_list=[]
    while True:
        try:
            the_line=all_lines[count]
            dataFields = the_line.split()
            if len(dataFields) == 11:
                try:
                    dataFields = [float(number) for number in dataFields]
                    es = find_esat(dataFields[3] + 273.15)*0.01  #get vapor pressure from dewpoint in hPa
                    dataFields[5] = (con.eps*es/(dataFields[0] - es))*1.e3   #g/kg
                except ValueError:
                    raise RuntimeError(f'trouble converting dataFields to float: {dataFields}')
                data_list.append(dataFields)
                #
                # get the next line
                #
            count += 1
            theLine = all_lines[count]
        except IndexError:
            break
    df_out=pd.DataFrame.from_records(data_list,columns=header_names)
    return df_out,unit_names

def make_frames(html_doc):
    """
    turn an html page retrieved from the wyoming site into a dataframe

    Parameters
    ----------

    html_doc : string
               web page from wyoming upperair sounding site
               http://weather.uwyo.edu/cgi-bin/sounding retrieved by
               the requests module

    Returns
    -------

    attr_dict : dict
               attr_dict dictionary with ['header', 'site_id','longitude','latitude', 'elevation', 'units']
              
    sound_dict : dict  
                 sounding dictionary with sounding times as keys and sounding as dataframes
    """  
    soup=BeautifulSoup(html_doc,'html.parser')
    keep=list()
    header= (soup.find_all('h2'))[0].text
    print('header is: ',header)
    for item in soup.find_all('pre'):
        keep.append(item.text)

    sounding_dict=OrderedDict()
    evens=np.arange(0,len(keep),2)
    for count in evens:
        df,units=parse_data(keep[count])
        theDate,the_id,lat,lon,elev=parse_header(keep[count+1])    
        sounding_dict[theDate]=df
        
    attr_dict=dict(units=';'.join(units),site_id=the_id,
                   latitude=lat,longitude=lon,elevation=elev,
                   header = header)
    
    return attr_dict,sounding_dict
    
#
# the Wyoming site retired http://weather.uwyo.edu/cgi-bin/sounding in 2025;
# the replacement returns one sounding per request (404 if none at that time)
#
WYOMING_URL = ("https://weather.uwyo.edu/wsgi/sounding?"
               "datetime={time}&id={station}&type=TEXT:LIST")

REQUEST_PAUSE = 1.0     # seconds between requests -- the site rate limits
RETRY_WAITS = (5, 10, 20, 40, 60, 120)   # backoff after a 503 "Too Busy"

def get_with_retry(url):
    """
    GET url, pausing between requests and backing off when the
    Wyoming server answers 503 Too Busy or drops the connection.
    The server closes the connection after each reply, so no Session is used.
    """
    time.sleep(REQUEST_PAUSE)
    for wait in RETRY_WAITS + (None,):
        try:
            response = requests.get(url, timeout=120)
            if response.status_code != 503:
                return response
            problem = "server busy (503)"
        except (requests.ConnectionError, requests.Timeout) as err:
            if wait is None:
                raise
            problem = f"connection problem ({type(err).__name__})"
        if wait is None:
            return response
        print(f"wyoming {problem}, retrying in {wait} s")
        time.sleep(wait)

def sounding_times(input_dict):
    """
    Turn the year/month/start/stop fields of input_dict into a list of
    utc datetimes to request.  start and stop are 'DDHH' strings
    (inclusive); hours defaults to the synoptic times (0, 12) and can
    be overridden with an optional 'hours' entry, e.g. hours=(0,6,12,18)
    """
    year=int(input_dict['year'])
    month=int(input_dict['month'])
    def to_time(ddhh):
        return datetime.datetime(year,month,int(ddhh[:2]),int(ddhh[2:4]),tzinfo=tz.utc)
    start=to_time(input_dict['start'])
    stop=to_time(input_dict['stop'])
    hours=set(int(h) for h in input_dict.get('hours',(0,12)))
    times=[]
    the_time=start.replace(hour=0)
    while the_time <= stop:
        if the_time >= start and the_time.hour in hours:
            times.append(the_time)
        the_time += datetime.timedelta(hours=1)
    return times

def make_frame(html_doc, the_time):
    """
    turn a single-sounding page from the wyoming wsgi site into a dataframe

    Parameters
    ----------

    html_doc : str
        page returned by WYOMING_URL

    the_time : datetime
        sounding time (used for the header)

    Returns
    -------

    attr_dict : dict
        dictionary with ['header', 'site_id','longitude','latitude', 'elevation', 'units']

    df : DataFrame
        sounding with the same columns as the old cgi-bin pages
        (wind speed sped in m/s is converted to sknt in knots)
    """
    soup=BeautifulSoup(html_doc,'html.parser')
    pre=soup.find('pre')
    if pre is None:
        raise RuntimeError(f"no sounding table found for {the_time}")
    df,units=parse_data(pre.text)
    if 'sped' in df.columns:
        idx=list(df.columns).index('sped')
        df['sped']=np.round(df['sped']*3600./1852.)   # m/s -> knots
        df=df.rename(columns={'sped':'sknt'})
        units[idx]='knot'
    indices={}
    for row in soup.find_all('tr'):
        cells=[td.text.strip() for td in row.find_all('td')]
        if len(cells) >= 3:
            indices[cells[0]]=cells[2]
    h1=soup.find('h1').text
    site_id=re.search(r'Station\s+(\S+)',h1).group(1)
    h3=soup.find('h3')
    name=' '.join(h3.text.split()) if h3 else ''
    header=f"{site_id} {name} Observations at {the_time:%HZ %d %b %Y}"
    attr_dict=dict(units=';'.join(units),site_id=site_id,
                   latitude=float(indices['SLAT']),longitude=float(indices['SLON']),
                   elevation=float(indices['SELV']),header=header)
    return attr_dict,df

def write_soundings(input_dict,outputdir):
    """
    function to download soundings from the Wyoming upper air site
    (https://weather.uwyo.edu/wsgi/sounding) and write them, plus
    a metadata.json file, to a folder

    Parameters
    ----------

    input_dict: dict
       dictionary with fields needed to specify the sounding
       i.e.
       dict(region='naconf',year='2017',month='7',start='0100',stop='1800',station='72451')
       start and stop are DDHH (inclusive).  region is no longer needed by the
       site but is kept for compatibility.  An optional hours=(0,6,12,18) entry
       changes which hours are requested (default 0 and 12 UTC)

    outputdir: string
       path to directory that will hold the csv sounding files
       will be overwritten if it exists

    Returns
    -------
     
    None: soundings and metadata.json file will be written as a side effect
    """

    print(f"{input_dict=}")
    sounding_dict=OrderedDict()
    attr_dict=None
    for the_time in sounding_times(input_dict):
        url=WYOMING_URL.format(time=the_time.strftime("%Y-%m-%d %H:%M:%S"),
                               station=input_dict['station'])
        response = get_with_retry(url)
        if response.status_code == 404:
            continue   # no sounding at this time
        response.raise_for_status()
        attrs, df = make_frame(response.text, the_time)
        sounding_dict[the_time]=df
        if attr_dict is None:
            attr_dict = attrs
    if attr_dict is None:
        raise RuntimeError(f"no soundings found at {WYOMING_URL} for {input_dict}")
    print(f"downloaded {len(sounding_dict)} soundings")
    attr_dict['history']="written by cloudlib.soundings.wyominglib.write_soundings"
    key_list=['header', 'site_id','longitude','latitude', 'elevation', 'units','history']
    #pdb.set_trace()
    folder = Path(outputdir)
    if folder.exists():
        shutil.rmtree(folder)

    folder.mkdir()
    
    filelist=[]
    for key,value in sounding_dict.items():
        thetime=key.strftime("Y%Y_%b_%d_%HZ")
        filename = f'{thetime}.csv'
        filepath= str(folder / Path(filename))
        time_tuple=key.utctimetuple()
        filelist.append((filename,time_tuple))
        value.to_csv(filepath)

    metafile = folder / Path('metadata.json')
    metadict=dict(filelist=filelist,attributes=attr_dict,input_args=input_dict)
    with open(metafile,'w') as outmeta:
        json.dump(metadict,outmeta,indent=4)
        
    print(f'files written to {str(folder)}')
    return None

def read_soundings(soundingdir):
    """
    read the soundings created by write_soundings

    Parameters
    ----------

    soundingdir: string
       path to directory containing sounding csv files and metadata.json

    Returns
    -------

    meta_dict: dict
       dictionary with keys dict_keys(['filelist', 'attributes', 'input_args', 'file_dict', 'sounding_dict'])
    """
    input_dir=Path(soundingdir)
    json_file = input_dir / Path('metadata.json')
    with open(json_file,'r') as infile:
        meta_dict = json.load(infile)
    file_dict={}
    #
    # turn the time.struct_time time tuples into a plain tuple
    # with (year, month, day, hour) and use that for
    # the flie_dict key
    #
    for filename,timetup in meta_dict['filelist']:
        tutc=datetime.datetime(*timetup[:6],tzinfo=pytz.utc)
        key=(tutc.year,tutc.month,tutc.day,tutc.hour)
        file_dict[key]=filename

    sounding_dict={}
    for the_time,filename in file_dict.items():
        full_path=input_dir / Path(filename)
        sounding_dict[the_time]=pd.read_csv(str(full_path))
    
    meta_dict['file_dict']=file_dict
    meta_dict['sounding_dict']=sounding_dict
    #pdb.set_trace()
    
    return meta_dict

def test_lib():
    values=dict(region='samer',year='2013',month='2',start='0100',stop='2800',station='82965')
    write_soundings(values, 'soundingdir')
    soundingdir = 'soundingdir'
    out=read_soundings(soundingdir)
    





    

if __name__ == "__main__":
    #
    # some sample input dictionaries
    #
    values=dict(region='samer',year='2013',month='2',start='0100',stop='2800',station='82965')
    #values=dict(region='nz',year='2013',month='2',start='0100',stop='2800',station='93417')
    #values=dict(region='naconf',year='2013',month='2',start='0100',stop='2800',station='71802')
    #values=dict(region='ant',year='2013',month='07',start='0100',stop='2800',station='89009')
    values=dict(region='naconf',year='2017',month='7',start='0100',stop='1800',station='72451')
    
    #naconf, samer, pac, nz, ant, np, europe,africa, seasia, mideast

    write_soundings(values, 'soundingdir')
    soundingdir = 'soundingdir'
    out=read_soundings(soundingdir)
    print(list(out.keys()))
    
    
