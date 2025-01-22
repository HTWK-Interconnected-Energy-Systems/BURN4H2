from pyomo.environ import *
from pyomo.network import *

import pandas as pd

class ElectricalGrid:
    """Class for constructing electrical grid asset objects."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)
    
    
    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.electrical_grid_block_rule)
        )

    
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
    
class HydrogenGrid:
    """Class for constructing hydrogen grid asset objects."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)
    
    
    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.hydrogen_grid_block_rule)
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


class NGasGrid:
    """Class for constructing natural gas grid asset objects."""

    def __init__(self, name) -> None:
        self.name = name
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.natural_gas_grid_block_rule))


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
    

class HeatGrid:
    """Class for constructing heat grid asset objects."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)
    
    
    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    

    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.heat_grid_block_rule))


    def heat_grid_block_rule(self, block):

        # Get index from model
        t = block.model().t

        # Declare components
        block.heat_balance = Var(t, domain=NonNegativeReals)
        block.heat_feedin = Var(t, domain=NonNegativeReals)
        block.heat_supply = Var(t, domain=NonNegativeReals)

        # Ports
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

class WasteHeatGrid:
    """Class for constructing waste heat grid asset objects."""

    def __init__(self, name, filepath, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)
    
    
    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    
    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.waste_heat_grid_block_rule))

    
    def waste_heat_grid_block_rule(self,block):
        
        # Get index from model
        t = block.model().t

        # Declare components
        block.waste_heat_balance = Var(t, domain=NonNegativeReals)
        block.waste_heat_supply = Var(t, domain=NonNegativeReals)
        block.waste_heat_feedin = Var(t, domain=NonNegativeReals)

        # Ports
        block.waste_heat_in = Port()
        block.waste_heat_in.add(
            block.waste_heat_feedin,
            'waste_heat',
            Port.Extensive,
            include_splitfrac=False
        )
        block.waste_heat_out = Port()
        block.waste_heat_out.add(
            block.waste_heat_supply,
            'waste_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        # Define construction rules for constraints
        def waste_heat_balance_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.waste_heat_balance[i] == (
                + _block.waste_heat_supply[i] 
                - _block.waste_heat_feedin[i]
                )
        
        def waste_supply_heat_demand_rule(_block, i):
            """Rule for fully suppling the heat demand."""
            return _block.waste_heat_balance[i] == 0
        

        # Define constraints
        block.waste_heat_balance_constraint = Constraint(
            t,
            rule=waste_heat_balance_rule
        )
        block.waste_supply_heat_demand_constraint = Constraint(
            t,
            rule=waste_supply_heat_demand_rule
        )

