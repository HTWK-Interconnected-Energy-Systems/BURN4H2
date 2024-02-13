import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import *
from pyomo.network import *

import blocks.chp as chp
import blocks.grid as grid
import blocks.storage as storage
import blocks.res as res
import blocks.electrolyzer as elec
import blocks.heatpump as hp


# Path
PATH_IN = 'data/input/'
PATH_OUT = 'data/output/'


# Select Solver
opt = SolverFactory('gurobi')
opt.options['TimeLimit'] = 3600   # solver will stop after x seconds
opt.options['MIPGap'] = 0.01      # solver will stop if gap <= 1%


# Declare constant prices
CO2_PRICE = 95.98   # price in €/t
HEAT_PRICE = 0      # price in €/MWh
H2_PRICE = 81.01    # price in €/MWh

# Create DataPortal
data = DataPortal()


# Read Time Series
data.load(
    # filename=PATH_IN + 'prices/dummy/gas_price.csv',
    filename=PATH_IN + 'prices/gee23/gas_price_2024.csv',
    index='t',
    param='gas_price'
)
data.load(
    # filename=PATH_IN + 'prices/dummy/power_price.csv',
    filename=PATH_IN + 'prices/gee23/power_price_2024.csv',
    index='t',
    param='power_price'
)
data.load(
    filename=PATH_IN + 'demands/heat.csv',
    index='t',
    param='heat_demand'
)


# Get performance parameters for the assets
chp_data = pd.read_csv(
    PATH_IN + 'assets/chp.csv',
    index_col=0
)
electrical_grid_data = pd.read_csv(
    PATH_IN + 'assets/electrical_grid.csv',
    index_col=0
)
battery_storage_data = pd.read_csv(
    PATH_IN + 'assets/battery_storage.csv',
    index_col=0
)
pv_data = pd.read_csv(
    PATH_IN + 'assets/pv.csv',
    index_col=0
)
pv_capacity_factors = pd.read_csv(
    PATH_IN + 'pv_capacity_factors/leipzig_t45_a180.csv',
    index_col=0
)
electrolyzer_data = pd.read_csv(
    PATH_IN + 'assets/electrolyzer.csv',
    index_col=0
)
hydrogen_grid_data = pd.read_csv(
    PATH_IN + 'assets/hydrogen_grid.csv',
    index_col=0
)
# hydrogen_storage_data = pd.read_csv(
#     PATH_IN + 'assets/hydrogen_storage.csv',
#     index_col=0
# )
heatpump_data = pd.read_csv(
    PATH_IN + 'assets/heatpump.csv',
    index_col=0
)
heat_grid_data = pd.read_csv(
    PATH_IN + 'assets/heat_grid.csv',
    index_col=0
)
heat_storage_data = pd.read_csv(
    PATH_IN + 'assets/heat_storage.csv',
    index_col=0
)


# Create instance
chp_obj = chp.Chp(
    data=chp_data,
    hydrogen_admixture=0
    )
electrical_grid_obj = grid.Grid(
    data=electrical_grid_data
    )
battery_storage_obj = storage.BatteryStorage(
    battery_storage_data
    )
pv_obj = res.Photovoltaics(
    data=pv_data,
    capacity_factors=pv_capacity_factors
    )
electrolyzer_obj = elec.Electrolyzer(
    data=electrolyzer_data
    )
hydrogen_grid_obj = grid.Grid(
    data=hydrogen_grid_data
    )
natural_gas_grid_obj = grid.Grid()
# hydrogen_storage_obj = storage.HydrogenStorage(
#     data=hydrogen_storage_data
#     )
heatpump_obj = hp.Heatpump(
    data=heatpump_data
    )
heat_grid_obj = grid.Grid(
    data=heat_grid_data
    )
heat_storage_obj = storage.HeatStorage(
    data=heat_storage_data
)


# Define abstract model
m = AbstractModel()


# Define sets
m.t = Set(ordered=True)


# Define parameters
m.gas_price = Param(m.t)
m.power_price = Param(m.t)
m.heat_demand = Param(m.t)


# Define block components
m.chp_1 = Block(
    rule=chp_obj.chp_block_rule
    )
m.chp_2 = Block(
    rule=chp_obj.chp_block_rule
)
m.electrical_grid = Block(
    rule=electrical_grid_obj.electrical_grid_block_rule
    )
m.battery_storage = Block(
    rule=battery_storage_obj.battery_storage_block_rule
    )
m.pv = Block(
    rule=pv_obj.pv_block_rule
    )
m.electrolyzer_1 = Block(
    rule=electrolyzer_obj.electrolyzer_block_rule
    )
m.electrolyzer_2 = Block(
    rule=electrolyzer_obj.electrolyzer_block_rule
    )
m.electrolyzer_3 = Block(
    rule=electrolyzer_obj.electrolyzer_block_rule
    )
m.electrolyzer_4 = Block(
    rule=electrolyzer_obj.electrolyzer_block_rule
    )
m.electrolyzer_5 = Block(
    rule=electrolyzer_obj.electrolyzer_block_rule
    )
m.electrolyzer_6 = Block(
    rule=electrolyzer_obj.electrolyzer_block_rule
    )
m.hydrogen_grid = Block(
    rule=hydrogen_grid_obj.hydrogen_grid_block_rule
    )
m.ngas_grid = Block(
    rule=natural_gas_grid_obj.natural_gas_grid_block_rule
    )
# m.hydrogen_storage = Block(
#     rule=hydrogen_storage_obj.hydrogen_storage_block_rule
#     )
m.heatpump = Block(
    rule=heatpump_obj.heatpump_block_rule
    )
m.heat_grid = Block(
    rule=heat_grid_obj.heat_grid_block_rule
    )
m.heat_storage = Block(
    rule=heat_storage_obj.heat_storage_block_rule
    )


# Define Objective
def obj_expression(m):
    """ Objective Function """
    return (quicksum(m.ngas_grid.ngas_balance[t] * m.gas_price[t] for t in m.t) +
            quicksum(m.chp_1.co2[t] * CO2_PRICE for t in m.t) +
            quicksum(m.chp_2.co2[t] * CO2_PRICE for t in m.t) +
            quicksum(m.electrical_grid.power_balance[t] * m.power_price[t] for t in m.t) +
            quicksum(m.hydrogen_grid.hydrogen_balance[t] * H2_PRICE for t in m.t) -
            quicksum(m.heat_grid.heat_feedin[t] * HEAT_PRICE for t in m.t))


m.obj = Objective(
    rule=obj_expression,
    sense=minimize
    )


# Create instance
instance = m.create_instance(data)


# Define arcs
instance.arc01 = Arc(
    source=instance.chp_1.power_out,
    destination=instance.electrical_grid.power_in
)
instance.arc02 = Arc(
    source=instance.chp_2.power_out,
    destination=instance.electrical_grid.power_in
)
instance.arc03 = Arc(
    source=instance.pv.power_out,
    destination=instance.electrical_grid.power_in
)
instance.arc04 = Arc(
    source=instance.battery_storage.power_out,
    destination=instance.electrical_grid.power_in
)
instance.arc05 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.battery_storage.power_in
)
instance.arc06 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.electrolyzer_1.power_in
)
instance.arc07 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.electrolyzer_2.power_in
)
instance.arc08 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.electrolyzer_3.power_in
)
instance.arc09 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.electrolyzer_4.power_in
)
instance.arc10 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.electrolyzer_5.power_in
)
instance.arc11 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.electrolyzer_6.power_in
)
instance.arc12 = Arc(
    source=instance.electrolyzer_1.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)
instance.arc13 = Arc(
    source=instance.electrolyzer_2.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)
instance.arc14 = Arc(
    source=instance.electrolyzer_3.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)
instance.arc15 = Arc(
    source=instance.electrolyzer_4.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)
instance.arc16 = Arc(
    source=instance.electrolyzer_5.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)
instance.arc17 = Arc(
    source=instance.electrolyzer_6.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)
# instance.arc07 = Arc(
#     source=instance.hydrogen_grid.hydrogen_out,
#     destination=instance.hydrogen_storage.hydrogen_in
# )
# instance.arc08 = Arc(
#     source=instance.hydrogen_storage.hydrogen_out,
#     destination=instance.hydrogen_grid.hydrogen_in
# )
instance.arc18 = Arc(
    source=instance.chp_1.natural_gas_in,
    destination=instance.ngas_grid.ngas_out
)
instance.arc19 = Arc(
    source=instance.chp_2.natural_gas_in,
    destination=instance.ngas_grid.ngas_out
)
instance.arc20 = Arc(
    source=instance.chp_1.hydrogen_in,
    destination=instance.hydrogen_grid.hydrogen_out
)
instance.arc21 = Arc(
    source=instance.chp_2.hydrogen_in,
    destination=instance.hydrogen_grid.hydrogen_out
)
instance.arc22 = Arc(
    source=instance.electrolyzer_1.heat_out,
    destination=instance.heatpump.heat_in
)
instance.arc23 = Arc(
    source=instance.electrolyzer_2.heat_out,
    destination=instance.heatpump.heat_in
)
instance.arc24 = Arc(
    source=instance.electrolyzer_3.heat_out,
    destination=instance.heatpump.heat_in
)
instance.arc25 = Arc(
    source=instance.electrolyzer_4.heat_out,
    destination=instance.heatpump.heat_in
)
instance.arc26 = Arc(
    source=instance.electrolyzer_5.heat_out,
    destination=instance.heatpump.heat_in
)
instance.arc27 = Arc(
    source=instance.electrolyzer_6.heat_out,
    destination=instance.heatpump.heat_in
)
instance.arc28 = Arc(
    source=instance.heatpump.heat_out,
    destination=instance.heat_grid.heat_in
)
instance.arc29 = Arc(
    source=instance.chp_1.heat_out,
    destination=instance.heat_grid.heat_in
)
instance.arc30 = Arc(
    source=instance.chp_2.heat_out,
    destination=instance.heat_grid.heat_in
)
instance.arc31 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.heatpump.power_in
)
instance.arc32 = Arc(
    source=instance.heat_storage.heat_out,
    destination=instance.heat_grid.heat_in
)
instance.arc33 = Arc(
    source=instance.heat_grid.heat_out,
    destination=instance.heat_storage.heat_in
)


# Expand arcs and generate connection constraints
TransformationFactory('network.expand_arcs').apply_to(instance)

print('START SOLVING...')

# Solve the optimization problem
results = opt.solve(
    instance,
    symbolic_solver_labels=True,
    tee=True,
    logfile=PATH_OUT + 'solver.log', 
    load_solutions=True,
    report_timing=True)


# Write Results
results.write()

df_variables = pd.DataFrame()
df_parameters = pd.DataFrame()
df_output = pd.DataFrame()

for parameter in instance.component_objects(Param, active=True):
    name = parameter.name
    if 'hydrogen_admixture_factor' in name:
        continue
    df_parameters[name] = [value(parameter[t]) for t in instance.t]

for variable in instance.component_objects(Var, active=True):
    name = variable.name
    if 'aux' in name:   # Filters auxiliary variables from the output data
        continue
    if 'splitfrac' in name:
        continue
    df_variables[name] = [value(variable[t]) for t in instance.t]

df_output = pd.concat([df_parameters, df_variables], axis=1)
df_output.index = instance.t
df_output.index.name = 't'
df_output.to_csv(PATH_OUT + 'output_time_series.csv')
