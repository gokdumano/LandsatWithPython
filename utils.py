from osgeo import gdal
import numpy as np
import tarfile
import re, os

from enum import IntEnum
L8Bands = IntEnum('Landsat Bands', 'CoastalAerosol Blue Green Red NIR SWIR1 SWIR2 Panchromatic Cirrus TIRS1 TIRS2 QAPIXEL QARADSAT')

def atoi(text):
    return int(text) if text.isdigit() else text

def human_sorting(name):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [ atoi(c) for c in re.split(r'(\d+)', name) ]
    
def read2dict(tifpath):
    src = gdal.Open(tifpath, gdal.GA_ReadOnly)
    
    band   = src.GetRasterBand(1)
    data   = band.ReadAsArray()
    nodata = band.GetNoDataValue()
    
    geoTransform = src.GetGeoTransform()
    projection   = src.GetProjection()
    
    return {'data':data, 'nodata':nodata, 'geoTransform':geoTransform, 'projection':projection}

from pprint import pprint

def ParseMTL(mtltext):
    mtldict  = {}
    
    for L8Band in L8Bands:
        bandidx  = L8Band.value
        bandname = L8Band.name
        data     = {}
        
        if bandidx in range(1, 10):
            data['Type'] = 'PANCHROMATIC' if bandname == 'Panchromatic' else 'REFLECTIVE'
            pattern      = '|'.join({f'REFLECTANCE_(?:MULT|ADD)_BAND_{bandidx} =.*', f'SUN_ELEVATION =.*'})
            matches      = re.findall(pattern, mtltext)
            for match in matches:
                key, value = match.split(' = ')
                if   'SUN_ELEVATION'    in key: data['SE'  ] = np.radians(float(value))
                elif 'REFLECTANCE_MULT' in key: data['Mref'] = float(value)
                elif 'REFLECTANCE_ADD'  in key: data['Aref'] = float(value)
            
        elif bandidx in range(10, 12):
            data['Type'] = 'THERMAL'
            pattern      = '|'.join({f'RADIANCE_(?:MULT|ADD)_BAND_{bandidx} =.*', f'K(?:1|2)_CONSTANT_BAND_{bandidx} =.*'})
            matches      = re.findall(pattern, mtltext)
            for match in matches:
                key, value = match.split(' = ')
                if   'K1_CONSTANT_BAND' in key: data['K1'  ] = float(value)
                elif 'K2_CONSTANT_BAND' in key: data['K2'  ] = float(value)
                elif 'RADIANCE_MULT'    in key: data['Mrad'] = float(value)
                elif 'RADIANCE_ADD'     in key: data['Arad'] = float(value)
        else:
            data['Type'] = 'MASK'
                
        mtldict[bandname] = data
            
    return mtldict

def ParseL8Tar(tarpath):
    dirname  = tarpath.rstrip('.tar')
    filename = os.path.basename(dirname)
    mtlname  = filename + '_MTL.txt'
    
    pattern  = r'\w*_(?:B\d{1,2}|QA\w*).TIF'
    bands    = {}
    
    with tarfile.open(tarpath, 'r') as file:
        mtlmember = file.getmember(mtlname)
        with file.extractfile(mtlmember) as mtlfile:
            mtltext = mtlfile.read().decode()
            mtldata = ParseMTL(mtltext)
            
        tifnames = [tifname for tifname in file.getnames() if re.match(pattern, tifname)]
        tifnames.sort(key=human_sorting)
        for idx, tifname in enumerate(tifnames, start=1):
            bandname = L8Bands(idx).name
            banddict = read2dict(f'/vsitar/{tarpath}/{tifname}')
            bands[bandname] = {**banddict, **mtldata[bandname]}
            print('.', end='')
    print()
    return bands

def ProcessL8Band(banddata):
    assert banddata['Type'] in ('REFLECTIVE', 'PANCHROMATIC', 'THERMAL')
    mask = banddata['data'] == banddata['nodata']
    
    if banddata['Type'] in ('REFLECTIVE', 'PANCHROMATIC'):
        TOA = banddata['Mref'] * banddata['data'] + banddata['Aref']
        TOA = TOA / np.sin(banddata['SE'])
    else:
        TOA = banddata['Mrad'] * banddata['data'] + banddata['Arad']
        TOA = banddata['K2'] / np.log(1 + banddata['K1'] / TOA)
        
    TOA[mask] = banddata['nodata']
    return TOA