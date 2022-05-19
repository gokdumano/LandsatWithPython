from utils import ParseL8Tar, ProcessL8Band
from osgeo import gdal
import numpy as np

paths = ['LANDSAT8/LC08_L1TP_180031_20130730_20200912_02_T1.tar',
         'LANDSAT8/LC08_L1TP_180032_20130730_20200912_02_T1.tar']

for path in paths:
    bands = ParseL8Tar(path)
    
    maskPixel  = np.bitwise_and(bands['QAPIXEL']['data'], 31)
    maskRadsat = ~np.equal(bands['QARADSAT']['data'], 0)
    mask       = np.logical_or(maskPixel, maskRadsat)
    
    driver = gdal.GetDriverByName('GTiff')
    opath  = path.replace('.tar', '.TIF')
    
    nrow, ncol   = bands['QAPIXEL']['data'].shape
    projection   = bands['QAPIXEL']['projection']
    geoTransform = bands['QAPIXEL']['geoTransform']
    nbands       = len(bands) - 3
    dtype        = gdal.GDT_Float64
    
    dst = driver.Create(opath, ncol, nrow, nbands, dtype)
    dst.SetProjection(projection)
    dst.SetGeoTransform(geoTransform);
    
    filtered = [(name, band) for (name, band) in bands.items() if name not in ('Panchromatic', 'QAPIXEL', 'QARADSAT')]
    for idx, (name, band) in enumerate(filtered, start=1):
        data       = ProcessL8Band(band)
        data[mask] = band['nodata']
        
        sds = dst.GetRasterBand(idx)
        sds.WriteArray(data)
        sds.SetDescription(name)
        sds.SetNoDataValue(band['nodata'])
        sds.FlushCache()
    dst = None
