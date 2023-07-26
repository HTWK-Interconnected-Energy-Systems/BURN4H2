"""Script for calculating the optimal operation of a cgu."""

from pyomo.environ import *

ENERGY_PRICE_GAS = 0.1543  # €/kWh for net calorific value
CONVERSION_FACTOR = 1.11  # net calorific value to gross calorific value
HEAT_PRICE = 0.105  # €/kWh
CONSUMPTION_SHARE = 0.03  # relative value for electrical in-house consumption
CHP_INDEX = 0.1158  # €/kWh of the provided electricity


def calc_thermal_efficiency(thermal_power: int):
    """
    Calculates the thermal efficiency of a cgu.

    Parameters
    ----------
    thermal_power: int
        Thermal power of the cgu in Watt.

    Returns
    -------
    thermal_efficiency: float
        The thermal efficiency of the cgu at a given thermal power.
    """

    eta_thermal = (8.687E-9 * thermal_power ** 2 +
                   -1.465E-3 * thermal_power +
                   117.5) / 100

    return eta_thermal


def calc_electric_efficiency(thermal_power: int):
    """
    Calculates the electrical efficiency of a cgu based on the heat output as
    function of the thermal_power.

    Parameters
    ----------
    thermal_power: int
        Thermal power of the cgu in Watt.

    Returns
    -------
    electrical_efficiency: float
        The electrical efficiency of a cgu at a given thermal power.
    """

    eta_electrical = (-8.473E-9 * thermal_power ** 2 +
                      1.438E-3 * thermal_power +
                      -26.78) / 100

    return eta_electrical


def calc_gas_costs(thermal_power: int):
    """
    Calculates the costs of the natural gas purchase.

    Parameters
    ----------
    thermal_power: int
        Thermal power of a heat source in Watt.

    Returns
    -------
    costs_gas: float
        The costs of the gas purchase.
    """

    costs = (thermal_power / 1000 / calc_thermal_efficiency(thermal_power) *
             CONVERSION_FACTOR *
             ENERGY_PRICE_GAS)

    return costs


def calc_heat_revenue(thermal_power: int):
    """
    Calculates the revenue of the provided heat.

    Parameters
    ----------
    thermal_power: int
     Thermal power of a heat source in Watt.

    Returns
    -------
    heat_revenue: float
        The revenue for the provided heat.
    """

    revenue = thermal_power / 1000 * HEAT_PRICE

    return revenue


def calc_chp_index_revenue(thermal_power: int):
    """
    Calculates the revenue of the provided electricity according to the
    chp-index.

    Parameters
    ----------
    thermal_power: int
        Thermal power of a chp heat source in Watt.

    Returns
    -------
    electricity_revenue: float
        The revenue for the provided electricity
    """

    electricity_output = (thermal_power / 1000 /
                          calc_thermal_efficiency(thermal_power) *
                          calc_electric_efficiency(thermal_power)
                          )

    revenue = (electricity_output * (1 - CONSUMPTION_SHARE) * CHP_INDEX)

    return revenue


model = ConcreteModel(name='cgu')

# Define model parameters
model.q_demand = Param(initialize=70000)


# Define model variables
model.q = Var(bounds=(58000, 89000), domain=Integers)

# Define model objective
model.objective = Objective(
    expr=(calc_heat_revenue(model.q) +
          calc_chp_index_revenue(model.q) -
          calc_gas_costs(model.q)
          ),
    sense=maximize
)

# Define model constraints
model.c1 = Constraint(expr=model.q_demand * 0.9 <= model.q)
model.c2 = Constraint(expr=model.q <= model.q_demand * 1.1)

solver = SolverFactory('ipopt')

results = solver.solve(model)

model.display()

print('This is Martins')
