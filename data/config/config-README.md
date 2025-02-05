# Configuration Files Documentation

## Naming Convention

```python
{price_scenario}_{solar_thermal_scenario}_{local_heat_demand_scenario}_{year}.json
```

Where:
- price_scenario: gee23, kt23, ue23
- solar_thermal_scenario: ST-min, ST-max
- local_heat_demand_scenario: NW-ref, NW-ext
- year: 2028-2050

## Scenario Descriptions

### Price Scenarios
- gee23: 
- kt23: 
- ue23: 


### Solar Thermal (ST) Scenarios
- ST-min: Minimum solar thermal capacity
- ST-max: Maximum solar thermal capacity


### Network (NW) Scenarios
- NW-ref: Reference local heat demand configuration
- NW-ext: Extended consumers

### Example Configuration

```python
gee23_ST-min_NW-ref_2028.json
```

## File Structure
- file: Path to input data relative to input
- index: Time index parameter (typically "t")
- param: Parameter name in the optimization model

## Input Parameters
- gas_price: Natural gas price timeseries
- power_price: Electricity price timeseries
- heat_demand: District heating demand
- solar_thermal_heat_profile: Solar thermal generation profile
- local_heat_demand: Local heating network demand

## Scenario Matrix
| Configuration File           | Price Scenario | Solar Thermal | Local Heat Demand  | Description                          |
|------------------------------|----------------|---------------|--------------------|--------------------------------------|
| gee23_ST-min_NW-ref_2028     | Gee23          | Minimum       | Reference          | Gee23 scenario with reference local heat demand, minimum ST        |
| gee23_ST-max_NW-ref_2028     | Gee23          | Maximum       | Reference          | Gee23 scenario with reference local heat demand, maximum ST        |
| gee23_ST-min_NW-ext_2028     | Gee23          | Minimum       | Extended           | Gee23 scenario with extended consumers, minimum ST         |
| gee23_ST-max_NW-ext_2028     | Gee23          | Maximum       | Extended           | Gee23 scenario with extended consumers, maximum ST         |


## Notes
- All timeseries use hourly resolution
- Prices are in €/MWh
- Heat demands are in MW

