from pyomo.environ import *
from pyomo.network import *

class Chp:
    """Class for constructing chp asset objects.
    
    kwargs:
    -------
    forced_operation_time: integer
        Integer value (h). If declared, the forced_operation_time_constraint will be added 
        to the block construction rule.
    """


    def __init__(self, data, **kwargs) -> None:
        self.data = data
        self.kwargs = kwargs
        self.validate_kwargs()
    

    def validate_kwargs(self):
        """Checks for unknown kwargs and returns a KeyError if some are found."""
        allowed_kwargs = ['forced_operation_time']

        for key in self.kwargs:
            if key not in allowed_kwargs:
                raise(KeyError(f'Unexpected kwarg "{key}" detected.'))
    

    def chp_block_rule(self, block):
        """Rule for creating a chp block with default components and constraints."""
        # Get index from model
        t = block.model().t


        # Declare components
        block.bin = Var(t, within=Binary)
        block.gas = Var(t, domain=NonNegativeReals)
        block.power = Var(t, domain=NonNegativeReals)
        block.heat = Var(t, domain=NonNegativeReals)

        block.power_out = Port()
        block.power_out.add(block.power, 'power', block.power_out.Extensive, include_splitfrac=False)


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
            """Rule for the dependencies betwwen heat and power output."""
            heat_max = self.data.loc['max', 'heat']
            heat_min = self.data.loc['min', 'heat']
            power_max = self.data.loc['max', 'power']
            power_min = self.data.loc['min', 'power']

            a = (heat_max - heat_min) / (power_max - power_min)
            b = heat_max - a * power_max

            return _block.heat[i] == a * _block.power[i] + b * _block.bin[i]
        

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


        # Declare optional constraint via expression when right kwarg is given.
        if 'forced_operation_time' in self.kwargs:
            kwarg_value = self.kwargs['forced_operation_time']

            block.forced_operation_time_constraint = Constraint(
                expr=quicksum(block.bin[i] for i in t) >= kwarg_value
            )
