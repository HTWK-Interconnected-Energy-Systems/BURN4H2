"""Tests the ac output of different surface tilts for one location."""

import pvlib
import pandas as pd
import matplotlib.pyplot as plt

coordinates = [52.5, 13.4, 'Berlin', 34, 'Etc/GMT-1']

# Define modules and inverter parameters
sandia_modules = pvlib.pvsystem.retrieve_sam('SandiaMod')
sapm_inverters = pvlib.pvsystem.retrieve_sam('cecinverter')
module = sandia_modules['Canadian_Solar_CS5P_220M___2009_']
inverter = sapm_inverters['ABB__MICRO_0_25_I_OUTD_US_208__208V_']
temperature_model_parameters = pvlib.temperature.TEMPERATURE_MODEL_PARAMETERS[
    'sapm'][
    'open_rack_glass_glass']

# Prepare weather data
latitude, longitude, name, altitude, timezone = coordinates
weather = pvlib.iotools.get_pvgis_tmy(
    latitude,
    longitude,
    map_variables=True
)[0]
weather.index.name = 'utc_time'

new_index = pd.date_range(
    start=pd.to_datetime('1/1/2016').tz_localize('Europe/Berlin'),
    periods=8760,
    freq='H'
)
weather.index = new_index

energies = {}

location = pvlib.location.Location(
    latitude,
    longitude,
    name=name,
    altitude=altitude,
    tz=timezone,
)

for tilt in range(0, 100, 10):
    for azimuth in range(0, 450, 90):
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
            location
        )

        mc.run_model(weather)

        annual_energy = mc.results.ac.sum()
        energies[tilt, azimuth] = annual_energy / 1000

energies = pd.Series(energies)
print(energies)

p = pd.Series(mc.results.ac)
plt.ylabel('Energy yield [kWh]')
p.plot()
plt.show()


energies.plot(kind='bar', rot=90)
plt.ylabel('Yearly energy yield [kWh]')
plt.grid()

# plt.show()

