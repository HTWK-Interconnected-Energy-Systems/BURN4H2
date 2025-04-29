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

        block.hydrogen_out = Port()
        block.hydrogen_out.add(
            block.hydrogen_supply,
            'hydrogen',
            Port.Extensive,
            include_splitfrac=False
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
        block.ngas_supply = Var(t, domain=NonNegativeReals)

        block.ngas_out = Port()
        block.ngas_out.add(
            block.ngas_supply,
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
        block.heat_balance = Var(t, domain=Reals)
        block.heat_feedin = Var(t, domain=NonNegativeReals)
        block.heat_supply = Var(t, domain=NonNegativeReals)
        
        # Heat transfer between local grid and heat grid
        block.excess_heat_feedin = Var(t, domain=NonNegativeReals)
        block.FW_to_NW = Var(t, domain=NonNegativeReals)

        # NEUE Binärvariablen für exklusive Wärmeflussrichtung
        block.bin_excess_active = Var(t, domain=Binary)  # 1 wenn excess_heat_feedin > 0
        block.bin_FW_to_NW_active = Var(t, domain=Binary)  # 1 wenn FW_to_NW > 0

        # Maximale Wärmeströme für Big-M-Constraints
        block.max_excess_heat = Param(initialize=10)  # [MW] Max. Überschusswärme
        block.max_FW_to_NW = Param(initialize=10)  # [MW] Max. Wärme von FW zu NW
        block.min_flow = Param(initialize=0.5)      # [MW] Minimum meaningful flow

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

        
        # Define construction rules for constraints
        def heat_balance_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.heat_balance[i] == (
                _block.model().heat_demand[i] 
                + _block.heat_supply[i] 
                + _block.FW_to_NW[i]
                - _block.heat_feedin[i] 
                - _block.excess_heat_feedin[i]
                )
        
        def supply_heat_demand_rule(_block, i):
            """Rule for fully suppling the heat demand."""
            return _block.heat_balance[i] == 0
        

        # NEUE Constraints für exklusive Wärmeflussrichtung
        def excess_heat_active_rule(_block, i):
            """Begrenze excess_heat_feedin basierend auf Binärvariable"""
            return _block.excess_heat_feedin[i] <= _block.max_excess_heat * _block.bin_excess_active[i]

        def FW_to_NW_active_rule(_block, i):
            """Begrenze FW_to_NW basierend auf Binärvariable"""
            return _block.FW_to_NW[i] <= _block.max_FW_to_NW * _block.bin_FW_to_NW_active[i]
        
        def excess_heat_min_rule(_block, i):
            """Stelle sicher, dass excess_heat_feedin bei aktivem Flag mindestens den Minimalwert hat"""
            return _block.excess_heat_feedin[i] >= _block.min_flow * _block.bin_excess_active[i]
    
        def FW_to_NW_min_rule(_block, i):
            """Stelle sicher, dass FW_to_NW bei aktivem Flag mindestens den Minimalwert hat"""
            return _block.FW_to_NW[i] >= _block.min_flow * _block.bin_FW_to_NW_active[i]

        def exclusive_heat_flow_rule(_block, i):
            """Stelle sicher, dass nur eine Richtung des Wärmeflusses aktiv sein kann"""
            return _block.bin_excess_active[i] + _block.bin_FW_to_NW_active[i] <= 1
        
        # NEUE Constraints zum Block hinzufügen
        block.excess_heat_active = Constraint(t, rule=excess_heat_active_rule)
        block.FW_to_NW_active = Constraint(t, rule=FW_to_NW_active_rule)
        block.exclusive_heat_flow = Constraint(t, rule=exclusive_heat_flow_rule)
        
        # Define constraints
        block.heat_balance_constraint = Constraint(
            t,
            rule=heat_balance_rule
        )
        block.supply_heat_demand_constraint = Constraint(
            t,
            rule=supply_heat_demand_rule
        )

        block.excess_heat_min = Constraint(t, rule=excess_heat_min_rule)  # NEW
        block.FW_to_NW_min = Constraint(t, rule=FW_to_NW_min_rule)        # NEW

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
        block.heat_balance = Var(t, domain=Reals)
        block.heat_supply = Var(t, domain=NonNegativeReals)
        block.heat_dissipation = Var(t, domain=NonNegativeReals)
        block.heat_feedin = Var(t, domain=NonNegativeReals)
       
        # Ports
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


        # Define construction rules for constraints
        def waste_heat_balance_rule(_block, i):
            """Rule for calculating the overall power."""
            return _block.heat_balance[i] == (
                + _block.heat_supply[i]
                + _block.heat_dissipation[i] 
                - _block.heat_feedin[i]
                )    
        
        def supply_waste_heat_rule(_block, i):
            """Rule for fully suppling the heat demand."""
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
            Block(rule=self.local_heat_grid_block_rule))
            
    def local_heat_grid_block_rule(self, block):

        t = block.model().t

        block.heat_balance = Var(t, domain=Reals)
        block.heat_supply = Var(t, domain=NonNegativeReals)
        block.Z1_heat_feedin = Var(t, domain=NonNegativeReals)
        block.Z2_heat_feedin = Var(t, domain=NonNegativeReals)
        block.district_heat_feedin = Var(t, domain=NonNegativeReals)
        

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
    
        def supply_heat_demand_balance_rule(_block, i):
            """Rule for fully suppling the heat demand."""
            return _block.heat_balance[i] == 0
        
        def supply_heat_demand_rule(_block, i):
            """Rule for fully suppling the heat demand."""
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
                sum(_block.heat_feedin[i] for i in t) >= 
                0.8 * sum(_block.model().local_heat_demand[i] for i in t)
            )

        # Declare constraints
        # block.annual_local_heat_share_constraint = Constraint(
        #     t,
        #     rule=annual_local_heat_share_rule
        # )
        
        block.supply_heat_demand_constraint = Constraint(
            t,
            rule=supply_heat_demand_rule
        )

        block.supply_heat_demand_balance_constraint = Constraint(
            t,
            rule=supply_heat_demand_balance_rule
        )

        block.max_district_heat_feedin_constraint = Constraint(
            t,
            rule=max_district_heat_feedin_rule
        )

    
        




    

