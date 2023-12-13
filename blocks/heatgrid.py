from pyomo.environ import *
from pyomo.network import *


class Heatgrid:
    """Class for constructing grid asset objects."""

    def __init__(self, data) -> None:
        self.data = data

    def heat_grid_block_rule(self, block):
        """Rule for creating a electrical power grid block with default components and
        constraints."""
        # Get index from model
        t = block.model().t

        # Define components
        block.overall_heat = Var(t, domain=Reals)
        block.supply_heat = Var(t, domain=NonNegativeReals)
        block.feedin_heat = Var(t, domain=NonNegativeReals)

        block.heat_in = Port()
        block.heat_in.add(block.feedin_heat, 'heat', Port.Extensive, include_splitfrac=False)
        block.heat_out = Port()
        block.heat_out.add(block.supply_heat, 'heat', Port.Extensive, include_splitfrac=False)

        # Define construction rules for constraints
        def overall_heat_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.overall_heat[i] == _block.supply_heat[i] - _block.feedin_heat[i]

        # Define constraints
        block.overall_power_constraint = Constraint(
            t,
            rule=overall_heat_rule
        )

