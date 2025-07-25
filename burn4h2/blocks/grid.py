from pyomo.environ import *
from pyomo.network import *

import pandas as pd


class ElectricalGrid:
    """Class for constructing electrical grid asset objects.
    
    This class creates an electrical grid that can supply 
    power to or receive power from other components in the energy system.
    """

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
        """Rule for creating an electrical power grid block with default 
        components and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.power_balance = Var(t, domain=Reals)
        block.power_supply = Var(t, domain=NonNegativeReals)
        block.power_feedin = Var(t, domain=NonNegativeReals)

        # Declare ports
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
            """Rule for calculating the overall power balance."""
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
    """Class for constructing hydrogen grid asset objects.
    
    This class creates a hydrogen grid that can supply
    hydrogen to other components in the energy system.
    """

    def __init__(self, name) -> None:
        self.name = name
    
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
        block.hydrogen_supply = Var(t, domain=NonNegativeReals)

        # Declare ports
        block.hydrogen_out = Port()
        block.hydrogen_out.add(
            block.hydrogen_supply,
            'hydrogen',
            Port.Extensive,
            include_splitfrac=False
        )


class NGasGrid:
    """Class for constructing natural gas grid asset objects.
    
    This class creates a natural gas grid that can supply
    natural gas to other components in the energy system.
    """

    def __init__(self, name) -> None:
        self.name = name
    
    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.natural_gas_grid_block_rule)
        )

    def natural_gas_grid_block_rule(self, block):
        """Rule for creating a natural gas grid block with default components 
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.ngas_supply = Var(t, domain=NonNegativeReals)

        # Declare ports
        block.ngas_out = Port()
        block.ngas_out.add(
            block.ngas_supply,
            'natural_gas',
            Port.Extensive,
            include_splitfrac=False
        )


class HeatGrid:
    """Class for constructing heat grid asset objects.
    
    This class creates a heat grid that can supply
    or receive heat from other components in the energy system.
    """

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
            Block(rule=self.heat_grid_block_rule)
        )

    def heat_grid_block_rule(self, block):
        """Rule for creating a heat grid block with default components 
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.heat_balance = Var(t, domain=Reals)
        block.heat_feedin = Var(t, domain=NonNegativeReals)
        block.heat_supply = Var(t, domain=NonNegativeReals)
        
        # Heat transfer between local grid and heat grid
        block.excess_heat_feedin = Var(t, domain=NonNegativeReals)
        block.FW_to_NW = Var(t, domain=NonNegativeReals)

        # Binary variables for exclusive heat flow direction
        block.bin_excess_active = Var(t, domain=Binary)  # 1 when excess_heat_feedin > 0
        block.bin_FW_to_NW_active = Var(t, domain=Binary)  # 1 when FW_to_NW > 0

        # Maximum heat flows for Big-M constraints
        block.max_excess_heat = Param(initialize=10)  # [MW] Max. excess heat
        block.max_FW_to_NW = Param(initialize=10)  # [MW] Max. heat from FW to NW
        block.min_flow = Param(initialize=0.5)  # [MW] Minimum meaningful flow

        # Declare ports
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

        block.excess_heat_in = Port()
        block.excess_heat_in.add(
            block.excess_heat_feedin,
            'nw_excess_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        block.heat_grid_to_local_out = Port()
        block.heat_grid_to_local_out.add(
            block.FW_to_NW,
            'fw_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        # Declare construction rules for constraints
        def heat_balance_rule(_block, i):
            """Rule for calculating the overall heat balance."""
            return _block.heat_balance[i] == (
                _block.model().heat_demand[i] 
                + _block.heat_supply[i] 
                + _block.FW_to_NW[i]
                - _block.heat_feedin[i] 
                - _block.excess_heat_feedin[i]
            )
        
        def supply_heat_demand_rule(_block, i):
            """Rule for fully supplying the heat demand."""
            return _block.heat_balance[i] == 0
        
        def excess_heat_active_rule(_block, i):
            """Limit excess_heat_feedin based on binary variable."""
            return _block.excess_heat_feedin[i] <= _block.max_excess_heat * _block.bin_excess_active[i]

        def FW_to_NW_active_rule(_block, i):
            """Limit FW_to_NW based on binary variable."""
            return _block.FW_to_NW[i] <= _block.max_FW_to_NW * _block.bin_FW_to_NW_active[i]
        
        def excess_heat_min_rule(_block, i):
            """Ensure that excess_heat_feedin has at least the minimum value when active."""
            return _block.excess_heat_feedin[i] >= _block.min_flow * _block.bin_excess_active[i]
    
        def FW_to_NW_min_rule(_block, i):
            """Ensure that FW_to_NW has at least the minimum value when active."""
            return _block.FW_to_NW[i] >= _block.min_flow * _block.bin_FW_to_NW_active[i]

        def exclusive_heat_flow_rule(_block, i):
            """Ensure that only one direction of heat flow can be active."""
            return _block.bin_excess_active[i] + _block.bin_FW_to_NW_active[i] <= 1
        
        # Define constraints
        block.heat_balance_constraint = Constraint(
            t,
            rule=heat_balance_rule
        )
        block.supply_heat_demand_constraint = Constraint(
            t,
            rule=supply_heat_demand_rule
        )
        block.excess_heat_active = Constraint(
            t, 
            rule=excess_heat_active_rule
        )
        block.FW_to_NW_active = Constraint(
            t, 
            rule=FW_to_NW_active_rule
        )
        block.exclusive_heat_flow = Constraint(
            t, 
            rule=exclusive_heat_flow_rule
        )
        block.excess_heat_min = Constraint(
            t, 
            rule=excess_heat_min_rule
        )
        block.FW_to_NW_min = Constraint(
            t, 
            rule=FW_to_NW_min_rule
        )


class WasteHeatGrid:
    """Class for constructing waste heat grid asset objects.
    
    This class creates a waste heat grid that can handle
    waste heat from other components in the energy system.
    """

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
            Block(rule=self.waste_heat_grid_block_rule)
        )
    
    def waste_heat_grid_block_rule(self, block):
        """Rule for creating a waste heat grid block with default components 
        and constraints."""
        
        # Get index from model
        t = block.model().t

        # Declare components
        block.heat_balance = Var(t, domain=Reals)
        block.heat_supply = Var(t, domain=NonNegativeReals)
        block.heat_dissipation = Var(t, domain=NonNegativeReals)
        block.heat_feedin = Var(t, domain=NonNegativeReals)
       
        # Declare ports
        block.waste_heat_in = Port()
        block.waste_heat_in.add(
            block.heat_feedin,
            'waste_heat',
            Port.Extensive,
            include_splitfrac=False
        )
        block.waste_heat_out = Port()
        block.waste_heat_out.add(
            block.heat_supply,
            'waste_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        # Declare construction rules for constraints
        def waste_heat_balance_rule(_block, i):
            """Rule for calculating the overall heat balance."""
            return _block.heat_balance[i] == (
                + _block.heat_supply[i]
                + _block.heat_dissipation[i] 
                - _block.heat_feedin[i]
            )    
        
        def supply_waste_heat_rule(_block, i):
            """Rule for ensuring heat balance is maintained."""
            return _block.heat_balance[i] == 0

        # Define constraints
        block.waste_heat_balance_constraint = Constraint(
            t,
            rule=waste_heat_balance_rule
        )
        block.supply_waste_heat_constraint = Constraint(
            t,
            rule=supply_waste_heat_rule
        )


class LocalHeatGrid:
    """Class for constructing local heat grid asset objects.
    
    This class creates a local heat grid that interacts with
    district heating and handles local heat supply requirements.
    """

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
            Block(rule=self.local_heat_grid_block_rule)
        )
            
    def local_heat_grid_block_rule(self, block):
        """Rule for creating a local heat grid block with default components 
        and constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.heat_balance = Var(t, domain=Reals)
        block.heat_supply = Var(t, domain=NonNegativeReals)
        block.Z1_heat_feedin = Var(t, domain=NonNegativeReals)
        block.Z2_heat_feedin = Var(t, domain=NonNegativeReals)
        block.district_heat_feedin = Var(t, domain=NonNegativeReals)
        
        # Declare ports
        block.Z1_NW_heat_in = Port()
        block.Z1_NW_heat_in.add(
            block.Z1_heat_feedin,
            'local_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        block.Z2_NW_heat_in = Port()
        block.Z2_NW_heat_in.add(
            block.Z2_heat_feedin,
            'local_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        block.heat_out = Port()
        block.heat_out.add(
            block.heat_supply,
            'local_heat',
            Port.Extensive,
            include_splitfrac=False
        )

        block.district_heat_in = Port()
        block.district_heat_in.add(
            block.district_heat_feedin,
            'fw_heat',
            Port.Extensive,
        )
    
        # Declare construction rules for constraints
        def supply_heat_demand_balance_rule(_block, i):
            """Rule for ensuring heat balance is maintained."""
            return _block.heat_balance[i] == 0
        
        def supply_heat_demand_rule(_block, i):
            """Rule for calculating heat demand balance."""
            return _block.heat_balance[i] == (
                + _block.Z1_heat_feedin[i]
                + _block.Z2_heat_feedin[i]
                + _block.district_heat_feedin[i]
                - _block.model().local_heat_demand[i]
            )
        
        def max_district_heat_feedin_rule(_block, i):
            """Rule for the maximal district heat feed in."""
            return _block.district_heat_feedin[i] <= self.data.loc['max', 'heat']

        def annual_local_heat_share_rule(_block, i):
            """Rule for ensuring 80% annual share from local sources."""
            return (
                sum(_block.district_heat_feedin[i] for i in t) <= 
                0.2 * sum(_block.model().local_heat_demand[i] for i in t)
            )

        # Define constraints
        block.supply_heat_demand_balance_constraint = Constraint(
            t,
            rule=supply_heat_demand_balance_rule
        )
        block.supply_heat_demand_constraint = Constraint(
            t,
            rule=supply_heat_demand_rule
        )
        block.max_district_heat_feedin_constraint = Constraint(
            t,
            rule=max_district_heat_feedin_rule
        )
        block.annual_local_heat_share_constraint = Constraint(
            t,
            rule=annual_local_heat_share_rule
        )









