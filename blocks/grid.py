from pyomo.environ import *
from pyomo.network import *

class Grid:
    """Class for constructing grid asset objects."""

    def __init__(self, data=None) -> None:
        self.data = data

    
    def electrcial_grid_block_rule(self, block):
        """Rule for creating a electrical power grid block with default 
        components and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.overall_power = Var(t, domain=Reals)
        block.supply_power = Var(t, domain=NonNegativeReals)
        block.feedin_power = Var(t, domain=NonNegativeReals)

        block.power_in = Port()
        block.power_in.add(
            block.feedin_power,
            'power',
            Port.Extensive,
            include_splitfrac=False
            )
        block.power_out = Port()
        block.power_out.add(
            block.supply_power,
            'power',
            Port.Extensive,
            include_splitfrac=False
            )

        # Declare construction rules for constraints
        def max_supply_power_rule(_block, i):
            """Rule for the maximal supply power."""
            return _block.supply_power[i] <= self.data.loc['max', 'power']
        
        def max_feedin_power_rule(_block, i):
            """Rule for the maximal feed in power."""
            return _block.feedin_power[i] <= self.data.loc['max', 'power']
        
        def overall_power_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.overall_power[i] == _block.supply_power[i] - _block.feedin_power[i]
        
        # Define constraints
        block.max_supply_power_constraint = Constraint(
            t,
            rule=max_supply_power_rule
        )
        block.max_feedin_power_constraint = Constraint(
            t,
            rule=max_feedin_power_rule
        )
        block.overall_power_constraint = Constraint(
            t,
            rule=overall_power_rule
        )
    

    def hydrogen_grid_block_rule(self, block):
        """Rule for creating a hydrogen gas grid block with default components 
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.overall_hydrogen = Var(t, domain=Reals)
        block.supply_hydrogen = Var(t, domain=NonNegativeReals)
        block.feedin_hydrogen = Var(t, domain=NonNegativeReals)

        block.hydrogen_in = Port()
        block.hydrogen_in.add(
            block.feedin_hydrogen,
            'hydrogen',
            Port.Extensive,
            include_splitfrac=False
            )
        block.hydrogen_out = Port()
        block.hydrogen_out.add(
            block.supply_hydrogen,
            'hydrogen',
            Port.Extensive,
            include_splitfrac=False
            )

        # Declare construction rules for constraints
        def max_supply_hydrogen_rule(_block, i):
            """Rule for the maximal supply of hydrogen from the grid."""
            return _block.supply_hydrogen[i] <= self.data.loc['max', 'hydrogen']
        
        def max_feedin_hydrogen_rule(_block, i):
            """Rule for the maximal feed in of hydrogen into the grid."""
            return _block.feedin_hydrogen[i] <= self.data.loc['max', 'hydrogen']
        
        def overall_hydrogen_rule(_block, i):
            """Rule for calculating the overall hydrogen balance of the grid."""
            return _block.overall_hydrogen[i] == _block.supply_hydrogen[i] - _block.feedin_hydrogen[i]
          
        # Declare constraints
        block.max_supply_hydrogen_constraint = Constraint(
            t,
            rule=max_supply_hydrogen_rule
        )
        block.max_feedin_hydrogen_constraint = Constraint(
            t,
            rule=max_feedin_hydrogen_rule
        )
        block.overall_hydrogen_constraint = Constraint(
            t,
            rule=overall_hydrogen_rule
        )


    def natural_gas_grid_block_rule(self, block):
        """Rule for creating a natural gas grid block with default components 
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.overall_ngas = Var(t, domain=Reals)

        block.ngas_out = Port()
        block.ngas_out.add(
            block.overall_ngas,
            'natural_gas',
            Port.Extensive,
            include_splitfrac=False
            )
    

    def heat_grid_block_rule(self, block):

        # Get index from model
        t = block.model().t

        # Declare components
        block.overall_heat = Var(t, domain=Reals)
        block.supply_heat = Var(t, domain=NonNegativeReals)
        block.feedin_heat = Var(t, domain=NonNegativeReals)

        block.heat_in = Port()
        block.heat_in.add(
            block.feedin_heat,
            'heat',
            Port.Extensive,
            include_splitfrac=False
            )
        block.heat_out = Port()
        block.heat_out.add(
            block.supply_heat,
            'heat',
             Port.Extensive,
             include_splitfrac=False
            )
        
        # Define construction rules for constraints
        def overall_heat_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.overall_heat[i] == _block.supply_heat[i] - _block.feedin_heat[i]

        # Define constraints
        block.overall_power_constraint = Constraint(
            t,
            rule=overall_heat_rule
        )