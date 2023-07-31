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
    param='Gas_Price'
)
data.load(
    filename=path_in + 'Power_Price.csv',
    index='t',
    param='Power_Price'
)

# Read BHKW Performance Data
df_BHKWHilde = pd.read_csv(
    path_in + 'BHKWHilde.csv',
    index_col=0
)

# Define abstract model
m = AbstractModel()

# Define sets
m.t = Set(ordered=True)

# Define parameters
m.Gas_Price = Param(m.t)
m.Power_Price = Param(m.t)

# Define Binary Variables
m.BHKW_Bin = Var(
    m.t,
    within=Binary,
    doc='Online'
)

# Define Continuous Variable
m.BHKW_Gas = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Fuel Consumption'
)
m.BHKW_Power = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Power Production'
)
m.BHKW_Heat = Var(
    m.t,
    domain=NonNegativeReals,
    doc='Heat Production'
)


def PowerMax(m, t):
    """ Power Max Constraint """
    return m.BHKW_Power[t] <= df_BHKWHilde.loc['Max', 'Power'] * m.BHKW_Bin[t]


m.PowerMax_Constraint = Constraint(m.t, rule=PowerMax)


def PowerMin(m, t):
    """ Power Min Constraint """
    return df_BHKWHilde.loc['Min', 'Power'] * m.BHKW_Bin[t] <= m.BHKW_Power[t]


m.PowerMin_Constraint = Constraint(m.t, rule=PowerMin)


def GasDependsOnPower(m, t):
    """ Gas = a * Power + b Constraint """
    value_GasMax = df_BHKWHilde.loc['Max', 'Gas']
    value_GasMin = df_BHKWHilde.loc['Min', 'Gas']
    value_PowerMax = df_BHKWHilde.loc['Max', 'Power']
    value_PowerMin = df_BHKWHilde.loc['Min', 'Power']

    a = (value_GasMax - value_GasMin) / (value_PowerMax - value_PowerMin)
    b = value_GasMax - a * value_PowerMax

    return m.BHKW_Gas[t] == a * m.BHKW_Power[t] + b * m.BHKW_Bin[t]


m.GasDependsOnPower_Constraint = Constraint(m.t, rule=GasDependsOnPower)


def HeatDependsOnPower(m, t):
    """ Heat = a * Power + b Constraint """
    value_HeatMax = df_BHKWHilde.loc['Max', 'Heat']
    value_HeatMin = df_BHKWHilde.loc['Min', 'Heat']
    value_PowerMax = df_BHKWHilde.loc['Max', 'Power']
    value_PowerMin = df_BHKWHilde.loc['Min', 'Power']

    a = (value_HeatMax - value_HeatMin) / (value_PowerMax - value_PowerMin)
    b = value_HeatMax - a * value_PowerMax

    return m.BHKW_Heat[t] == a * m.BHKW_Power[t] + b * m.BHKW_Bin[t]


m.HeatDependsOnPower_Constraint = Constraint(m.t, rule=HeatDependsOnPower)


def operating_hours(m, t):
    """ Minimal amount of operating hours Constraint """

    return quicksum(m.BHKW_Bin[t] for t in m.t) >= 10


m.operating_hours_constraint = Constraint(m.t, rule=operating_hours)


def obj_expression(m):
    """ Objective Function """
    return (quicksum(m.BHKW_Gas[t] * m.Gas_Price[t] for t in m.t) -
            quicksum(m.BHKW_Power[t] * m.Power_Price[t] for t in m.t))


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
    df_output.loc[t, 'Power_Price'] = instance.Power_Price[t]
    df_output.loc[t, 'Gas_Price'] = instance.Gas_Price[t]

    for variable in m.component_objects(Var, active=True):
        name = variable.name
        df_output.loc[t, name] = instance.__getattribute__(name)[t].value
df_output.to_csv(path_out + 'Output_TimeSeries.csv')
