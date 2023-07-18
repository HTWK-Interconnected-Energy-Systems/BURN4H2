"""Script for generating a time series of correction factor data for
pv-moduls with the clear sky weather model."""
import pvlib
import pandas as pd
from pvlib.location import Location

LOCATION = Location(
    latitude=52.5,
    longitude=13.4,
    name='Berlin',
    altitude=34,
    tz='Etc/GMT-1'
)
TIMES = pd.date_range(
    start='2016-01-01',  # format YYYY-MM-DD
    end='2017-01-01',
    freq='60min',
    tz='Etc/GMT-1'
)

sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')
module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']
inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS[
    'sapm'][
    'open_rack_glass_glass']
peak_power = module.Impo * module.Vmpo

irradiation = LOCATION.get_clearsky(TIMES)

capacity_factors = pd.DataFrame()
for azimuth in range(90, 360, 90):
    for tilt in range(0, 105, 15):
        mount = pvlib.pvsystem.FixedMount(
            surface_tilt=azimuth,
            surface_azimuth=tilt
        )
        array = pvlib.pvsystem.Array(
            mount=mount,
            module_parameters=module,
            temperature_model_parameters=temperature_model_parameters
        )
        system = pvlib.pvsystem.PVSystem(
            arrays=[array],
            inverter_parameters=inverter
        )
        mc = pvlib.modelchain.ModelChain(
            system=system,
            location=LOCATION
        )
        mc.run_model(
            weather=irradiation
        )
        model_id = str(azimuth) + '_' + str(tilt)
        capacity_factors[model_id] = round(mc.results.ac / peak_power, 3)

capacity_factors.to_csv('../data/correction_factors.csv')
