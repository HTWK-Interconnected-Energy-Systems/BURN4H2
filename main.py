import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import *
from pyomo.network import *

import blocks.chp as chp
import blocks.grid as grid
import blocks.storage as storage
import blocks.res as res
import blocks.electrolyzer as elec


# Path
PATH_IN = 'data/input/'
PATH_OUT = 'data/output/'


# Select Solver
opt = SolverFactory('gurobi')


# Create DataPortal
data = DataPortal()


# Read Time Series
data.load(
    filename=PATH_IN + 'prices/dummy/gas_price.csv',
    index='t',
    param='gas_price'
)
data.load(
    filename=PATH_IN + 'prices/dummy/power_price.csv',
    index='t',
    param='power_price'
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
hydrogen_storage_data = pd.read_csv(
    PATH_IN + 'assets/hydrogen_storage.csv',
    index_col=0
)


# Create instance
chp_obj = chp.Chp(chp_data)
electrical_grid_obj = grid.Grid(electrical_grid_data)
battery_storage_obj = storage.BatteryStorage(battery_storage_data)
pv_obj = res.Photovoltaics(pv_data, pv_capacity_factors)
electrolyzer_obj = elec.Electrolyzer(electrolyzer_data)
hydrogen_grid_obj = grid.Grid(hydrogen_grid_data)
hydrogen_storage_obj = storage.HydrogenStorage(hydrogen_storage_data)


# Define abstract model
m = AbstractModel()


# Define sets
m.t = Set(ordered=True)


# Define parameters
m.gas_price = Param(m.t)
m.power_price = Param(m.t)


# Define block components
m.chp = Block(rule=chp_obj.chp_block_rule)
m.electrical_grid = Block(rule=electrical_grid_obj.electrcial_grid_block_rule)
m.battery_storage = Block(rule=battery_storage_obj.battery_storage_block_rule)
m.pv = Block(rule=pv_obj.pv_block_rule)
m.electrolyzer = Block(rule=electrolyzer_obj.electrolyzer_block_rule)
m.hydrogen_grid = Block(rule=hydrogen_grid_obj.hydrogen_grid_block_rule)
m.hydrogen_storage = Block(rule=hydrogen_storage_obj.hydrogen_storage_block_rule)


# Define Objective
def obj_expression(m):
    """ Objective Function """
    return (quicksum(m.chp.gas[t] * m.gas_price[t] for t in m.t) +
            quicksum(m.electrical_grid.overall_power[t] * m.power_price[t] for t in m.t) +
            quicksum(m.hydrogen_grid.overall_hydrogen[t] * m.gas_price[t] * 2.5 for t in m.t))


m.obj = Objective(
    rule=obj_expression,
    sense=minimize
    )


# Create instance
instance = m.create_instance(data)


# Define arcs
instance.arc1 = Arc(
    source=instance.chp.power_out,
    destination=instance.electrical_grid.power_in
)
instance.arc2 = Arc(
    source=instance.pv.power_out,
    destination=instance.electrical_grid.power_in
)
instance.arc3 = Arc(
    source=instance.battery_storage.power_out,
    destination=instance.electrical_grid.power_in
)
instance.arc4 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.battery_storage.power_in
)
instance.arc5 = Arc(
    source=instance.electrical_grid.power_out,
    destination=instance.electrolyzer.power_in
)
instance.arc6 = Arc(
    source=instance.electrolyzer.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)
instance.arc7 = Arc(
    source=instance.hydrogen_grid.hydrogen_out,
    destination=instance.hydrogen_storage.hydrogen_in
)
instance.arc8 = Arc(
    source=instance.hydrogen_storage.hydrogen_out,
    destination=instance.hydrogen_grid.hydrogen_in
)


# Expand arcs and generate connection constraints
TransformationFactory('network.expand_arcs').apply_to(instance)


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
    df_parameters[name] = [value(parameter[t]) for t in instance.t]

for variable in instance.component_objects(Var, active=True):
    name = variable.name
    if 'aux' in name:   # Filters auxiliary variables from the output data
        continue
    df_variables[name] = [value(variable[t]) for t in instance.t]

df_output = pd.concat([df_parameters, df_variables], axis=1)
df_output.index = instance.t
df_output.index.name = 't'
df_output.to_csv(PATH_OUT + 'output_time_series.csv')
