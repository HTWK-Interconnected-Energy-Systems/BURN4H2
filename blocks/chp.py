from pyomo.environ import *
from pyomo.network import *

import pandas as pd


class Chp:
    """Class for constructing chp asset objects.
    
    kwargs:
    -------
    forced_operation_time: integer
        Integer value (h). If declared, the forced_operation_time_constraint will be added 
        to the block construction rule.
    
    hydrogen_admixture: float
        Float value with arbitrary unit. If declared, the additional variables 
        and constraints for the natural gas and hydrogen consumption will be
        added to the block construction rule.
    """


    def __init__(self, name, filepath, index_col=0, **kwargs) -> None:
        self.name = name
        self.get_data(filepath, index_col)
        self.kwargs = kwargs
        self.validate_kwargs()

    

    def validate_kwargs(self):
        """Checks for unknown kwargs and returns a KeyError if some are 
        found."""

        allowed_kwargs = ['forced_operation_time', 'hydrogen_admixture']

        for key in self.kwargs:
            if key not in allowed_kwargs:
                raise(KeyError(f'Unexpected kwarg "{key}" detected.'))
    

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
            Block(rule=self.chp_block_rule)
        )
    

    def chp_block_rule(self, block):
        """Rule for creating a chp block with default components and 
        constraints."""

        # Get index from model
        t = block.model().t

        # Declare components
        block.bin = Var(t, within=Binary)
        block.gas = Var(t, domain=NonNegativeReals)
        block.power = Var(t, domain=NonNegativeReals)
        block.heat = Var(t, domain=NonNegativeReals)
        block.co2 = Var(t, domain=NonNegativeReals)
        block.waste_heat = Var(t, domain=NonNegativeReals)
        block.hydrogen_admixture_factor = Param(initialize=self.kwargs['hydrogen_admixture'])


        block.power_out = Port()
        block.power_out.add(
            block.power,
            'power',
            Port.Extensive,
            include_splitfrac=False
        )
        block.natural_gas_in = Port()
        block.natural_gas_in.add(
            block.gas,
            'natural_gas',
            Port.Extensive,
            include_splitfrac=False
        )
        block.heat_out = Port()
        block.heat_out.add(
            block.heat,
            'heat',
            Port.Extensive,
            include_splitfrac=False
        )

        block.waste_heat_out = Port()
        block.waste_heat_out.add(
            block.waste_heat,
            'waste_heat',
            Port.Extensive,
            include_splitfrac=False
        )


        # Declare construction rules for constraints
        def power_max_rule(_block, i):
            """Rule for the maximal power."""
            return _block.power[i] <= self.data.loc['max', 'power'] * _block.bin[i]


        def power_min_rule(_block, i):
            """Rule for the minimal power."""
            return self.data.loc['min', 'power'] * _block.bin[i] <= _block.power[i]
        

        def gas_depends_on_power_rule(_block, i):
            """Rule for the dependencies between gas demand and power output."""
            gas_max = self.data.loc['max', 'gas']
            gas_min = self.data.loc['min', 'gas']
            power_max = self.data.loc['max', 'power']
            power_min = self.data.loc['min', 'power']

            a = (gas_max - gas_min) / (power_max - power_min)
            b = gas_max - a * power_max

            return _block.gas[i] == a * _block.power[i] + b * _block.bin[i]


        def heat_depends_on_power_rule(_block, i):
            """Rule for the dependencies between heat and power output."""
            heat_max = self.data.loc['max', 'heat']
            heat_min = self.data.loc['min', 'heat']
            power_max = self.data.loc['max', 'power']
            power_min = self.data.loc['min', 'power']

            a = (heat_max - heat_min) / (power_max - power_min)
            b = heat_max - a * power_max

            return _block.heat[i] == a * _block.power[i] + b * _block.bin[i]
        

        def co2_depends_on_power_rule(_block, i):
            """Rule for calculating the co2 emissions."""
            co2_max = self.data.loc['max', 'co2']
            co2_min = self.data.loc['min', 'co2']
            power_max = self.data.loc['max', 'power']
            power_min = self.data.loc['min', 'power']

            a = (co2_max - co2_min) / (power_max - power_min)
            b = co2_max - a * power_max

            return _block.co2[i] == a * _block.power[i] + b * _block.bin[i]
        
        def waste_heat_depends_on_power_rule(_block, i):
            """Rule for calculating the waste heat."""
            waste_heat_max = self.data.loc['max', 'waste_heat']
            waste_heat_min = self.data.loc['min', 'waste_heat']
            power_max = self.data.loc['max', 'power']
            power_min = self.data.loc['min', 'power']

            a = (waste_heat_max - waste_heat_min) / (power_max - power_min)
            b = waste_heat_max - a * power_max
            
            return _block.waste_heat[i] == a*_block.power[i] + b*_block.bin[i]
        

        # Declare constraints
        block.power_max_constraint = Constraint(
            t,
            rule=power_max_rule
            )
        block.power_min_constraint = Constraint(
            t,
            rule=power_min_rule
            )
        block.gas_depends_on_power_constraint = Constraint(
            t,
            rule=gas_depends_on_power_rule
            )
        block.heat_depends_on_power_constraint = Constraint(
            t,
            rule = heat_depends_on_power_rule
        )
        block.co2_depends_on_power_constraint = Constraint(
            t,
            rule=co2_depends_on_power_rule
        )
        block.waste_heat_depends_on_power_constraint = Constraint(
            t,
            rule=waste_heat_depends_on_power_rule
        )   


        # Declare optional constraint via expression when right kwarg is given.
        if 'forced_operation_time' in self.kwargs:
            kwarg_value = self.kwargs['forced_operation_time']

            block.forced_operation_time_constraint = Constraint(
                expr=quicksum(block.bin[i] for i in t) >= kwarg_value
            )

        if 'hydrogen_admixture' in self.kwargs:

            hydrogen_admixture_factor = self.kwargs['hydrogen_admixture']
            if not 0 <= hydrogen_admixture_factor <= 1:
                raise ValueError(
                    'Admixture factor out of bounds. Should be >= 0 or <= 1'
                )
            
            # Delete components
            block.del_component("co2_depends_on_power_constraint")
            
            def co2_when_admixtured_depends_on_power_rule(_block, i):
                """Rule for calculating the co2 emissions when hydrogen is 
                admixtured."""
                co2_max = self.data.loc['max', 'co2']
                co2_min = self.data.loc['min', 'co2']
                power_max = self.data.loc['max', 'power']
                power_min = self.data.loc['min', 'power']

                a = (co2_max - co2_min) / (power_max - power_min)
                b = co2_max - a * power_max

                return _block.co2[i] == ((
                    a * _block.power[i] 
                    + b * _block.bin[i])
                    * (1 - _block.hydrogen_admixture_factor))
            
            block.co2_when_admixtured_depends_on_power_constraint = Constraint(
                t,
                rule=co2_when_admixtured_depends_on_power_rule
            )


            # Declare additional components
            block.natural_gas = Var(t, domain=NonNegativeReals)
            block.hydrogen = Var(t, domain=NonNegativeReals)

            block.natural_gas_in.remove('natural_gas')
            block.natural_gas_in.add(
                block.natural_gas,
                'natural_gas',
                Port.Extensive,
                include_splitfrac=False
            )

            block.hydrogen_in = Port()
            block.hydrogen_in.add(
                block.hydrogen,
                'hydrogen',
                Port.Extensive,
                include_splitfrac=False
            )

            def hydrogen_depends_on_gas_rule(_block, i):
                """Rule for determine the hydrogen demand for combustion."""
                return _block.hydrogen[i] == _block.gas[i] * _block.hydrogen_admixture_factor
            
            def ngas_depends_on_gas_rule(_block, i):
                """Rule for determine the ngas demand for combustion."""
                return _block.natural_gas[i] == _block.gas[i] * (1 - _block.hydrogen_admixture_factor)

            
            block.hydrogen_depends_on_gas_constraint = Constraint(
                t,
                rule=hydrogen_depends_on_gas_rule
            )
            block.ngas_depends_on_gas_constraint = Constraint(
                t,
                rule=ngas_depends_on_gas_rule
            )
