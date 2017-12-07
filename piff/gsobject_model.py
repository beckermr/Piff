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

"""
.. module:: gsobject_model
"""

import numpy as np
import galsim

from .model import Model, ModelFitError
from .star import Star, StarFit, StarData
from .util import hsm

class GSObjectModel(Model):
    """ Model that takes a fiducial GalSim.GSObject and dilates, shifts, and shears it to get a
    good match to stars.

    :param gsobj:    GSObject to use as fiducial profile.
    :param fastfit:  Use HSM moments for fitting.  Approximate, but fast.  [default: False]
    :param force_model_center: If True, PSF model centroid is fixed at origin and
                        PSF fitting will marginalize over stellar position.  If False, stellar
                        position is fixed at input value and the fitted PSF may be off-center.
                        [default: True]
    :param include_pixel:   Include integration over pixel?  [default: True]
    :param unnormalized_basis:  Do parameter fit for size and ellipticity in unnormalized second moment space? [default: False]
    :param logger:   A logger object for logging debug info. [default: None]
    """
    def __init__(self, gsobj, fastfit=False, force_model_center=True, include_pixel=True, unnormalized_basis=False,
                 logger=None):
        if isinstance(gsobj, str):
            import galsim
            gsobj = eval(gsobj)

        self.kwargs = {'gsobj':repr(gsobj),
                       'fastfit':fastfit,
                       'force_model_center':force_model_center,
                       'include_pixel':include_pixel,
                       'unnormalized_basis':unnormalized_basis}

        # Center and normalize the fiducial model.
        self.gsobj = gsobj.withFlux(1.0).shift(-gsobj.centroid)
        self._fastfit = fastfit
        self._force_model_center = force_model_center
        self._unnormalized_basis = unnormalized_basis
        self._method = 'auto' if include_pixel else 'no_pixel'
        # Params are [du, dv], scale, g1, g2, i.e., transformation parameters that bring the
        # fiducial gsobject towards the data.
        if self._force_model_center:
            self._nparams = 3
        else:
            self._nparams = 5

    @staticmethod
    def convert_to_unnormalized_basis(scale, g1, g2):
        shear = galsim.Shear(g1=g1, g2=g2)
        e1norm = shear.e1
        e2norm = shear.e2
        # absgsq = g1**2 + g2**2
        # g2e = 2. / (1.+absgsq)
        # e1norm = g1 * g2e
        # e2norm = g2 * g2e
        e0 = np.sqrt(4 * scale ** 4 / (1 - e1norm ** 2 - e2norm ** 2))
        e1 = e1norm * e0
        e2 = e2norm * e0
        return e0, e1, e2

    @staticmethod
    def convert_from_unnormalized_basis(e0, e1, e2):
        e1norm = e1 / e0
        e2norm = e2 / e0
        shear = galsim.Shear(e1=e1norm, e2=e2norm)
        g1 = shear.g1
        g2 = shear.g2
        # absesq = e1 ** 2 + e2 ** 2
        # e2g = 1. / (1. + np.sqrt(1. - absesq))
        # g1 = e1norm * e2g
        # g2 = e2norm * e2g
        scale = np.sqrt(np.sqrt((e0 ** 2 - e1 ** 2 - e2 ** 2)) * 0.5)
        return scale, g1, g2

    def moment_fit(self, star, logger=None):
        """Estimate transformations needed to bring self.gsobj towards given star."""
        if logger: logger.debug('Entering moment fit')
        import galsim
        flux, cenu, cenv, size, g1, g2 = star.data.properties['hsm']
        shape = galsim.Shear(g1=g1, g2=g2)

        ref_flux, ref_cenu, ref_cenv, ref_size, ref_g1, ref_g2, flag = hsm(self.draw(star))
        ref_shape = galsim.Shear(g1=ref_g1, g2=ref_g2)
        if flag:
            raise ModelFitError("Error calculating model moments for this star.")

        param_flux = star.fit.flux
        if self._force_model_center:
            param_scale, param_g1, param_g2 = star.fit.params
            param_du, param_dv = star.fit.center
        else:
            param_du, param_dv, param_scale, param_g1, param_g2 = star.fit.params
        if self._unnormalized_basis:
            # need to convert fit params from unnormalized basis back to normalized
            if logger: logger.debug('Unnormalized initial starfit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(param_scale, param_g1, param_g2))
            param_scale, param_g1, param_2 = self.convert_from_unnormalized_basis(param_scale, param_g1, param_g2)
            if logger: logger.debug('Normalized initial starfit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(param_scale, param_g1, param_g2))

        param_shear = galsim.Shear(g1=param_g1, g2=param_g2)

        param_flux *= flux / ref_flux
        param_du += cenu - ref_cenu
        param_dv += cenv - ref_cenv
        param_scale *= size / ref_size
        param_shear += (shape - ref_shape)
        param_g1 = param_shear.g1
        param_g2 = param_shear.g2

        # report results in unnormalized basis if that is what we wanted
        # print(g1, ref_g1, param_g1)
        # print(g2, ref_g2, param_g2)
        if self._unnormalized_basis:
            # convert scale, g1, g2 to unnormalized basis
            if logger: logger.debug('Normalized final fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(param_scale, param_g1, param_g2))
            param_scale, param_g1, param_g2 = self.convert_to_unnormalized_basis(param_scale, param_g1, param_g2)
            if logger: logger.debug('Unnormalized final fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(param_scale, param_g1, param_g2))
        return param_flux, param_du, param_dv, param_scale, param_g1, param_g2

    def getProfile(self, params, logger=None):
        """Get a version of the model as a GalSim GSObject

        :param params:      A numpy array with either  [ size, g1, g2 ]
                            or  [ cenu, cenv, size, g1, g2 ]
                            depending on if the center of the model is being forced to (0.0, 0.0)
                            or not.

        :returns: a galsim.GSObject instance
        """
        if self._force_model_center:
            scale, g1, g2 = params
            du, dv = (0.0, 0.0)
        else:
            du, dv, scale, g1, g2 = params

        if self._unnormalized_basis:
            # params are actually e0, e1, e2, so convert from that to create galsim profile
            if logger: logger.debug('Unnormalized fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(scale, g1, g2))
            scale, g1, g2 = self.convert_from_unnormalized_basis(scale, g1, g2)
            if logger: logger.debug('Normalized fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(scale, g1, g2))

        return self.gsobj.dilate(scale).shear(g1=g1, g2=g2).shift(du, dv)

    def draw(self, star, logger=None):
        """Draw the model on the given image.

        :param star:    A Star instance with the fitted parameters to use for drawing and a
                        data field that acts as a template image for the drawn model.

        :returns: a new Star instance with the data field having an image of the drawn model.
        """
        prof = self.getProfile(star.fit.params, logger=logger).shift(star.fit.center) * star.fit.flux
        image = star.image.copy()
        prof.drawImage(image, method=self._method, offset=(star.image_pos-image.true_center))
        data = StarData(image, star.image_pos, star.weight, star.data.pointing)
        return Star(data, star.fit)

    def _lmfit_resid(self, lmparams, star, logger=None):
        """Residual function to use with lmfit.  Essentially `chi` from `chisq`, but not summed
        over pixels yet.

        :param lmparams:  An lmfit.Parameters() instance.  The model.
        :param star:    A Star instance.  The data.

        :returns: `chi` as a flattened numpy array.
        """
        import galsim
        image, weight, image_pos = star.data.getImage()
        if self._unnormalized_basis:
            # scale, g1, g2 actually unnormalized second moments
            flux, du, dv, e0, e1, e2 = lmparams.valuesdict().values()
            if logger: logger.debug('Unnormalized fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(e0, e1, e2))
            scale, g1, g2 = self.convert_from_unnormalized_basis(e0, e1, e2)
            if logger: logger.debug('Normalized fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(scale, g1, g2))
        else:
            flux, du, dv, scale, g1, g2 = lmparams.valuesdict().values()
        # Fit du and dv regardless of force_model_center.  The difference is whether the fit
        # value is recorded (force_model_center=False) or discarded (force_model_center=True).
        prof = self.gsobj.dilate(scale).shear(g1=g1, g2=g2).shift(du, dv) * flux
        model_image = galsim.Image(image, dtype=float)
        prof.drawImage(model_image, method=self._method,
                       offset=(image_pos - model_image.true_center))
        chi = (np.sqrt(weight.array)*(model_image.array - image.array)).ravel()
        # print(flux, du, dv, scale, g1, g2, model_image.array.max(), image.array.max(), np.square(chi).mean())
        return chi

    def _lmfit_params(self, star, vary_params=True, vary_flux=True, vary_center=True, logger=None):
        """Generate an lmfit.Parameters() instance from arguments.

        :param star:         A Star from which to initialize parameter values.
        :param vary_params:  Allow non-flux and non-center params to vary?
        :param vary_flux:    Allow flux to vary?
        :param vary_center:  Allow center to vary?

        :returns: lmfit.Parameters() instance.
        """
        import lmfit
        if logger: logger.debug("lmfit params.")

        # Get initial parameter values.  Either use values currently in star.fit, or if those are
        # absent, run HSM to get initial values.
        if star.fit.params is None:
            flux, du, dv, scale, g1, g2, flag = self.moment_fit(star, logger=logger)
            if flag != 0:
                raise RuntimeError("Error initializing star fit values using hsm.")
        else:
            # NOTE: assumes that the fit params are in the correct basis
            flux = star.fit.flux
            if self._force_model_center:
                du, dv = star.fit.center
                scale, g1, g2 = star.fit.params
            else:
                du, dv, scale, g1, g2 = star.fit.params

        params = lmfit.Parameters()
        # Order of params is important!
        params.add('flux', value=flux, vary=vary_flux, min=0.0)
        params.add('du', value=du, vary=vary_center)
        params.add('dv', value=dv, vary=vary_center)
        params.add(['scale', 'e0'][self._unnormalized_basis], value=scale, vary=vary_params, min=0.0)
        # Limits of +/- 0.7 is definitely a hack to avoid |g| > 1, but if the PSF is ever actually
        # this elliptical then we have more serious problems to worry about than hacky code!
        # when we have the unnormalized basis, our unnormalized ellipticites can also go up!
        maxg = [0.7, 5][self._unnormalized_basis]
        params.add(['g1', 'e1'][self._unnormalized_basis], value=g1, vary=vary_params, min=-maxg, max=maxg)
        params.add(['g2', 'e2'][self._unnormalized_basis], value=g2, vary=vary_params, min=-maxg, max=maxg)
        return params

    def _lmfit_minimize(self, params, star, logger=None):
        """ Run lmfit.minimize with given lmfit.Parameters() and on given star data.

        :param params: lmfit.Parameters() instance (holds initial guess and which params to let
                       float or hold fixed).
        :param star:   Star to fit.

        :returns: lmfit.MinimizerResult instance containing fit results.
        """
        import lmfit
        import time
        logger = galsim.config.LoggerWrapper(logger)
        t0 = time.time()
        logger.debug("lmfit minimize.")

        results = lmfit.minimize(self._lmfit_resid, params, args=(star,logger,))

        logger.debug("End lmfit minimize.  Elapsed time: {0}".format(time.time() - t0))
        return results

    def lmfit(self, star, logger=None):
        """Fit parameters of the given star using lmfit (Levenberg-Marquardt minimization
        algorithm).

        :param star:    A Star to fit.
        :param logger:  A logger object for logging debug info. [default: None]

        :returns: (flux, dx, dy, scale, g1, g2, flag)
        """
        if logger: logger.debug('Entering lmfit')
        import lmfit
        logger = galsim.config.LoggerWrapper(logger)
        params = self._lmfit_params(star,logger=logger,)
        results = self._lmfit_minimize(params, star, logger=logger)
        logger.debug(lmfit.fit_report(results))
        flux, du, dv, scale, g1, g2 = results.params.valuesdict().values()
        if not results.success:
            raise RuntimeError("Error fitting with lmfit.")

        return flux, du, dv, scale, g1, g2

    @staticmethod
    def with_hsm(star):
        if not hasattr(star.data.properties, 'hsm'):
            flux, cenu, cenv, size, g1, g2, flag = hsm(star)
            if flag != 0:
                raise RuntimeError("Error initializing star fit values using hsm.")
            sd = star.data.copy()
            sd.properties['hsm'] = flux, cenu, cenv, size, g1, g2
            return Star(sd, star.fit)
        return star

    def fit(self, star, fastfit=None, logger=None):
        """Fit the image either using HSM or lmfit.

        If `fastfit` is True, then the galsim.hsm module will be used to estimate the transformation
        parameters that take the fiducial moments into the data moments.  If `fastfit` is False,
        then the Levenberg-Marquardt minimization algorithm will be used instead.  The latter should
        generally be more accurate, but slower due to the need to iteratively propose model
        improvements.

        :param star:    A Star to fit.
        :param fastfit: Use fast HSM moments to fit? [default: None, which means use fitting mode
                        specified in the constructor.]
        :param logger:  A logger object for logging debug info. [default: None]

        :returns: a new Star with the fitted parameters in star.fit
        """
        if fastfit is None:
            fastfit = self._fastfit

        if not hasattr(star.data.properties, 'hsm'):
            star = self.initialize(star, logger=logger)

        if fastfit:
            flux, du, dv, scale, g1, g2 = self.moment_fit(star, logger=logger)
        else:
            flux, du, dv, scale, g1, g2 = self.lmfit(star, logger=logger)
        # Make a StarFit object with these parameters
        if self._force_model_center:
            params = np.array([ scale, g1, g2 ])
            center = (du, dv)
        else:
            params = np.array([ du, dv, scale, g1, g2 ])
            center = (0.0, 0.0)

        # Also need to compute chisq
        if logger: logger.debug('Get profile in fit for calculating chisq')
        prof = self.getProfile(params, logger=logger) * flux
        model_image = star.image.copy()
        prof.shift(center).drawImage(model_image, method=self._method,
                                     offset=(star.image_pos - model_image.true_center))
        chisq = np.sum(star.weight.array * (star.image.array - model_image.array)**2)
        dof = np.count_nonzero(star.weight.array) - self._nparams
        fit = StarFit(params, flux=flux, center=center, chisq=chisq, dof=dof)
        return Star(star.data, fit)

    def initialize(self, star, mask=True, logger=None):
        """Initialize the given star's fit parameters.

        :param star:  The Star to initialize.
        :param logger:  A logger object for logging debug info. [default: None]

        :returns: a new initialized Star.
        """
        if logger: logger.debug('In initialize')
        star = self.with_hsm(star)
        if star.fit.params is None:
            if self._force_model_center:
                params = np.array([ 1.0, 0.0, 0.0])
            else:
                params = np.array([ 0.0, 0.0, 1.0, 0.0, 0.0])
            fit = StarFit(params, flux=1.0, center=(0.0, 0.0))
            star = Star(star.data, fit)
            if logger: logger.debug('initialize, post hsm, moment fit')
            star = self.fit(star, fastfit=True, logger=logger)
            if logger: logger.debug('Moment fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(*star.fit.params))

        # TODO: I do not understand why this did not work
        # elif self._unnormalized_basis:
        #     if logger: logger.debug('Initialize: Dealing with unnormalized basis')
        #     # convert hsm parameters to unnormalized basis
        #     if self._force_model_center:
        #         if logger: logger.debug('Normalized initialize fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(*star.fit.params))
        #         star.fit.params = self.convert_to_unnormalized_basis(*star.fit.params)
        #         if logger: logger.debug('Unnormalized initialize fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(*star.fit.params))
        #     else:
        #         if logger: logger.debug('Normalized initialize fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(*star.fit.params[2:]))
        #         star.fit.params[2:] = self.convert_to_unnormalized_basis(*star.fit.params[2:])
        #         if logger: logger.debug('Unnormalized initialize fit params: {0:.2e}, {1:+.2e}, {2:+.2e}'.format(*star.fit.params[2:]))
        star = self.reflux(star, fit_center=False)
        return star

    def reflux(self, star, fit_center=True, logger=None):
        """Fit the Model to the star's data, varying only the flux (and
        center, if it is free).  Flux and center are updated in the Star's
        attributes.  This is a single-step solution if only solving for flux,
        otherwise an iterative operation.  DOF in the result assume
        only flux (& center) are free parameters.

        :param star:        A Star instance
        :param fit_center:  If False, disable any motion of center
        :param logger:      A logger object for logging debug info. [default: None]

        :returns:           New Star instance, with updated flux, center, chisq, dof, worst
        """
        logger = galsim.config.LoggerWrapper(logger)
        logger.debug("Reflux for star:")
        logger.debug("    flux = %s",star.fit.flux)
        logger.debug("    center = %s",star.fit.center)
        logger.debug("    props = %s",star.data.properties)
        logger.debug("    image = %s",star.data.image)
        #logger.debug("    image = %s",star.data.image.array)
        #logger.debug("    weight = %s",star.data.weight.array)
        logger.debug("    image center = %s",star.data.image(star.data.image.center))
        logger.debug("    weight center = %s",star.data.weight(star.data.weight.center))
        do_center = fit_center and self._force_model_center
        if do_center:
            params = self._lmfit_params(star, vary_params=False)
            results = self._lmfit_minimize(params, star, logger=logger)
            return Star(star.data, StarFit(star.fit.params,
                                           flux = results.params['flux'].value,
                                           center = (results.params['du'].value,
                                                     results.params['dv'].value),
                                           chisq = results.chisqr,
                                           dof = np.count_nonzero(star.data.weight.array) - 3,
                                           alpha = star.fit.alpha,
                                           beta = star.fit.beta))
        else:
            image, weight, image_pos = star.data.getImage()
            model_image = self.draw(star).image
            flux_ratio = (np.sum(weight.array * image.array * model_image.array)
                          / np.sum(weight.array * model_image.array**2))
            new_chisq = np.sum(weight.array * (image.array - flux_ratio*model_image.array)**2)
            return Star(star.data, StarFit(star.fit.params,
                                           flux = star.flux*flux_ratio,
                                           center = star.fit.center,
                                           chisq = new_chisq,
                                           dof = np.count_nonzero(weight.array) - 1,
                                           alpha = star.fit.alpha,
                                           beta = star.fit.beta))


class Gaussian(GSObjectModel):
    """ Model PSFs as elliptical Gaussians.

    :param fastfit:  Use HSM moments for fitting.  Approximate, but fast.  [default: False]
    :param force_model_center: If True, PSF model centroid is fixed at origin and
                        PSF fitting will marginalize over stellar position.  If False, stellar
                        position is fixed at input value and the fitted PSF may be off-center.
                        [default: True]
    :param include_pixel:   Include integration over pixel?  [default: True]
    :param unnormalized_basis:  Do parameter fit for size and ellipticity in unnormalized second moment space? [default: False]
    :param logger:   A logger object for logging debug info. [default: None]
    """
    def __init__(self, fastfit=False, force_model_center=True, include_pixel=True, unnormalized_basis=False, logger=None):
        import galsim
        gsobj = galsim.Gaussian(sigma=1.0)
        GSObjectModel.__init__(self, gsobj, fastfit, force_model_center, include_pixel, unnormalized_basis, logger)
        # We'd need self.kwargs['gsobj'] if we were reconstituting via the GSObjectModel
        # constructor, but since config['type'] for this will be Gaussian, it gets reconstituted
        # here, where there is no `gsobj` argument.  So remove `gsobj` from kwargs.
        del self.kwargs['gsobj']


class Kolmogorov(GSObjectModel):
    """ Model PSFs as elliptical Kolmogorovs.

    :param fastfit:  Use HSM moments for fitting.  Approximate, but fast.  [default: False]
    :param force_model_center: If True, PSF model centroid is fixed at origin and
                        PSF fitting will marginalize over stellar position.  If False, stellar
                        position is fixed at input value and the fitted PSF may be off-center.
                        [default: True]
    :param include_pixel:   Include integration over pixel?  [default: True]
    :param unnormalized_basis:  Do parameter fit for size and ellipticity in unnormalized second moment space? [default: False]
    :param logger:   A logger object for logging debug info. [default: None]
    """
    def __init__(self, fastfit=False, force_model_center=True, include_pixel=True, unnormalized_basis=False, logger=None):
        import galsim
        gsobj = galsim.Kolmogorov(half_light_radius=1.0)
        GSObjectModel.__init__(self, gsobj, fastfit, force_model_center, include_pixel, unnormalized_basis, logger)
        # We'd need self.kwargs['gsobj'] if we were reconstituting via the GSObjectModel
        # constructor, but since config['type'] for this will be Kolmogorov, it gets reconstituted
        # here, where there is no `gsobj` argument.  So remove `gsobj` from kwargs.
        del self.kwargs['gsobj']


class Moffat(GSObjectModel):
    """ Model PSFs as elliptical Moffats.

    :param beta:  Moffat shape parameter.
    :param trunc:  Optional truncation radius at which profile drops to zero.  Measured in half
                   light radii.  [default: 0, indicating no truncation]
    :param fastfit:  Use HSM moments for fitting.  Approximate, but fast.  [default: False]
    :param force_model_center: If True, PSF model centroid is fixed at origin and
                        PSF fitting will marginalize over stellar position.  If False, stellar
                        position is fixed at input value and the fitted PSF may be off-center.
                        [default: True]
    :param include_pixel:   Include integration over pixel?  [default: True]
    :param unnormalized_basis:  Do parameter fit for size and ellipticity in unnormalized second moment space? [default: False]
    :param logger:   A logger object for logging debug info. [default: None]
    """
    def __init__(self, beta, trunc=0., fastfit=False, force_model_center=True, include_pixel=True, unnormalized_basis=False,
                 logger=None):
        import galsim
        gsobj = galsim.Moffat(half_light_radius=1.0, beta=beta, trunc=trunc)
        GSObjectModel.__init__(self, gsobj, fastfit, force_model_center, include_pixel, unnormalized_basis, logger)
        # We'd need self.kwargs['gsobj'] if we were reconstituting via the GSObjectModel
        # constructor, but since config['type'] for this will be Moffat, it gets reconstituted
        # here, where there is no `gsobj` argument.  So remove `gsobj` from kwargs.
        del self.kwargs['gsobj']
        # Need to add `beta` and `trunc` though.
        self.kwargs.update(dict(beta=beta, trunc=trunc))
