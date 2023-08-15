import os
import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import *


# Path
PATH_IN = 'data/input/'
PATH_OUT = 'data/output/'

# Scenario
# SCENARIO = 'UE23'
SCENARIO = 'testing'

# Year
YEAR = '2024'

# Select Solver
opt = SolverFactory('gurobi')

# Create DataPortal
data = DataPortal()

# Read Time Series
if SCENARIO == 'testing':
    data.load(
        filename=PATH_IN + SCENARIO + '/gas_price.csv',
        index='t',
        param='gas_price'
    )
    data.load(
        filename=PATH_IN + SCENARIO + '/power_price.csv',
        index='t',
        param='power_price'
    )
else:
    data.load(
        filename=PATH_IN + SCENARIO + '/gas_price_' + YEAR + '.csv',
        index='t',
        param='gas_price'
    )
    data.load(
        filename=PATH_IN + SCENARIO + '/power_price_' + YEAR + '.csv',
        index='t',
        param='power_price'
    )

# Read BHKW Performance Data
df_bhkw_hilde = pd.read_csv(
    PATH_IN + 'assets/BHKWHilde.csv',
    index_col=0
)

df_electricity_storage = pd.read_csv(
    PATH_IN + 'assets/Electricity_Storage.csv',
    index_col=0
)

# Define abstract model
m = AbstractModel()

# Define sets
m.t = Set(ordered=True)

# Define parameters
m.gas_price = Param(m.t)
m.power_price = Param(m.t)

# Define Binary Variables
m.bhkw_bin = Var(
    m.t,
    within=Binary,
    doc='BHKW_Online'
)
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
m.bhkw_gas = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Fuel Consumption'
)
m.bhkw_power = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Power Production'
)
m.bhkw_heat = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Heat Production'
)
m.net_power = Var(
    m.t,
    domain=NonNegativeReals,
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
m.bhkw_p_con_1 = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Power of the connection between bhkw and electricity storage'
)
m.bhkw_p_con_2 = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Power of the connection between bhkw and net'
)
m.storage_p_con_3 = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Discharging power of the connection between storage and net'
)
m.net_p_con_4 = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Charging power of the connection between net and storage'
)

# Define Constraints

def bhkw_power_max(m, t):
    """ BHKW Power Max Constraint """
    return m.bhkw_power[t] <= df_bhkw_hilde.loc['Max', 'Power'] * m.bhkw_bin[t]


m.bhkw_power_max_constraint = Constraint(
    m.t,
    rule=bhkw_power_max
    )


def bhkw_power_min(m, t):
    """ BHKW Power Min Constraint """
    return df_bhkw_hilde.loc['Min', 'Power'] * m.bhkw_bin[t] <= m.bhkw_power[t]


m.bhkw_power_min_constraint = Constraint(
    m.t,
    rule=bhkw_power_min
    )


def bhkw_gas_depends_on_power(m, t):
    """ BHKW Gas = a * Power + b Constraint """
    value_gas_max = df_bhkw_hilde.loc['Max', 'Gas']
    value_gas_min = df_bhkw_hilde.loc['Min', 'Gas']
    value_power_max = df_bhkw_hilde.loc['Max', 'Power']
    value_power_min = df_bhkw_hilde.loc['Min', 'Power']

    a = (value_gas_max - value_gas_min) / (value_power_max - value_power_min)
    b = value_gas_max - a * value_power_max

    return m.bhkw_gas[t] == a * m.bhkw_power[t] + b * m.bhkw_bin[t]


m.bhkw_gas_depends_on_power_constraint = Constraint(
    m.t,
    rule=bhkw_gas_depends_on_power
    )


def bhkw_heat_depends_on_power(m, t):
    """ BHKW Heat = a * Power + b Constraint """
    value_heat_max = df_bhkw_hilde.loc['Max', 'Heat']
    value_heat_min = df_bhkw_hilde.loc['Min', 'Heat']
    value_power_max = df_bhkw_hilde.loc['Max', 'Power']
    value_power_min = df_bhkw_hilde.loc['Min', 'Power']

    a = (value_heat_max - value_heat_min) / (value_power_max - value_power_min)
    b = value_heat_max - a * value_power_max

    return m.bhkw_heat[t] == a * m.bhkw_power[t] + b * m.bhkw_bin[t]


m.bhkw_heat_depends_on_power_constraint = Constraint(
    m.t,
    rule=bhkw_heat_depends_on_power
    )


def bhkw_operating_hours(m, t):
    """ BHKW Minimal amount of operating hours Constraint """

    return quicksum(m.bhkw_bin[t] for t in m.t) >= 10


m.bhkw_operating_hours_constraint = Constraint(
    m.t,
    rule=bhkw_operating_hours
    )


def bhkw_connections(m,t):
    """ BHKW power distribution constraint """

    # return m.bhkw_power[t] == (m.p_con_1[t] + m.p_con_2[t]) * m.bhkw_bin[t]
    return m.bhkw_power[t] == m.bhkw_p_con_1[t] + m.bhkw_p_con_2[t]


m.bhkw_connections_constraint = Constraint(
    m.t,
    rule=bhkw_connections
)


def net_overall_power(m, t):
    """ Electrical network overall power constraint """
    feed_in = (m.bhkw_p_con_2[t] + m.storage_p_con_3[t]) * m.net_feeding_bin[t]
    supplying = m.net_p_con_4[t] * m.net_supplying_bin[t]

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
    return m.storage_p_con_3[t] <= value_discharge_power_max * m.storage_discharge_bin[t]


m.storage_discharging_power_max_constraint = Constraint(
    m.t,
    rule=storage_discharging_power_max
)


def storage_charging_power_max(m, t):
    """ Storage charging power max constraint """
    value_charging_power_max = df_electricity_storage.loc['Max', 'Power']

    # return m.storage_power[t] >= value_charging_power_max * m.storage_charge_bin[t]
    return -(m.bhkw_p_con_1[t] + m.net_p_con_4[t]) >= value_charging_power_max * m.storage_charge_bin[t]


m.storage_charging_power_max_constraint = Constraint(
    m.t,
    rule=storage_charging_power_max
)


def storage_overall_power(m, t):
    """ Storage overall power constraint """
    # charge = (m.p_con_1[t] + m.p_con_4[t]) * m.storage_charge_bin[t]
    charge = m.bhkw_p_con_1[t] + m.net_p_con_4[t]
    # discharge = m.p_con_3[t] * m.storage_discharge_bin[t]
    discharge = m.storage_p_con_3[t]

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
    return (quicksum(m.bhkw_gas[t] * m.gas_price[t] for t in m.t) -
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
    load_solutions=True)

# Write Results
results.write()

""" Write Output Time Series """
df_output = pd.DataFrame()

if SCENARIO == 'testing':
    path_output = PATH_OUT + SCENARIO + '/'
else:
    path_output = PATH_OUT + SCENARIO + '/' + YEAR + '/'

if not os.path.exists(path_output):
    os.makedirs(path_output)

for t in instance.t.data():
    df_output.loc[t, 'power_price'] = instance.power_price[t]
    df_output.loc[t, 'gas_price'] = instance.gas_price[t]

    for variable in m.component_objects(Var, active=True):
        name = variable.name
        df_output.loc[t, name] = instance.__getattribute__(name)[t].value
        
df_output.to_csv(path_output + 'output_time_series.csv')

# Write results
df_results = pd.DataFrame()
df_results['objective_value'] = pd.Series(value(instance.obj))

df_results.to_csv(path_output + 'results.csv')