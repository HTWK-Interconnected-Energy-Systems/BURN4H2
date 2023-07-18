"""Script to test the clear sky weather model of pvlib."""

import pvlib
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pvlib.location import Location

coordinates = [
    (52.5, 13.4, 'Berlin', 34, 'Etc/GMT-1'),
]

new_index = pd.date_range(
    start='2016-01-01',
    periods=8760,
    freq='1h',
    tz='Etc/GMT-1'
)

weather = None
for location in coordinates:
    latitude, longitude, name, altitude, timezone = location
    weather = pvlib.iotools.get_pvgis_tmy(
        latitude,
        longitude,
        map_variables=True
    )[0]
    weather.index.name = 'utc_time'
    weather.index = new_index

print('Weather info:', weather.info())

# fig, ax = plt.subplots()
# ax.plot(
#     weather.index[0:72],
#     weather['ghi'][0:72],
#     label='ghi'
# )
# ax.plot(
#     weather.index[0:72],
#     weather['dni'][0:72],
#     label='dni',
# )
# ax.plot(
#     weather.index[0:72],
#     weather['dhi'][0:72],
#     label='dhi',
# )
# ax.set_ylabel('Irradiance [W/m²]')
# ax.legend()
# ax.grid()
# plt.show()

berlin = Location(
    latitude=52.5,
    longitude=13.4,
    tz='Etc/GMT-1',
    altitude=34,
    name='Berlin'
)

times = pd.date_range(
    start='2016-01-01',
    periods=168,
    freq='1h',
    tz=berlin.tz
)

print('Times:', times)

cs = berlin.get_clearsky(times)

# Define modules and inverter parameters
sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')
module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']
print(module)
inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS[
    'sapm'][
    'open_rack_glass_glass']

tilt = 45
azimuth = 180

mount = pvlib.pvsystem.FixedMount(
    surface_tilt=tilt,
    surface_azimuth=azimuth,
)
array = pvlib.pvsystem.Array(
    mount=mount,
    module_parameters=module,
    temperature_model_parameters=temperature_model_parameters,
)
system = pvlib.pvsystem.PVSystem(
    arrays=[array],
    inverter_parameters=inverter
)
mc = pvlib.modelchain.ModelChain(
    system,
    berlin
)

mc.run_model(cs)

peak_power = module.Impo * module.Vmpo
print(peak_power)

actual_energy = pd.Series(mc.results.ac)
print(actual_energy)
print(actual_energy.index)
capacity_factors = pd.Series(mc.results.ac / peak_power)

print(cs)

# fig, (ax1, ax3) = plt.subplots(
#     nrows=1,
#     ncols=2
# )
# l1, = ax1.plot(actual_energy, 'C0', label='produced energy')
# ax2 = ax1.twinx()
# l2, = ax2.plot(capacity_factors, 'C1', label='capacity factor')
# ax2.legend([l1, l2], ['produced energy', 'capacity factor'])
# ax1.tick_params('x', labelrotation=90)
# ax1.set_ylabel('produced energy [Wh]')
# ax2.set_ylabel('capacity factor [-]')
# ax2.set_ylim(0, 1)
# ax1.set_ylim(0, 150)
#
# ax3.plot(cs['ghi'], label='ghi')
# ax3.plot(cs['dni'], label='dni')
# ax3.plot(cs['dhi'], label='dhi')
# ax3.tick_params('x', labelrotation=90)
# ax3.set_ylabel('irradiance [W/m²]')
# ax3.legend()
#
# plt.tight_layout()
# plt.show()
