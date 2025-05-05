from pyomo.environ import *
from pyomo.network import *

import pandas as pd


class Photovoltaics:
    """Class for constructing photovoltaic asset objects.
    
    This class creates a photovoltaic system that converts solar radiation
    into electrical power based on provided capacity factors and profiles.
    """

    def __init__(self, name, filepath, capacity_factors, index_col=0) -> None:
        self.name = name
        self.get_data(filepath, index_col)
        self.get_capacity_factors(capacity_factors, index_col)
    
    def get_data(self, filepath, index_col):
        """Collects data from a csv."""
        self.data = pd.read_csv(
            filepath,
            index_col=index_col
        )
    
    def get_capacity_factors(self, capacity_factors, index_col):
        """Collects capacity factor data from a csv."""
        self.capacity_factors = pd.read_csv(
            capacity_factors,
            index_col=index_col
        )
    
    def add_to_model(self, model):
        """Adds the asset as a pyomo block component to a given model."""
        model.add_component(
            self.name,
            Block(rule=self.pv_block_rule)
        )
    
    def pv_block_rule(self, block):
        """Rule for creating a photovoltaic block with default components and constraints."""
        
        # Get index from model
        t = block.model().t

        # Get profile from model
        norm_pv_profile = block.model().normalized_pv_profile

        # Declare components
        block.power = Var(t, domain=NonNegativeReals)

        # Declare ports
        block.power_out = Port()
        block.power_out.add(
            block.power, 
            'power', 
            Port.Extensive, 
            include_splitfrac=False
        )

        # Declare construction rules for constraints
        def power_generation_rule(_block, i):
            """Rule for calculating the power generation of the photovoltaics.
            
            The power output is based on the installed capacity, inverter efficiency,
            and the normalized PV profile for the current time step.
            """
            installed_power = self.data.loc['value', 'installed_power']
            inverter_efficiency = self.data.loc['value', 'inverter_efficiency']
            capacity_factors = self.capacity_factors['capacity_factor']
            return _block.power[i] == installed_power * inverter_efficiency * norm_pv_profile[i]
        
        # Define constraints
        block.power_generation_constraint = Constraint(
            t,
            rule=power_generation_rule
        )