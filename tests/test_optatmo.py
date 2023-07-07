# Copyright (c) 2016 by Mike Jarvis and the other collaborators on GitHub at
# https://github.com/rmjarvis/Piff  All rights reserved.
#
# Piff is free software: Redistribution and use in source and binary forms
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.

from __future__ import print_function
import numpy as np
import piff
import os
import fitsio
import galsim

from piff_test_helper import timer


@timer
def test_init():
    # make a psf
    config = get_config()
    logger = piff.setup_logger(verbose=1)
    psf = piff.PSF.process(config['psf'],logger=None)

#####
# convenience functions
#####


def make_empty_star(icen=500, jcen=700, ccdnum=28, params=None,
                    properties={},
                    fit_kwargs={}):

    properties['ccdnum'] = ccdnum
    # setting scale is crucial
    star = piff.Star.makeTarget(x=icen, y=jcen, properties=properties,
                                scale=0.263)

    if params is None:
        starfit = None
    else:
        starfit = piff.StarFit(params, **fit_kwargs)

    star = piff.Star(star.data, starfit)

    return star

def get_config():
    config = {'psf': {
                    'type': 'OptAtmo',
                    'model': {
                         'type': 'Optical',
                         'lam': 782.1,
                         'template': 'des_128',
                         'gsparams': 'fast',
                         'atmo_type': 'VonKarman'},
                    'do_ofit': True,
                    'do_sfit': True,
                    'do_afit': False,
                    'wavefront_kwargs':  {
                         'survey': 'des',
                         'source1': {
                            'file': 'input/GPInterp-20140212s2-v22i2.npz',
                            'zlist': [4,5,6,7,8,9,10,11,14,15],
                            'keys': {"x_fp":"xfp","y_fp":"yfp"},
                            'chip': {"chipnum":range(1,62+1)} },
                         'source2': {
                            'file':  'input/decam_2012-iband-700nm.npz',
                            'zlist': [12,13,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37],
                            'keys': {"x_fp":"xfp","y_fp":"yfp"},
                            'chip': 'None'}, },
                    'ofit_double_zernike_terms':  [[4, 1], [5, 3], [6, 3], [7, 1], [8, 1], [9, 1], [10, 1], [11, 1]],  
                    'ofit_type': 'shape',  # shape or pixel or shapegrad
                    'ofit_nstars': 500,
                    'ofit_optimizer': 'iminuit', # 'least_squares' or 'iminuit'
                    'ofit_strategy': 1,    # 0,1,2 for iminuit
                    'ofit_tol': 1000,       # tolerance multiplier for iminuit
                    'ofit_initvalues': {"opt_L0":10.,"opt_size":1.0},
                    'ofit_bounds': {"opt_L0":[1.0,100.0],"opt_g1":[-0.7,0.7],"opt_g2":[-0.7,0.7]},
                    'ofit_shape_kwargs': {
                        'moment_list': ["M11","M20","M02","M21","M12","M30","M03","M22n"],
                        'weights': [0.707,1.0,1.0,1.0,1.0,1.0,1.0,1.0],  #  change weight for e0 to sqrt(2)
                        'systerrors': [0.006, 0.0032, 0.0032, 0.0004, 0.0004, 0.0006, 0.0006, 0.0095] }, # see OptAtmo-test-newcode-part11.ipynb
                    'sfit_optimizer': 'least_squares',
                    'sfit_pixel_kwargs': {'pixel_radius':2.0},  # number of HWHM radii to include in pixel-based Chi2
                    'fov_radius': 4500.0,
                    'interp': {
                       'type': 'GPInterp',
                       #anisotropic: true
                       'optimizer': 'anisotropic',
                       'kernel': '1e-2 * AnisotropicVonKarman(invLam=np.array([[1./3000.**2,0],[0,1./3000.**2]]))',
                       'max_sep': 1020.0,
                       'min_sep': 0.0,
                       'nbins': 21,
                       #optimize: true
                       #optimizer: two-pcf
                       'l0': 3000.0 }
                     }
                  }
    return config

if __name__ == '__main__':
    test_init()
