import numpy as np
from astropy.coordinates import SkyCoord
from astropy import units as u
import matplotlib.pyplot as pl
from matplotlib import rcParams

from MulensModel.modelparameters import ModelParameters
from MulensModel.magnificationcurve import MagnificationCurve
from MulensModel.trajectory import Trajectory
from MulensModel.caustics import Caustics
from MulensModel.mulensparallaxvector import MulensParallaxVector
from MulensModel.satelliteskycoord import SatelliteSkyCoord
from MulensModel.utils import Utils
from MulensModel.fit import Fit
from MulensModel.mulensdata import MulensData
from MulensModel.limbdarkeningcoeffs import LimbDarkeningCoeffs


class Model(object):
    """
    A Model for a microlensing event with the specified parameters.

    Two ways to define the model:
        1. :py:obj:`parameters` = a
            :py:class:`~MulensModel.modelparameters.ModelParameters`
            object

        2. specify :py:obj:`t_0`, :py:obj:`u_0`, :py:obj:`t_E`
            (optionally: :py:obj:`rho`, :py:obj:`s`, :py:obj:`q`,
            :py:obj:`alpha`)

            Parallax may be specified either as :py:obj:`pi_E` OR
            :py:obj:`pi_E_N` and :py:obj:`pi_E_E`. :py:obj:`t_0_par`
            is optional. For default behavior see
            :py:class:`MulensModel.trajectory.Trajectory`

    Also optional: may specify :py:obj:`coords` OR :py:obj:`ra` and
    :py:obj:`dec`.

    Default values for parallax are all True. Use :func:`parallax()`
    to turn different parallax effects ON/OFF. If using satellite
    parallax, you may also specify an `ephemerides_file` (see
    :py:class:`MulensModel.mulensdata.MulensData`).

    Caveat:
    satellite parallax works for datasets, but not for
    model. i.e. The satellite parallax will be calculated correctly
    for the model evaluated at the data points, but satellite parallax
    is not implemented for the model alone.

    """

    def __init__(
        self, parameters=None, t_0=None, u_0=None, t_E=None, rho=None, s=None, 
        q=None, alpha=None, pi_E=None, pi_E_N=None, pi_E_E=None, pi_E_ref=None, 
        t_0_par=None, coords=None, ra=None, dec=None, ephemerides_file=None):
        """
        Two ways to define the model:
        1. parameters = a :class:`~MulensModel.modelparameters.ModelParameters` object
        2. specify t_0, u_0, t_E (optionally: rho, s, q, alpha, pi_E, t_0_par)

        When defining event coordinates, may specify coords as an
        astropy.coordinates.SkyCoord object, otherwise assumes RA is
        in hour angle and DEC is in degrees.

        Default values for parallax are all True. Use model.parallax() to turn
        different parallax effects ON/OFF.
        """
        # Initialize the parameters of the model
        if isinstance(parameters, ModelParameters):
            self._parameters = parameters
        elif parameters is None:
            self._parameters = ModelParameters()
        else:
            raise TypeError(
                "If specified, parameters must be a ModelParameters object.")

        # Set each model parameter
        if t_0 is not None:
            self.t_0 = t_0
        if u_0 is not None:
            self.u_0 = u_0
        if t_E is not None:
            self.t_E = t_E
        if rho is not None:
            self.rho = rho
        if s is not None:
            self.s = s

        if q is not None:
            if isinstance(q, (list, np.ndarray)):
                if len(q) > 1:
                    raise NotImplementedError(
                        'Too many q. Does not support more than 2 bodies.')
                else:
                    q = q[0]
            self.q = q

        if alpha is not None:
            self.alpha = alpha

        if s is not None or q is not None or alpha is not None:
            if s is None or q is None or alpha is None:
                raise AttributeError('If one of (s, q, alpha) is specified, ' +
                                    'all three must be specified.')

        self.t_0_par = t_0_par
        
        # Set the parallax
        par_msg = 'Must specify both or neither of pi_E_N and pi_E_E'
        if pi_E is not None:
            if pi_E_ref is None:
                self.pi_E = pi_E
            else:
                self._parameters.pi_E = MulensParallaxVector(pi_E, 
                                                                ref=pi_E_ref)
        if pi_E_N is not None:
            if pi_E_E is not None:
                if pi_E_ref is None:
                    self.pi_E_N = pi_E_N
                    self.pi_E_E = pi_E_E
                else:
                    self._parameters.pi_E = MulensParallaxVector(
                        pi_E_1=pi_E_N, pi_E_2=pi_E_E, ref=pi_E_ref)
            else:
                raise AttributeError(par_msg)
        else:
            if pi_E_E is not None:
                raise AttributeError(par_msg)

        # Set the coordinates of the event
        coords_msg = 'Must specify both or neither of ra and dec'
        self._coords = None
        if coords is not None:
            if isinstance(coords, SkyCoord):
                self._coords = coords
            else:
                self._coords = SkyCoord(coords, unit=(u.hourangle, u.deg))
        if ra is not None:
            if dec is not None:
                self._coords = SkyCoord(ra, dec, unit=(u.hourangle, u.deg))
            else:
                raise AttributeError(coords_msg)
        else:
            if ra is not None:
                raise AttributeError(coords_msg)

        self.ephemerides_file = ephemerides_file
        self._satellite_skycoord = None
        
        # Set some defaults
        self._parallax = {'earth_orbital': True, 
                          'satellite': True, 
                          'topocentric': True}
        self._default_magnification_method = 'point_source'
        self._methods = None
        self.caustics = None

        #Set dictionary to store plotting properties
        self.reset_plot_properties()
        
        self._limb_darkening_coeffs = LimbDarkeningCoeffs()
        self._bandpasses = []
        
        self._datasets = None

    def __repr__(self):
        return '{0}'.format(self._parameters)

    @property
    def t_0(self):
        """
        The time of the minimum projected separation between the source
        and the lens center of mass.
        """
        return self._parameters.t_0

    @t_0.setter
    def t_0(self, value):
        self._parameters.t_0 = value

    @property
    def u_0(self):
        """
        The time of minimum projected separation between the source
        and the lens center of mass.
        """
        return self._parameters._u_0
    
    @u_0.setter
    def u_0(self, value):
        self._parameters._u_0 = value

    @property
    def t_E(self):
        """
        The Einstein timescale. An *astropy.Quantity* object. Default unit 
        is "day".
        """
        return self._parameters.t_E

    @t_E.setter
    def t_E(self, value):
        self._parameters.t_E = value
       
    @property
    def rho(self):
        """source size relative to the Einstein ring radius"""
        return self._parameters.rho

    @rho.setter
    def rho(self, value):
        self._parameters.rho = value

    @property
    def pi_E(self):
        """
        The microlens parallax vector. May be specified either
        relative to the sky ("NorthEast") or relative to the binary
        lens axis ("ParPerp", i.e., parallel and perpendicular). "NorthEast" 
        is default. A :class:`MulensParallaxVector` object.
        """
        return self._parameters.pi_E

    @pi_E.setter
    def pi_E(self, value):
        self._parameters.pi_E = value

    @property
    def pi_E_N(self):
        """
        The North component of the microlens parallax vector.
        """
        return self._parameters.pi_E_N

    @pi_E_N.setter
    def pi_E_N(self, value):
        self._parameters.pi_E_N = value

    @property
    def pi_E_E(self):
        """
        The East component of the microlens parallax vector.
        """
        return self._parameters.pi_E_E

    @pi_E_E.setter
    def pi_E_E(self, value):
        self._parameters.pi_E_E = value

    @property
    def t_0_par(self):
        """reference time for parameters, in particular microlensing 
        parallax"""
        return self._t_0_par

    @t_0_par.setter
    def t_0_par(self, value):
        self._t_0_par = value

    @property
    def s(self):
        """lens components separation in units of theta_E"""
        return self._parameters.s

    @s.setter
    def s(self, value):
        self._parameters.s = value

    @property
    def q(self):
        """mass ratio of the lens components"""
        return self._parameters.q

    @q.setter
    def q(self, value):
        self._parameters.q = value

    @property
    def alpha(self):
        """angle between lens axis and source trajectory"""
        return self._parameters.alpha

    @alpha.setter
    def alpha(self, value):
        self._parameters.alpha = value
    
    @property
    def parameters(self):
        """
        The parameters of the model. A
        :class:`~MulensModel.modelparameters.ModelParameters` object.
        """
        return self._parameters

    def set_parameters(self, t_0=0., u_0=None, t_E=1., rho=None, s=None, 
                        q=None, alpha=None, pi_E=None, pi_E_N=None, 
                        pi_E_E=None, pi_E_ref=None):
        """
        Set the parameters of the model. Any parameter not explicitly
        specified will be set to None. Creates a new
        :class:`~MulensModel.modelparameters.ModelParameters` object,
        so all the previously set parameters will be forgotten.
        """
        self._parameters = ModelParameters(
            t_0=t_0, u_0=u_0, t_E=t_E, rho=rho, s=s, q=q, alpha=alpha, 
            pi_E=pi_E, pi_E_N=pi_E_N, pi_E_E=pi_E_E, pi_E_ref=pi_E_ref)
            
    def get_satellite_coords(self, times):
        """
        Get *astropy.SkyCoord* object that gives satellite positions for 
        given times.
        
        Parameters :
            times: *np.ndarray* or *list*
                Epochs for which satellite position is requested.
        
        Returns :
            satellite_skycoord: *astropy.SkyCoord*
                *SkyCoord* giving satellite positions. The parameter 
                *representation* is set to 'spherical'.
        """
        if self.ephemerides_file is None:
            return None
        else:
            satellite_skycoords = SatelliteSkyCoord(
                 ephemerides_file=self.ephemerides_file)
            return satellite_skycoords.get_satellite_coords(times)

    def magnification(self, time, satellite_skycoord=None, gamma=0.):
        """
        Calculate the model magnification for the given time(s).

        Parameters :
            time: *np.ndarray*, *list of floats*, or *float*
                Times for which magnification values are requested.

            satellite_skycoord: *astropy.coordinates.SkyCoord*, optional
                *SkyCoord* object that gives satellite positions. Must be 
                the same length as time parameter. Use only for satellite 
                parallax calculations.

            gamma: *float*, optional
                The limb darkening coefficient in gamma convention. Default is 
                0 which means no limb darkening effect.

        Returns :
            magnification: *np.ndarray*
                A vector of calculated magnification values.
        """
        #Check for type
        if not isinstance(time, np.ndarray):
            if isinstance(time, (np.float, float)):
                time = np.array([time])
            elif isinstance(time, list):
                time = np.array(time)
            else:
                raise TypeError('time must be a float, list, or np.ndarray')

        if satellite_skycoord is None:
            satellite_skycoord = self.get_satellite_coords(time)

        magnification_curve = MagnificationCurve(
            time, parameters=self._parameters, 
            parallax=self._parallax, t_0_par=self.t_0_par,
            coords=self._coords, 
            satellite_skycoord=satellite_skycoord,
            gamma=gamma)
        magnification_curve.set_magnification_methods(self._methods, 
                                        self._default_magnification_method)
        return magnification_curve.magnification

    @property
    def data_magnification(self):
        """
        a list of magnifications calculated for every dataset time vector
        """
        self._data_magnification = []

        for dataset in self.datasets:
            magnification = self.get_data_magnification(dataset)
            self._data_magnification.append(magnification)

        return self._data_magnification
        
    def get_data_magnification(self, dataset):
        """
        Get the model magnification for a dataset.

        Parameters :
            dataset: :class:`~MulensModel.mulensdata.MulensData`
                Dataset with epochs for which magnification will be given.
                Satellite and limb darkening information is taken into 
                account.

        Returns :
            magnification_vector: *np.ndarray*
                Values on magnification.

        """
        if dataset.ephemerides_file is not None:
            dataset_satellite_skycoord = dataset.satellite_skycoord
        else:
            dataset_satellite_skycoord = None
            
        if dataset.bandpass is None:
            gamma = 0.
        else:
            if dataset.bandpass not in self.bandpasses:
                raise ValueError(("Limb darkening coefficient requested for " +
                    "bandpass {:}, but not set before. Use " +
                    "set_limb_coef_gamma() or set_limb_coef_u()"
                    ).format(dataset.bandpass))
            gamma = self._limb_darkening_coeffs.limb_coef_gamma(
                                                            dataset.bandpass)
            
        magnification = self.magnification(
                dataset.time, satellite_skycoord=dataset_satellite_skycoord, 
                gamma=gamma)
        return magnification
    
    @property
    def datasets(self):
        """
        a list of datasets linked to given model
        """
        if self._datasets is None:
            raise ValueError('No datasets were linked to the model')
        return self._datasets
        
    def set_datasets(self, datasets, data_ref=0):
        """set *datasets* property"""
        self._datasets = datasets
        self._data_magnification = None
        self.data_ref = data_ref

    @property
    def coords(self):
        """
        Sky coordinates (RA, Dec) as an *astropy.SkyCoord* object
        """
        return self._coords

    @coords.setter
    def coords(self, new_value):
        if isinstance(new_value, SkyCoord):
            self._coords = new_value
        else:
            self._coords = SkyCoord(new_value, unit=(u.hourangle, u.deg))

    @property
    def ra(self):
        """
        Right Ascension.
        See also :obj:`MulensModel.event.Event.ra`
        """
        return self._coords.ra

    @ra.setter
    def ra(self, new_value):
        try:
            self._coords.ra = new_value
        except AttributeError:
            if self._coords is None:
                self._coords = SkyCoord(
                    new_value, 0.0, unit=(u.hourangle, u.deg))
            else:
                self._coords = SkyCoord(
                    new_value, self._coords.dec, unit=(u.hourangle, u.deg)) 

    @property
    def dec(self):
        """
        Declination.
        See also :obj:`MulensModel.event.Event.dec`
        """
        return self._coords.dec

    @dec.setter
    def dec(self, new_value):
        try:
            self._coords.dec = new_value
        except AttributeError:
            if self._coords is None:
                self._coords = SkyCoord(
                    0.0, new_value, unit=(u.hourangle, u.deg))
            else:
                self._coords = SkyCoord(
                    self._coords.ra, new_value, unit=(u.hourangle, u.deg))

    @property
    def galactic_l(self):
        """Galactic longitude. Note that for connivance, the values l > 180 
        degrees are represented as 360-l."""
        l = self._coords.galactic.l
        if l > 180. * u.deg:
            l = l - 360. * u.deg
        return l

    @property
    def galactic_b(self):
        """Galactic latitude calculated from (RA, Dec)"""
        return self._coords.galactic.b

    @property
    def ecliptic_lon(self):
        """ecliptic longitude calculated from (RA, Dec)"""
        from astropy.coordinates import GeocentricTrueEcliptic
        return self._coords.transform_to(GeocentricTrueEcliptic).lon

    @property
    def ecliptic_lat(self):
        """ecliptic latitude calculated from (RA, Dec) """
        from astropy.coordinates import GeocentricTrueEcliptic
        return self._coords.transform_to(GeocentricTrueEcliptic).lat

    def parallax(self, 
                earth_orbital=None, satellite=None, topocentric=None):
        """
        Specifies the types of the microlensing parallax that will be 
        included in calculations.

        Parameters :
            earth_orbital: *boolean*, optional
                Do you want to include the effect of Earth motion about 
                the Sun? Default is *False*.
            satellite: *boolean*, optional
                Do you want to include the effect of difference due to 
                separation between the Earth and satellite? Note that this 
                separation changes over time. Default is *False*.
            topocentric: *boolean*, optional
                Do you want to include the effect of different positions 
                of observatories on the Earth? Default is *False*. 
                Note that this is significant only for very high magnification 
                events and if high quality datasets are analyzed. 
                Hence, this effect is rarely needed.

        """
        if earth_orbital is None and satellite is None and topocentric is None:
            return self._parallax
        else:
            if earth_orbital is not None:
                self._parallax['earth_orbital'] = earth_orbital
            if satellite is not None:
                self._parallax['satellite'] = satellite
            if topocentric is not None:
                self._parallax['topocentric'] = topocentric

    def plot_magnification(
        self, times=None, t_range=None, t_start=None, t_stop=None, dt=None, 
        n_epochs=None, subtract_2450000=False, subtract_2460000=False, 
        **kwargs):
        """
        Plot the model magnification curve.

        Keywords:
            times : [float, list, numpy.ndarray]
                a list of times at which to plot the magnifications

            t_range, t_start, t_stop, dt, n_epochs : see :func:`set_times`

            subtract_2450000, subtract_2460000 : boolean, optional
                If True, subtracts 2450000 or 2460000 from the time
                axis to get more human-scale numbers.

        ``**kwargs`` any arguments accepted by matplotlib.pyplot.plot().

        """
        if times is None:
            times = self.set_times(
                t_range=t_range, t_start=t_start, 
                t_stop=t_stop, dt=dt, 
                n_epochs=n_epochs)
        subtract = 0.
        if subtract_2450000:
            subtract = 2450000.
        if subtract_2460000:
            subtract = 2460000.

        pl.plot(times-subtract, self.magnification(times), **kwargs)
        pl.ylabel('Magnification')
        pl.xlabel('Time')

    def plot_lc(self, times=None, t_range=None, t_start=None, t_stop=None, 
            dt=None, n_epochs=None, data_ref=None, f_source=None, f_blend=None, 
            subtract_2450000=False, subtract_2460000=False, **kwargs):
        """
        plot the model light curve in magnitudes. 

        Keywords:
            times : [float, list, numpy.ndarray]
                a list of times at which to plot the magnifications

            t_range, t_start, t_stop, dt, n_epochs : see :func:`set_times`

            subtract_2450000, subtract_2460000 : boolean, optional
                If True, subtracts 2450000 or 2460000 from the time
                axis to get more human-scale numbers. If using, make
                sure to also set the same settings for all other
                plotting calls (e.g. :func:`plot_data()`)

            data_ref : int or a dataset
                Reference dataset to scale the model to. See
                :func:`get_ref_fluxes()`

            f_source, f_blend : float
                Explicitly specify the source and blend fluxes in a system
                where flux = 1 corresponds to utils.MAG_ZEROPOINT (= 22 mag). 

        ``**kwargs`` any arguments accepted by matplotlib.pyplot.plot().

        Either data_set or (f_source, f_blend) must be set, but there
        is no explicit check for this. Default behavior is probably to
        throw an exception that no data have been specified (see
        :func:`get_ref_fluxes()`).

        """
        if times is None:
            times = self.set_times(
                t_range=t_range, t_start=t_start, 
                t_stop=t_stop, dt=dt, 
                n_epochs=n_epochs)

        if data_ref is not None:
            self.data_ref = data_ref

        if (f_source is None) and (f_blend is None):
            (f_source, f_blend) = self.get_ref_fluxes(data_ref=data_ref)
        elif (f_source is None) or (f_blend is None):
            raise AttributeError(
                'If f_source is set, f_blend must also be set and vice versa.')
            
        flux = f_source * self.magnification(times) + f_blend

        subtract = 0.
        if subtract_2450000:
            subtract = 2450000.
        if subtract_2460000:
            subtract = 2460000.

        pl.plot(times-subtract, Utils.get_mag_from_flux(flux), **kwargs)
        pl.ylabel('Magnitude')
        pl.xlabel('Time')
        
        (ymin, ymax) = pl.gca().get_ylim()
        if ymax > ymin:
            pl.gca().invert_yaxis()

    def get_ref_fluxes(self, data_ref=None):
        """
        Get source and blending fluxes for the model by findig the
        best-fit values compared to data_ref.

        Parameters:
            data_ref: *:py:class:`~MulensModel.mulensdata.MulensData`* or *int*
                Reference dataset. If *int*, corresponds to the index of 
                the dataset in self.datasets. If None, than the first dataset 
                will be used.

        Returns :
            f_source: *float*
                source flux
            f_blend: *float*
                blending flux

        Determine the reference flux system from the
        datasets. The *data_ref* may either be a dataset or the index of a
        dataset (if :func:`Model.set_datasets()` was previously called). If
        *data_ref* is not set, it will use the first dataset. If you
        call this without calling :func:`set_datasets()` first, there will be
        an exception and that's on you.
        """
        if data_ref is None:
            if self._datasets is None:
                raise ValueError('You cannot get reference flux for Model if' +
                                ' you have not linked data first.')
            if isinstance(self.data_ref, MulensData):
                data = self.data_ref
            else:
                data = self.datasets[self.data_ref]
        elif isinstance(data_ref, MulensData):
            data = data_ref
            self.data_ref = data_ref
        else:
            data = self.datasets[data_ref]
            self.data_ref = data_ref

        fit = Fit(data=data, magnification=[self.get_data_magnification(data)])
        fit.fit_fluxes()
        f_source = fit.flux_of_sources(data)
        f_blend = fit.blending_flux(data)

        return (f_source, f_blend)
        
    def reset_plot_properties(self):
        """resets internal settings for plotting"""
        self.plot_properties = {}

    def _store_plot_properties(
        self, color_list=None, marker_list=None, size_list=None, 
        label_list=None, **kwargs):
        """
        Store plot properties for each data set.
        """
        if color_list is not None:
            self.plot_properties['color_list'] = color_list
        if marker_list is not None:
            self.plot_properties['marker_list'] = marker_list
        if size_list is not None:
            self.plot_properties['size_list'] = size_list
        if label_list is not None:
            self.plot_properties['label_list'] = label_list
        if len(kwargs) > 0:
            self.plot_properties['other_kwargs'] = kwargs
    
    def _set_plot_kwargs(self, index, show_errorbars=True, bad_data=False):
        """
        Set ``**kwargs`` arguments for plotting. If set, use previous values. 
        But new values take precedence. 
        
        Automatically handles (some) differences in keywords for pl.errorbar 
        vs. pl.scatter: fmt/marker, markersize/s

        Parameters :
            index: *int*
                index of the dataset for which ``**kwargs`` will be set
            
            show_errorbars: *boolean*, optional
                Do you want to see errorbars on the plot? Defaults to *True*.

            bad_data: *boolean*, optional
                Default is *False* --> set ``**kwargs`` for plotting good data,
                i.e., *marker*='o', *size*=3. If *True*, then *marker*='x' and 
                *size*=10.
       """                
        #Set different keywords for pl.errorbar vs. pl.scatter
        if show_errorbars:
            marker_key = 'fmt'
            size_key = 'markersize' # In pl.errorbar(), 'ms' is equivalent.
        else:
            marker_key = 'marker'
            size_key = 's'
    
        #Create new kwargs dictionary
        new_kwargs = {}  
        
        #Set defaults
        if 'color_list' not in self.plot_properties.keys():
            self.plot_properties['color_list'] =  rcParams[
                'axes.prop_cycle'].by_key()['color']
        if not bad_data:
            new_kwargs[marker_key] = 'o'
            new_kwargs[size_key] = 3
        else:
            new_kwargs[marker_key] = 'x'
            new_kwargs[size_key] = 10
        
        #Set custom
        if len(self.plot_properties) > 0:
            if 'color_list' in self.plot_properties.keys():
                new_kwargs['color'] = self.plot_properties['color_list'][index]

            if 'marker_list' in self.plot_properties.keys():
                new_kwargs[marker_key] = self.plot_properties['marker_list'][index]

            if 'size_list' in self.plot_properties.keys():
                new_kwargs[size_key] = self.plot_properties['size_list'][index]

            if 'label_list' in self.plot_properties.keys():
                new_kwargs['label'] = self.plot_properties['label_list'][index]
                
            if 'other_kwargs' in self.plot_properties.keys():
                for (key, value) in self.plot_properties['other_kwargs'].items():
                    if key in ['markersize', 'ms', 's']:
                        new_kwargs[size_key] = value
                    elif key in ['marker', 'fmt']:
                        new_kwargs[marker_key] = value
                    else:
                        new_kwargs[key] = value
                        
        return new_kwargs

    def plot_data(self, data_ref=None, show_errorbars=True, show_bad=False, 
            color_list=None, marker_list=None, size_list=None,  
            label_list=None, subtract_2450000=False, subtract_2460000=False, 
            **kwargs):
        """
        Plot the data scaled to the model. 

        Keywords:
            data_ref : see :func:`get_ref_fluxes()`
                If data_ref is not specified, uses the first dataset
                as the reference for flux scale.

            show_errorbars : boolean
                If show_errorbars is True (default), plots with
                matplotlib.errorbar(). If False, plots with
                matplotib.scatter().

            show_bad : boolean, optional
                if False, bad data are suppressed (default). 
                if True, shows points marked as bad
                (:py:obj:`mulensdata.MulensData.bad`) as 'x'
        
            color_list, marker_list, size_list : list, optional
                Controls point types for each dataset (length must be
                equal to the number of datasets). May specify none,
                some, or all of these lists. Automatically handles
                keyword variations in errorbar() vs. scatter():
                e.g. fmt/marker, markersize/s.

            label_list : list
                Attacheds a label to each data set, which can be used
                to create a legend by calling pl.legend().

            subtract_2450000, subtract_2460000 : boolean, optional
                If True, subtracts 2450000 or 2460000 from the time
                axis to get more human-scale numbers. If using, make
                sure to also set the same settings for all other
                plotting calls (e.g. :func:`plot_lc()`).

        May also use ``**kwargs`` or some combination of the lists and
        ``**kwargs``. e.g. set color_list to specify which color each
        data set should be plotted in, but use fmt='s' to make all
        data points plotted as squares.

        ``**kwargs`` (and point type lists) are remembered and used in
        subsequent calls to both plot_data() and plot_residuals().

        """
        if data_ref is not None:
            self.data_ref = data_ref

        self._store_plot_properties(
            color_list=color_list, marker_list=marker_list, 
            size_list=size_list, label_list=label_list,
            **kwargs)

        #Reference flux scale
        (f_source_0, f_blend_0) = self.get_ref_fluxes(data_ref=data_ref)

        #Get fluxes for all datasets
        fit = Fit(data=self.datasets, magnification=self.data_magnification)
        fit.fit_fluxes()
        
        # Set plot defaults.
        t_min = 3000000.
        t_max = 0.
        subtract = 0.
        if subtract_2450000:
            subtract = 2450000.
        if subtract_2460000:
            subtract = 2460000.

        #plot each dataset
        for (i, data) in enumerate(self.datasets):
            #Calculate scaled flux
            f_source = fit.flux_of_sources(data)
            f_blend = fit.blending_flux(data)
            flux = f_source_0 * (data.flux - f_blend) / f_source + f_blend_0

            new_kwargs = self._set_plot_kwargs(
                i, show_errorbars=show_errorbars)
            if show_bad:
                bad_kwargs = self._set_plot_kwargs(
                    i, show_errorbars=show_errorbars, bad_data=True)
                bad_kwargs['label'] = None

            #Plot
            if show_errorbars:
                err_flux = f_source_0 * data.err_flux / f_source
                (mag, err) = Utils.get_mag_and_err_from_flux(flux, err_flux)
                pl.errorbar(
                    data.time[np.logical_not(data.bad)] - subtract, 
                    mag[np.logical_not(data.bad)], 
                    yerr=err[np.logical_not(data.bad)], 
                    **new_kwargs) 
                if show_bad:
                    pl.errorbar(
                        data.time[data.bad] - subtract, mag[data.bad], 
                        yerr=err[data.bad], **bad_kwargs) 
            else:
                mag = Utils.get_mag_from_flux(flux)
                pl.scatter(
                    data.time[np.logical_not(data.bad)] - subtract, 
                    mag[np.logical_not(data.bad)], lw=0., **new_kwargs)
                if show_bad:
                    pl.scatter(
                        data.time[data.bad] - subtract, mag[data.bad],
                        **bad_kwargs)
                               
            #Set plot limits
            t_min = min(t_min, np.min(data.time))
            t_max = max(t_max, np.max(data.time))

        #Plot properties
        pl.ylabel('Magnitude')
        pl.xlabel('Time')
        pl.xlim(t_min-subtract, t_max-subtract)

        (ymin, ymax) = pl.gca().get_ylim()
        if ymax > ymin:
            pl.gca().invert_yaxis()

    def plot_residuals(self, show_errorbars=True, color_list=None, 
            marker_list=None, size_list=None, label_list=None, data_ref=None, 
            subtract_2450000=False, subtract_2460000=False, **kwargs):
        """
        Plot the residuals (in magnitudes) of the model. 
        Uses the best f_source, f_blend for each dataset 
        (not scaled to a particular photometric system).

        For explanation of ``**kwargs`` and other keywords, see doctrings in 
        :func:`plot_data()`. 

        """
        if data_ref is not None:
            self.data_ref = data_ref

        self._store_plot_properties(
            color_list=color_list, marker_list=marker_list, 
            size_list=size_list, label_list=label_list,
            **kwargs)
            
        #Get fluxes for all datasets
        fit = Fit(data=self.datasets, magnification=self.data_magnification)
        fit.fit_fluxes()

        #Plot limit parameters
        delta_mag = 0.
        t_min = 3000000.
        t_max = 0.
        subtract = 0.
        if subtract_2450000:
            subtract = 2450000.
        if subtract_2460000:
            subtract = 2460000.

        #Plot zeropoint line
        pl.plot([0., 3000000.], [0., 0.], color='black')
        
        #Plot residuals
        for (i, data) in enumerate(self.datasets):
            #Calculate model magnitude
            f_source = fit.flux_of_sources(data)
            f_blend = fit.blending_flux(data)
            model_flux = f_source * self.magnification(data.time) + f_blend
            model_mag = Utils.get_mag_from_flux(model_flux)

            #Calculate Residuals
            (mag, err) = Utils.get_mag_and_err_from_flux(data.flux, 
                                                       data.err_flux)
            residuals = model_mag - mag
            delta_mag = max(delta_mag, np.max(np.abs(residuals)))

            #Plot
            new_kwargs = self._set_plot_kwargs(i, 
                                                show_errorbars=show_errorbars)
            if show_errorbars:
                pl.errorbar(data.time-subtract, residuals, yerr=err, 
                            **new_kwargs) 
            else:
                pl.scatter(data.time-subtract, residuals, lw=0, **new_kwargs)

            #Set plot limits
            t_min = min(t_min, np.min(data.time))
            t_max = max(t_max, np.max(data.time))
       
        if delta_mag > 1.:
            delta_mag = 0.5

        #Plot properties
        pl.ylim(-delta_mag, delta_mag)
        pl.xlim(t_min-subtract, t_max-subtract)
        pl.ylabel('Residuals')
        pl.xlabel('Time')

    def plot_trajectory(self, times=None, t_range=None, t_start=None, 
                        t_stop=None, dt=None, n_epochs=None, caustics=False, 
                        show_data=False, arrow=True, satellite_skycoord=None, 
                        **kwargs):
        """
        Plot the source trajectory.

        Optional keyword arguments:

          times, t_range, t_start, t_stop, dt, n_epochs may all be
          used to specify exactly when to plot the source
          trajectory. times=specific dates, t_range=range of times,
          (t_start, t_stop)=range of times with optional dt OR
          n_epochs.

          caustics = plot the caustic structure in addition to the
          source trajectory. default=False (off). For finer control of
          plotting features, e.g. color, use self.plot_caustics()
          instead.

          show_data = mark epochs of data (Not Implemented, marker
          types should match data plotting.)

          arrow = show the direction of the motion. default=True (on)

          satellite_skycoord should allow user to specify the trajectory
          is calculated for a satellite. (Not checked)

          ``**kwargs`` controls plotting features of the trajectory.
        """
        if times is None:
            times = self.set_times(
                t_range=t_range, t_start=t_start, 
                t_stop=t_stop, dt=dt, 
                n_epochs=n_epochs)

        if satellite_skycoord is None:
            satellite_skycoord = self.get_satellite_coords(times)

        trajectory = Trajectory(
            times, parameters=self._parameters, parallax=self._parallax, 
            t_0_par=self.t_0_par, coords=self._coords, 
            satellite_skycoord=satellite_skycoord)

        pl.plot(trajectory.x, trajectory.y, **kwargs)
        
        if arrow:
            index = int(len(times)/2)
            pl.scatter(
                trajectory.x[index], trajectory.y[index], 
                marker=(3, 0, self.alpha), s=50)

        if caustics:
            self.plot_caustics(marker='.', color='red')

    def plot_caustics(self, n_points=5000, **kwargs):
        """
        Plot the caustic structure. 
        
        Parameters :
            n_points: *int*, optional 
                specifies the number of points on the caustic
            
            ``**kwargs``
                kwargs passes to :func:`plt.plot()`
        """
        if self.caustics is None:
            self.caustics = Caustics(q=self.q, s=self.s)

        self.caustics.plot(n_points=n_points, **kwargs)
        
    def set_times(
        self, t_range=None, t_start=None, 
        t_stop=None, dt=None, n_epochs=1000):
        """
        Retrun a list of times. If no keywords are specified, default
        is 1000 epochs from [t_0 - 1.5*t_E, t_0 + 1.5*t_E].

        Keywords (all optional) :
            t_range : [list, tuple]
                form [t_start, t_stop]
            t_start, t_stop : float
                a start or stop time.
            dt : float
                the interval spacing between successive points
            n_epochs : int
                the number of epochs (evenly spaced)
        """
        if t_range is not None:
            t_start = t_range[0]
            t_stop = t_range[1]

        n_tE = 1.5
        if t_start is None:
            t_start = self.t_0 - (n_tE * self.t_E)
        if t_stop is None:
            t_stop = self.t_0 + (n_tE * self.t_E)

        if dt is None:
            dt = (t_stop - t_start) / float(n_epochs)

        return np.arange(t_start, t_stop+dt, dt)

    def set_default_magnification_method(self, method):
        """Stores information on method to be used, when no method is
        directly specified.
        
        Parameters:
            method: *str*
                Name of the method to be used.
        """
        self._default_magnification_method = method

    def set_magnification_methods(self, methods):
        """Sets methods used for magnification calculation.
       
        Parameters :
            methods: *list*
                List that specifies which methods (*str*) should be used when 
                (*float* values for julian dates). Given method will be used 
                for times between the times between which it is on the list, 
                e.g., 
                
                methods = [2455746., 'Quadrupole', 2455746.6, 'Hexadecapole', 
                2455746.7, 'VBBL', 2455747., 'Hexadecapole', 2455747.15, 
                'Quadrupole', 2455748.]
        """
        self._methods = methods

    def set_limb_coef_gamma(self, bandpass, coef):
        """Store gamma limb darkening coefficient for given band.
                
        Parameters :
            bandpass: *str*
                Bandpass for which coefficient you provide.
            
            coef: *float*
                Value of the coefficient.
        
        """
        if bandpass not in self._bandpasses:
            self._bandpasses.append(bandpass)
        self._limb_darkening_coeffs.set_limb_coef_gamma(bandpass, coef)

    def set_limb_coef_u(self, bandpass, coef):
        """Store u limb darkening coefficient for given band.
        
        Parameters :
            bandpass: *str*
                Bandpass for which coefficient you provide.
            
            coef: *float*
                Value of the coefficient.
        
        """
        if bandpass not in self._bandpasses:
            self._bandpasses.append(bandpass)
        self._limb_darkening_coeffs.set_limb_coef_u(bandpass, coef)

    def limb_coef_gamma(self, bandpass):
        """Get gamma limb darkening coefficient for given band.
                
        Parameters :
            bandpass: *str*
                Bandpass for which coefficient will be provided.
        
        Returns :
            gamma: *float*
                limb darkening coefficient
            
        """
        return self._limb_darkening_coeffs.limb_coef_gamma(bandpass)

    def limb_coef_u(self, bandpass):
        """Get u limb darkening coefficient for given band.
        
        Parameters :
            bandpass: *str*
                Bandpass for which coefficient will be provided.
        
        Returns :
            u: *float*
                limb darkening coefficient
        
        """
        return self._limb_darkening_coeffs.limb_coef_u(bandpass)

    @property
    def bandpasses(self):
        """
        list of all bandpasses for which limb darkening coefficients are set
        """
        return self._bandpasses

