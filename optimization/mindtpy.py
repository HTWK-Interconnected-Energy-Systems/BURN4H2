from pyomo.environ import *
from data.data import pv_installation_data_dict, test_data_dict

model = ConcreteModel(name='least squares method')

# data_dict = pv_installation_data_dict
data_dict = pv_installation_data_dict
print('Data was initialized successfully.')

# Define set for the model
model.I = Set(initialize=data_dict['I'])
model.J = Set(initialize=data_dict['J'])

# Define parameters for the model
model.k = Param(model.I, model.J, initialize=data_dict['k'])
# model.b = pyo.Param(model.J, initialize=test_data_dict['b'])

# Define variables for the model
model.x = Var(model.I, domain=Integers, bounds=(0, 3000), initialize=0)

model.objective = Objective(
    expr=sum(
        [(sum([model.k[i, j] * model.x[i] for i in model.I]) - 1000) ** 2
         for j in model.J]),
    sense=minimize)


def constraint_rule(model, i):
    temp = value(model.x[i]) - int(value(model.x[i]) / 1000) * 1000
    if temp == 0:
        return Constraint.Feasible
    return Constraint.Skip


model.constrains = Constraint(model.I, rule=constraint_rule)

print('Model was created successfully.')


# solver = SolverFactory('ipopt')
# solver = SolverFactory('cbc')
# solver = SolverFactory('glpk')
# solver = SolverFactory('mindtpy')
solver = SolverFactory('scip')

results = solver.solve(model)

model.display()
