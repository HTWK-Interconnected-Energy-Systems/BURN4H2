"""Provides functions for model construction"""

import pyomo.environ as pyo


def create_simple_mkq_model(data_dict):
    """
    Creates a mathematical model for optimization purposes.

    Parameters
    ----------
    data_dict : dict
        A dictionary with the model data.

    Returns
    -------
    model
        A mathematical model of the optimization problem.
    """

    # Initialize model
    model = pyo.ConcreteModel(name='least squares method')

    # Define set for the model
    model.I = pyo.Set(initialize=data_dict['I'])
    model.J = pyo.Set(initialize=data_dict['J'])

    # Define parameters for the model
    model.k = pyo.Param(model.I, model.J, initialize=data_dict['k'])
    # model.b = pyo.Param(model.J, initialize=test_data_dict['b'])

    # Define variables for the model
    model.x = pyo.Var(model.I, domain=pyo.Integers, bounds=(0, 20))

    def objective_rule(model):
        """
        Rule that defines the mathematical problem of the objective.

        Parameters
        ----------
        model: object
            A pyomo model object with the necessary attributes.

        """
        return sum(
            # [(sum([model.k[i, j] * model.x[i] for i in model.I]) - model.b[j])
            #  ** 2
            #  for j in model.J]
            [(sum([model.k[i, j] * model.x[i] for i in model.I]) - 1)
             # ** 2
             for j in model.J]
        )

    model.objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

    def constraint_rule(model, i):
        return model.x[i] >= 1

    model.constrains = pyo.Constraint(model.I, rule=constraint_rule)

    return model
