"""Main script for solving models."""

import pyomo.environ as pyo
from model import create_simple_mkq_model
from data.data import pv_installation_data_dict, test_data_dict

model = create_simple_mkq_model(test_data_dict)
print('Model created successfully')

# solver = pyo.SolverFactory('ipopt')
# solver = pyo.SolverFactory('cbc')
# solver = pyo.SolverFactory('glpk')
solver = pyo.SolverFactory('mindtpy')
results = solver.solve(model)

model.display()
