import pandas as pd

from pyomo.opt import SolverFactory
from pyomo.environ import *


# Path
path_in = 'data/input/'
path_out = 'data/output/'

# Select Solver
opt = SolverFactory('gurobi')

# Create DataPortal
data = DataPortal()

# Read Time Series
data.load(
    filename=path_in + 'Gas_Price.csv',
    index='t',
    param='gas_price'
)
data.load(
    filename=path_in + 'Power_Price.csv',
    index='t',
    param='power_price'
)

# Read BHKW Performance Data
df_bhkw_hilde = pd.read_csv(
    path_in + 'BHKWHilde.csv',
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
    doc='Online'
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


def power_max(m, t):
    """ Power Max Constraint """
    return m.bhkw_power[t] <= df_bhkw_hilde.loc['Max', 'Power'] * m.bhkw_bin[t]


m.power_max_constraint = Constraint(m.t, rule=power_max)


def power_min(m, t):
    """ Power Min Constraint """
    return df_bhkw_hilde.loc['Min', 'Power'] * m.bhkw_bin[t] <= m.bhkw_power[t]


m.power_min_constraint = Constraint(m.t, rule=power_min)


def gas_depends_on_power(m, t):
    """ Gas = a * Power + b Constraint """
    value_gas_max = df_bhkw_hilde.loc['Max', 'Gas']
    value_gas_min = df_bhkw_hilde.loc['Min', 'Gas']
    value_power_max = df_bhkw_hilde.loc['Max', 'Power']
    value_power_min = df_bhkw_hilde.loc['Min', 'Power']

    a = (value_gas_max - value_gas_min) / (value_power_max - value_power_min)
    b = value_gas_max - a * value_power_max

    return m.bhkw_gas[t] == a * m.bhkw_power[t] + b * m.bhkw_bin[t]


m.gas_depends_on_power_constraint = Constraint(m.t, rule=gas_depends_on_power)


def heat_depends_on_power(m, t):
    """ Heat = a * Power + b Constraint """
    value_heat_max = df_bhkw_hilde.loc['Max', 'Heat']
    value_heat_min = df_bhkw_hilde.loc['Min', 'Heat']
    value_power_max = df_bhkw_hilde.loc['Max', 'Power']
    value_power_min = df_bhkw_hilde.loc['Min', 'Power']

    a = (value_heat_max - value_heat_min) / (value_power_max - value_power_min)
    b = value_heat_max - a * value_power_max

    return m.bhkw_heat[t] == a * m.bhkw_power[t] + b * m.bhkw_bin[t]


m.heat_depends_on_power_constraint = Constraint(m.t, rule=heat_depends_on_power)


def operating_hours(m, t):
    """ Minimal amount of operating hours Constraint """

    return quicksum(m.bhkw_bin[t] for t in m.t) >= 10


m.operating_hours_constraint = Constraint(m.t, rule=operating_hours)


def obj_expression(m):
    """ Objective Function """
    return (quicksum(m.bhkw_gas[t] * m.gas_price[t] for t in m.t) -
            quicksum(m.bhkw_power[t] * m.power_price[t] for t in m.t))


m.obj = Objective(rule=obj_expression, sense=minimize)

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

for t in instance.t.data():
    df_output.loc[t, 'power_price'] = instance.power_price[t]
    df_output.loc[t, 'gas_price'] = instance.gas_price[t]

    for variable in m.component_objects(Var, active=True):
        name = variable.name
        df_output.loc[t, name] = instance.__getattribute__(name)[t].value
        
df_output.to_csv(path_out + 'Output_TimeSeries.csv')
