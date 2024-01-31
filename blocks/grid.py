from pyomo.environ import *
from pyomo.network import *

class Grid:
    """Class for constructing grid asset objects."""

    def __init__(self, data=None) -> None:
        self.data = data

    
    def electrical_grid_block_rule(self, block):
        """Rule for creating a electrical power grid block with default 
        components and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.power_balance = Var(t, domain=Reals)
        block.power_supply = Var(t, domain=NonNegativeReals)
        block.power_feedin = Var(t, domain=NonNegativeReals)

        block.power_in = Port()
        block.power_in.add(
            block.power_feedin,
            'power',
            Port.Extensive,
            include_splitfrac=False
            )
        block.power_out = Port()
        block.power_out.add(
            block.power_supply,
            'power',
            Port.Extensive,
            include_splitfrac=False
            )

        # Declare construction rules for constraints
        def max_power_supply_rule(_block, i):
            """Rule for the maximal supply power."""
            return _block.power_supply[i] <= self.data.loc['max', 'power']
        
        def max_power_feedin_rule(_block, i):
            """Rule for the maximal feed in power."""
            return _block.power_feedin[i] <= self.data.loc['max', 'power']
        
        def power_balance_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.power_balance[i] == _block.power_supply[i] - _block.power_feedin[i]
        
        # Define constraints
        block.max_power_supply_constraint = Constraint(
            t,
            rule=max_power_supply_rule
        )
        block.max_power_feedin_constraint = Constraint(
            t,
            rule=max_power_feedin_rule
        )
        block.power_balance_constraint = Constraint(
            t,
            rule=power_balance_rule
        )
    

    def hydrogen_grid_block_rule(self, block):
        """Rule for creating a hydrogen gas grid block with default components 
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.hydrogen_balance = Var(t, domain=Reals)
        block.hydrogen_supply = Var(t, domain=NonNegativeReals)
        block.hydrogen_feedin = Var(t, domain=NonNegativeReals)

        block.hydrogen_in = Port()
        block.hydrogen_in.add(
            block.hydrogen_feedin,
            'hydrogen',
            Port.Extensive,
            include_splitfrac=False
            )
        block.hydrogen_out = Port()
        block.hydrogen_out.add(
            block.hydrogen_supply,
            'hydrogen',
            Port.Extensive,
            include_splitfrac=False
            )

        # Declare construction rules for constraints
        def max_hydrogen_supply_rule(_block, i):
            """Rule for the maximal supply of hydrogen from the grid."""
            return _block.hydrogen_supply[i] <= self.data.loc['max', 'hydrogen']
        
        def max_hydrogen_feedin_rule(_block, i):
            """Rule for the maximal feed in of hydrogen into the grid."""
            return _block.hydrogen_feedin[i] <= self.data.loc['max', 'hydrogen']
        
        def hydrogen_balance_rule(_block, i):
            """Rule for calculating the overall hydrogen balance of the grid."""
            return _block.hydrogen_balance[i] == _block.hydrogen_supply[i] - _block.hydrogen_feedin[i]
          
        # Declare constraints
        block.max_hydrogen_supply_constraint = Constraint(
            t,
            rule=max_hydrogen_supply_rule
        )
        block.max_hydrogen_feedin_constraint = Constraint(
            t,
            rule=max_hydrogen_feedin_rule
        )
        block.hydrogen_balance_constraint = Constraint(
            t,
            rule=hydrogen_balance_rule
        )


    def natural_gas_grid_block_rule(self, block):
        """Rule for creating a natural gas grid block with default components 
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.ngas_balance = Var(t, domain=Reals)

        block.ngas_out = Port()
        block.ngas_out.add(
            block.ngas_balance,
            'natural_gas',
            Port.Extensive,
            include_splitfrac=False
            )
    

    def heat_grid_block_rule(self, block):

        # Get index from model
        t = block.model().t

        # Declare components
        block.heat_balance = Var(t, domain=NonNegativeReals)
        block.heat_feedin = Var(t, domain=NonNegativeReals)
        block.heat_supply = Var(t, domain=NonNegativeReals)

        block.heat_in = Port()
        block.heat_in.add(
            block.heat_feedin,
            'heat',
            Port.Extensive,
            include_splitfrac=False
        )
        block.heat_out = Port()
        block.heat_out.add(
            block.heat_supply,
            'heat',
            Port.Extensive,
            include_splitfrac=False
        )

        
        # Define construction rules for constraints
        def heat_balance_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.heat_balance[i] == (
                _block.model().heat_demand[i] 
                + _block.heat_supply[i] 
                - _block.heat_feedin[i]
                )
        
        def supply_heat_demand_rule(_block, i):
            """Rule for fully suppling the heat demand."""
            return _block.heat_balance[i] == 0
        

        # Define constraints
        block.heat_balance_constraint = Constraint(
            t,
            rule=heat_balance_rule
        )
        block.supply_heat_demand_constraint = Constraint(
            t,
            rule=supply_heat_demand_rule
        )