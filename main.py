import os
import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import *

import blocks.chp as chp


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

# Get performance parameters for the chp
chp_data = pd.read_csv(
    PATH_IN + 'assets/chp.csv',
    index_col=0
)

# Read BHKW Performance Data
df_electricity_storage = pd.read_csv(
    PATH_IN + 'assets/Electricity_Storage.csv',
    index_col=0
)

df_electrical_net = pd.read_csv(
    PATH_IN + 'assets/electrical_net.csv',
    index_col=0
)

# Create chp instance
chp_obj = chp.Chp(chp_data, forced_operation_time=24)

# Define abstract model
m = AbstractModel()

# Define sets
m.t = Set(ordered=True)

# Define parameters
m.gas_price = Param(m.t)
m.power_price = Param(m.t)

# Define Binary Variables
m.storage_charge_bin = Var(
    m.t,
    within=Binary,
    doc='storage charging'
)
m.storage_discharge_bin = Var(
    m.t,
    within=Binary,
    doc='storage discharging'
)
m.net_feeding_bin = Var(
    m.t,
    within=Binary,
    doc='net feeding'
)
m.net_supplying_bin = Var(
    m.t,
    within=Binary,
    doc='net supplying'
)

# Define Continuous Variable
m.net_power = Var(
    m.t,
    domain=Reals,
    doc='Plant Supply Power'
)
m.storage_power = Var(
    m.t,
    domain=Reals,
    doc='Storage Charge/Discharge Power'
)
m.storage_energy = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Storage Actual Energy'
)
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
    feed_in_power_max = df_electrical_net.loc['Max', 'Power_feed_in']

    return m.bhkw_con_2_power[t] + m.storage_con_3_power[t] <= feed_in_power_max * m.net_feeding_bin[t]


m.net_feed_in_power_max_constraint = Constraint(
    m.t,
    rule=net_feed_in_power_max
)


def net_supply_max_power(m, t):
    """ Electrical network max supply power constraint """
    supply_power_max = df_electrical_net.loc['Max', 'Power_supply']

    return m.net_con_4_power[t] <= supply_power_max * m.net_supplying_bin[t]


m.net_supply_max_power_constraint = Constraint(
    m.t,
    rule=net_supply_max_power
)


def net_overall_power(m, t):
    """ Electrical network overall power constraint """
    feed_in = m.bhkw_con_2_power[t] + m.storage_con_3_power[t]
    supplying = m.net_con_4_power[t]

    return m.net_power[t] == feed_in - supplying


m.net_power_constraint = Constraint(
    m.t,
    rule=net_overall_power
    )


def net_binary(m, t):
    """ Net binary constraint """
    
    return m.net_feeding_bin[t] + m.net_supplying_bin[t] <= 1


m.net_binary_constraint = Constraint(
    m.t,
    rule=net_binary
)


def storage_discharging_power_max(m, t):
    """ Storage discharging power max constraint """
    value_discharge_power_max = df_electricity_storage.loc['Min', 'Power']

    # return m.storage_power[t] <= value_discharge_power_max * m.storage_discharge_bin[t]
    return m.storage_con_3_power[t] <= value_discharge_power_max * m.storage_discharge_bin[t]


m.storage_discharging_power_max_constraint = Constraint(
    m.t,
    rule=storage_discharging_power_max
)


def storage_charging_power_max(m, t):
    """ Storage charging power max constraint """
    value_charging_power_max = df_electricity_storage.loc['Max', 'Power']

    # return m.storage_power[t] >= value_charging_power_max * m.storage_charge_bin[t]
    return -(m.bhkw_con_1_power[t] + m.net_con_4_power[t]) >= value_charging_power_max * m.storage_charge_bin[t]


m.storage_charging_power_max_constraint = Constraint(
    m.t,
    rule=storage_charging_power_max
)


def storage_overall_power(m, t):
    """ Storage overall power constraint """
    # charge = (m.p_con_1[t] + m.p_con_4[t]) * m.storage_charge_bin[t]
    charge = m.bhkw_con_1_power[t] + m.net_con_4_power[t]
    # discharge = m.p_con_3[t] * m.storage_discharge_bin[t]
    discharge = m.storage_con_3_power[t]

    return m.storage_power[t] == discharge - charge 


m.storage_power_constraint = Constraint(
    m.t,
    rule=storage_overall_power
)


def storage_binary(m, t):
    """ Storage binary constraint """

    return m.storage_charge_bin[t] + m.storage_discharge_bin[t] <= 1


m.storage_bin_constraint = Constraint(
    m.t,
    rule=storage_binary
)


def storage_energy_min(m, t):
    """ Storage Energy Min Constraint. """
    value_energy_min = df_electricity_storage.loc['Min', 'Capacity']

    return m.storage_energy[t] >= value_energy_min


m.storage_energy_min_constraint = Constraint(
    m.t,
    rule=storage_energy_min
)


def storage_energy_max(m, t):
    """ Storage Energy Max Constraint. """
    value_energy_max = df_electricity_storage.loc['Max', 'Capacity']

    return m.storage_energy[t] <= value_energy_max


m.storage_energy_max_constraint = Constraint(
    m.t,
    rule=storage_energy_max
)


def storage_energy_actual(m, t):
    """ Storage Energy Actual Constraint. """
    if t == 1:
        return m.storage_energy[t] == 0 - m.storage_power[t]
    else:
        return m.storage_energy[t] == m.storage_energy[t - 1] - m.storage_power[t]


m.storage_energy_actual_constraint = Constraint(
    m.t,
    rule=storage_energy_actual
)


# Define Objective
def obj_expression(m):
    """ Objective Function """
    return (quicksum(m.chp.gas[t] * m.gas_price[t] for t in m.t) -
            quicksum(m.net_power[t] * m.power_price[t] for t in m.t))


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

""" Write Output Time Series """
df_output = pd.DataFrame()

if not os.path.exists(PATH_OUT):
    os.makedirs(PATH_OUT)

for t in instance.t.data():
    df_output.loc[t, 'power_price'] = instance.power_price[t]
    df_output.loc[t, 'gas_price'] = instance.gas_price[t]

    for variable in m.component_objects(Var, active=True):
        name = variable.name
        df_output.loc[t, name] = instance.__getattribute__(name)[t].value
        
df_output.to_csv(PATH_OUT + 'output_time_series.csv')

# Write results
df_results = pd.DataFrame()
df_results['objective_value'] = pd.Series(value(instance.obj))

df_results.to_csv(PATH_OUT + 'results.csv')