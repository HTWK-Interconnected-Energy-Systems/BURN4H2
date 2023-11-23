import os
import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import *

import blocks.chp as chp
import blocks.grid as grid
import blocks.storage as storage


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


# Create instance
chp_obj = chp.Chp(chp_data, forced_operation_time=24)
electrical_grid_obj = grid.Grid(electrical_grid_data)
battery_storage_obj = storage.BatteryStorage(battery_storage_data)

# Define abstract model
m = AbstractModel()

# Define sets
m.t = Set(ordered=True)

# Define parameters
m.gas_price = Param(m.t)
m.power_price = Param(m.t)


# Define Continuous Variable
m.bhkw_con_1_power = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Power of the connection between bhkw and electricity storage'
)
m.bhkw_con_2_power = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Power of the connection between bhkw and net'
)
m.storage_con_3_power = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Discharging power of the connection between storage and net'
)
m.net_con_4_power = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Charging power of the connection between net and storage'
)

# Define block components
m.chp = Block(rule=chp_obj.chp_block_rule)
m.electrical_grid = Block(rule=electrical_grid_obj.electrcial_grid_block_rule)
m.battery_storage = Block(rule=battery_storage_obj.battery_storage_construction_rule)


# Define Constraints
def bhkw_connections(m,t):
    """ BHKW power distribution constraint """

    # return m.bhkw_power[t] == (m.p_con_1[t] + m.p_con_2[t]) * m.bhkw_bin[t]
    return m.chp.power[t] == m.bhkw_con_1_power[t] + m.bhkw_con_2_power[t]


m.bhkw_connections_constraint = Constraint(
    m.t,
    rule=bhkw_connections
)

def net_feed_in_power_max(m, t):
    """ Electrical network max feed in power constraint """
    return m.bhkw_con_2_power[t] + m.storage_con_3_power[t] <= m.electrical_grid.max_power[t] * m.electrical_grid.feedin_bin[t]


m.net_feed_in_power_max_constraint = Constraint(
    m.t,
    rule=net_feed_in_power_max
)


def net_supply_max_power(m, t):
    """ Electrical network max supply power constraint """
    return m.net_con_4_power[t] <= m.electrical_grid.max_power[t] * m.electrical_grid.supply_bin[t]


m.net_supply_max_power_constraint = Constraint(
    m.t,
    rule=net_supply_max_power
)


def net_overall_power(m, t):
    """ Electrical network overall power constraint """
    feed_in = m.bhkw_con_2_power[t] + m.storage_con_3_power[t]
    supplying = m.net_con_4_power[t]

    return m.electrical_grid.power[t] == feed_in - supplying


m.net_power_constraint = Constraint(
    m.t,
    rule=net_overall_power
    )


def storage_discharging_power_max(m, t):
    """ Storage discharging power max constraint """
    return m.storage_con_3_power[t] <= (
        m.battery_storage.max_discharge_power[t] * m.battery_storage.discharge_bin[t]
    )


m.storage_discharging_power_max_constraint = Constraint(
    m.t,
    rule=storage_discharging_power_max
)


def storage_charging_power_max(m, t):
    """ Storage charging power max constraint """
    return -(m.bhkw_con_1_power[t] + m.net_con_4_power[t]) >= (
        m.battery_storage.max_charge_power[t] * m.battery_storage.charge_bin[t]
    )


m.storage_charging_power_max_constraint = Constraint(
    m.t,
    rule=storage_charging_power_max
)


def storage_overall_power(m, t):
    """ Storage overall power constraint """
    charge = m.bhkw_con_1_power[t] + m.net_con_4_power[t]
    discharge = m.storage_con_3_power[t]

    return m.battery_storage.overall_power[t] == discharge - charge 


m.storage_power_constraint = Constraint(
    m.t,
    rule=storage_overall_power
)


# Define Objective
def obj_expression(m):
    """ Objective Function """
    return (quicksum(m.chp.gas[t] * m.gas_price[t] for t in m.t) -
            quicksum(m.electrical_grid.power[t] * m.power_price[t] for t in m.t))


m.obj = Objective(
    rule=obj_expression,
    sense=minimize
    )

# Create instanz
instance = m.create_instance(data)

# Solve the optimization problem
results = opt.solve(
    instance,
    symbolic_solver_labels=True,
    tee=True,
    logfile=PATH_OUT + 'solver.log', 
    load_solutions=True)

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
    df_variables[name] = [value(variable[t]) for t in instance.t]

df_output = pd.concat([df_parameters, df_variables], axis=1)
df_output.to_csv(PATH_OUT + 'output_time_series.csv')
