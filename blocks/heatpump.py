from pyomo.environ import *
from pyomo.network import *

import pandas as pd


class HeatpumpStageOne:
    """ Class for constructing heatpump objects. """

    def __init__ (self, name, filepath, index_col=0) -> None:
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
            Block(rule=self.heatpump_block_rule)
        )


    def heatpump_block_rule(self, block):
        t = block.model().t

        # Heatpump Variables
        block.bin = Var(t, within=Binary) # Binärvariable
        block.power = Var(t, domain=NonNegativeReals) # Power needed for the heat pump 
        block.heat_input = Var(t, domain=NonNegativeReals) # Q_zu 
        block.heat = Var(t, domain=NonNegativeReals) # Q_0
        
        # Parameters
        block.delta_T_min = Param(t, initialize=10)  
    
        # Parameters Kältemittel
        block.R = Param(t, initialize=488) #spezifischer Gaskonstante R-717 [J/kgK]
        block.k = Param(t, initialize=1.31) # Iseotropenexponent R-717  

        
        # Zustandsgrößen Kreisprozess 

        # Äußere Verhältnisse für Medium Wasser
        block.T_q  = Param(t, initialize=0+273.15) # Temperatur Quelle in Kelvin -> äußeres Medium
        block.T_k = Param(t, initialize=35+273.15) # Temperatur Senke in Kelvin -> äußeres Medium
          
        # Innere Verhältnisse für Kältemittel R-717
        # Parameters Druck p
        block.p1 = Param(t, initialize=3 * 10**6) # bar in Pa Eintrittsdruck Verdichter  
        block.p2 = Param(t, initialize=17 * 10**6) # bar in Pa Austrittsdruck Verdichter
        block.p3 = Param(t, initialize=17 * 10**6) # bar in Pa Austrittsdruck Kondensator
        block.p4 = Param(t, initialize=3 * 10**6) # bar in Pa Eintrittsdruck Verdampfer

        # Parameter Temperatur T
        block.T1 = Param(t, initialize=-10+273.15) # Grad Celsius in Kelvin 
        block.T2 = Param(t, initialize=125+273.15) # Grad Celsius in Kelvin 
        block.T3 = Param(t, initialize=45+273.15) # Grad Celsius in Kelvin 
        block.T4 = Param(t, initialize=-10+273.15) # Grad Celsius in Kelvin 

        # Parameter Enthalpie h
        block.h1 = Param(t, initialize=1450) # Enthalpie kJ/kg 
        block.h2 = Param(t, initialize=1720) # Enthalpie kJ/kg
        block.h3 = Param(t, initialize=420) # Enthalpie kJ/kg
        block.h4 = Param(t, initialize=420) # Enthalpie kJ/kg

        # Verdichter 

        # Variables
        block.capacity_compressor = Var(t, domain=NonNegativeReals) # Verdichterleistung [kW]
        block.volume_flow = Var(t, domain=NonNegativeReals) # Volumenstrom Verdichter [m^3/s]
        block.massflow_refigerant = Var(t, domain=NonNegativeReals) # Massenstrom Kältemittel [kg/s]
        block.swept_volume = Var(t, domain=NonNegativeReals) # Hubraum Verdichter [m^3/s]

        # Parameters
        block.max_volume_flow_compressor = Param(t, initialize=564/3600) # Maximaler Volumenstrom Verdichter [m^3/h] in [m^3/s]
        block.electrical_efficiency_compressor = Param(t, initialize=0.85) # Elektrische Effizienz Verdichter
        block.n = Param(t, initialize=1500/60) # Drehzahl Verdichter [1/min] in [1/s] !!! muss zwischen 500 und 1500 liegen !!!
        block.z = Param(t, initialize=6) # Anzahl der Zylinder Verdichter


        # Port 1
        block.power_in = Port()
        block.power_in.add(block.power,'power', Port.Extensive, include_splitfrac=False)

        # Port 2
        block.heat_in = Port()
        block.heat_in.add(block.heat_input,'waste_heat',Port.Extensive,include_splitfrac=False)

        # Port 3
        block.heat_out = Port()
        block.heat_out.add(block.heat,'waste_heat',Port.Extensive, include_splitfrac=False)
     
       
        # Expressions
        def ideal_cop_rule(_block, i):
            """
            Expression: COP_Ideal
            Rule for the ideal COP. Carnot-Wirkungsgrad für Wärmepumpen.
            COP_ideal = T_k / (T_k - T_q) 
            """
            return (_block.T3[i]) / ((_block.T3[i]) - (_block.T1[i]))
        
        def efficiency_rule(_block, i):
            """
            Expression: d 
            Rule for the factor to calculate the real COP.
            """
            # Factors for working fluid R-717 
            A = 0.6932
            B = -0.4851
            return A + B / _block.ideal_cop[i]
        
        def real_cop_rule(_block, i):
            """
            Expression: COP_ideal
            Rule for the real coefficient of performance.
            """
            return _block.ideal_cop[i] * _block.d[i]
        

        # Define expressions
        block.ideal_cop = Expression(
            t, 
            rule=ideal_cop_rule
        )

        block.d = Expression(
            t, 
            rule=efficiency_rule
        )

        block.real_cop = Expression(
            t, 
            rule=real_cop_rule
        )   


        # Constraints
        def heat_pump_operation_rule(_block, i):
            """Rule for the heat pump operation."""
            return _block.heat[i] * 1000 == _block.ideal_cop[i]  * _block.capacity_compressor[i]  # in kW
        
        def capacity_compressor_rule(_block, i):
            """
            Variable: P_v
            Rule for the compressor capacity. P_v depends on the mass flow and the enthalpy difference.
            Assuption: isentropic compression
            """
            return _block.capacity_compressor[i]  == (_block.massflow_refigerant[i]) * (_block.h2[i]-_block.h1[i])  # in kW
        
        def massflow_depends_on_heat_input_rule(_block, i):
            """
            Variable: m_0
            Rule for the dependencies between mass flow and heat input.
            """
            return _block.massflow_refigerant[i] == ((_block.heat_input[i]*1000)/ (_block.h1[i] - _block.h4[i])) # in kg/s
        
        def volume_flow_rule(_block, i):
            """
            Variable: V
            Rule for the volume flow.
            """
            return _block.volume_flow[i] == (_block.massflow_refigerant[i] * (_block.R[i] * _block.T1[i])) / _block.p1[i] # in m^3/s
       
        def swept_volume_rule(_block, i):
            """
            Variable: swept_volume
            Rule for the swept volume.
            """
            return _block.swept_volume[i] == _block.volume_flow[i] / _block.n[i] * _block.z[i] # m^3/s
        
        def power_rule(_block, i):
            """Rule for the power input. (Elektrische Leistung  Verdichter in MW)"""
            return _block.power[i] * 1000  == _block.capacity_compressor[i] / _block.electrical_efficiency_compressor[i]

        
        def min_speed_rule(_block, i):
            """
            Variable: n (Drehzahl)
            Rule for the range of the speed.
            """
            return _block.n[i] >= 500 / 60
        
        def max_speed_rule(_block, i):
            """
            Variable: n (Drehzahl)
            Rule for the range of the speed.
            """
            return _block.n[i] <= 1500 / 60

        # Define constraints
        block.heat_pump_operation_constraint = Constraint(
            t,
            rule=heat_pump_operation_rule
        )

        block.capacity_compressor_constraint = Constraint(
            t,
            rule=capacity_compressor_rule
        )

        block.massflow_depends_on_heat_input_constraint = Constraint(
            t,
            rule=massflow_depends_on_heat_input_rule
        )

        block.power_constraint = Constraint(
            t,
            rule=power_rule
        )

        block.volume_flow_constraint = Constraint(
            t,
            rule=volume_flow_rule
        )

        block.swept_volume_constraint = Constraint(
            t,
            rule=swept_volume_rule
        )

        # block.min_speed_constraint = Constraint(
        #     t,
        #     rule=min_speed_rule
        # )

        # block.max_speed_constraint = Constraint(
        #     t,
        #     rule=max_speed_rule
        # )

        
        ############## OLD RULES ####################
        
        # def powers_rule(_block, i):
        #     """
        #     Andere Option um P_v zu berechnen. 
        #     Variable: P_v
        #     Rule for the power input. (Verdichterleistung in kW)
        #     """
        #     if easy_way == True:
        #         return _block.capacity_compressor[i] == 313 # in kW 
        #     else:
        #         return _block.capacity_compressor[i] == (_block.k[i]/(block.k[i] - 1))*_block.R[i]*_block.T_q[i]*((_block.p2[i] / _block.p1[i])**((block.k[i] - 1)/block.k[i]) - 1) * _block.massflow_refigerant[i] # in kW

        # def massflow_refigerante_rule(_block, i): 
        #     """
        #     Andere Option um m_0 zu berechnen.
        #     Variable: m_0
        #     Rule for the massflow of the refrigerant.
        #     """
        #     return _block.massflow_refigerant[i] == _block.p1[i] * (10**5) / (_block.R[i] * _block.T_q[i]) * _block.volume_flow[i]   # mass flow in  kg/s
        

        ############## OLD RULES ####################



class HeatpumpStageTwo:
    """ Class for constructing heatpump objects. """

    def __init__ (self, name, filepath, index_col=0) -> None:
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
            Block(rule=self.heatpump_block_rule)
        )


    def heatpump_block_rule(self, block):
        t = block.model().t

        # Heatpump Variables
        block.bin = Var(t, within=Binary) # Binärvariable
        block.power = Var(t, domain=NonNegativeReals) # Power needed for the heat pump 
        block.heat_input = Var(t, domain=NonNegativeReals) # Q_zu 
        block.heat = Var(t, domain=NonNegativeReals) # Q_0
        
        # Parameters
        block.delta_T_min = Param(t, initialize=10)  
    
        # Parameters Kältemittel
        block.R = Param(t, initialize=488) #spezifischer Gaskonstante R-717 [J/kgK]
        block.k = Param(t, initialize=1.31) # Iseotropenexponent R-717  

        
        # Zustandsgrößen Kreisprozess 

        # Äußere Verhältnisse für Medium Wasser
        block.T_q  = Param(t, initialize=30+273.15) # Temperatur Quelle in Kelvin -> äußeres Medium
        block.T_k = Param(t, initialize=80+273.15) # Temperatur Senke in Kelvin -> äußeres Medium
          
        # Innere Verhältnisse für Kältemittel R-717
        # Parameters Druck p
        block.p1 = Param(t, initialize=8.3 * 10**6) # bar in Pa Eintrittsdruck Verdichter  
        block.p2 = Param(t, initialize=52 * 10**6) # bar in Pa Austrittsdruck Verdichter
        block.p3 = Param(t, initialize=52 * 10**6) # bar in Pa Austrittsdruck Kondensator
        block.p4 = Param(t, initialize=8.3 * 10**6) # bar in Pa Eintrittsdruck Verdampfer

        # Parameter Temperatur T
        block.T1 = Param(t, initialize=20+273.15) # Grad Celsius in Kelvin 
        block.T2 = Param(t, initialize=170+273.15) # Grad Celsius in Kelvin 
        block.T3 = Param(t, initialize=90+273.15) # Grad Celsius in Kelvin 
        block.T4 = Param(t, initialize=20+273.15) # Grad Celsius in Kelvin 

        # Parameter Enthalpie h
        block.h1 = Param(t, initialize=1480) # Enthalpie kJ/kg 
        block.h2 = Param(t, initialize=1760) # Enthalpie kJ/kg
        block.h3 = Param(t, initialize=660) # Enthalpie kJ/kg
        block.h4 = Param(t, initialize=660) # Enthalpie kJ/kg

        # Verdichter 

        # Variables
        block.capacity_compressor = Var(t, domain=NonNegativeReals) # Verdichterleistung [kW]
        block.volume_flow = Var(t, domain=NonNegativeReals) # Volumenstrom Verdichter [m^3/s]
        block.massflow_refigerant = Var(t, domain=NonNegativeReals) # Massenstrom Kältemittel [kg/s]
        block.swept_volume = Var(t, domain=NonNegativeReals) # Hubraum Verdichter [m^3/s]

        # Parameters
        block.max_volume_flow_compressor = Param(t, initialize=564/3600) # Maximaler Volumenstrom Verdichter [m^3/h] in [m^3/s]
        block.electrical_efficiency_compressor = Param(t, initialize=0.85) # Elektrische Effizienz Verdichter
        block.n = Param(t, initialize=1500/60) # Drehzahl Verdichter [1/min] in [1/s] !!! muss zwischen 500 und 1500 liegen !!!
        block.z = Param(t, initialize=6) # Anzahl der Zylinder Verdichter


        # Port 1
        block.power_in = Port()
        block.power_in.add(block.power,'power', Port.Extensive, include_splitfrac=False)

        # Port 2
        block.waste_heat_in = Port()
        block.waste_heat_in.add(block.heat_input,'waste_heat',Port.Extensive,include_splitfrac=False)

        # Port 3
        block.heat_out = Port()
        block.heat_out.add(block.heat,'wp_heat',Port.Extensive, include_splitfrac=False)
     
       
        # Expressions
        def ideal_cop_rule(_block, i):
            """
            Expression: COP_Ideal
            Rule for the ideal COP. Carnot-Wirkungsgrad für Wärmepumpen.
            COP_ideal = T_k / (T_k - T_q) 
            """
            return (_block.T3[i]) / ((_block.T3[i]) - (_block.T1[i]))
        
        def efficiency_rule(_block, i):
            """
            Expression: d 
            Rule for the factor to calculate the real COP.
            """
            # Factors for working fluid R-717 
            A = 0.6932
            B = -0.4851
            return A + B / _block.ideal_cop[i]
        
        def real_cop_rule(_block, i):
            """
            Expression: COP_ideal
            Rule for the real coefficient of performance.
            """
            return _block.ideal_cop[i] * _block.d[i]
        

        # Define expressions
        block.ideal_cop = Expression(
            t, 
            rule=ideal_cop_rule
        )

        block.d = Expression(
            t, 
            rule=efficiency_rule
        )

        block.real_cop = Expression(
            t, 
            rule=real_cop_rule
        )   


        # Constraints
        def heat_pump_operation_rule(_block, i):
            """Rule for the heat pump operation."""
            return _block.heat[i] * 1000 == _block.real_cop[i]  * _block.capacity_compressor[i]  # in kW
        
        def capacity_compressor_rule(_block, i):
            """
            Variable: P_v
            Rule for the compressor capacity. P_v depends on the mass flow and the enthalpy difference.
            Assuption: isentropic compression
            """
            return _block.capacity_compressor[i]  == (_block.massflow_refigerant[i]) * (_block.h2[i]-_block.h1[i])  # in kW
        
        def massflow_depends_on_heat_input_rule(_block, i):
            """
            Variable: m_0
            Rule for the dependencies between mass flow and heat input.
            """
            return _block.massflow_refigerant[i] == ((_block.heat_input[i]*1000)/ (_block.h1[i] - _block.h4[i])) # in kg/s
        
        def volume_flow_rule(_block, i):
            """
            Variable: V
            Rule for the volume flow.
            """
            return _block.volume_flow[i] == (_block.massflow_refigerant[i] * (_block.R[i] * _block.T1[i])) / _block.p1[i] # in m^3/s
       
        def swept_volume_rule(_block, i):
            """
            Variable: swept_volume
            Rule for the swept volume.
            """
            return _block.swept_volume[i] == _block.volume_flow[i] / _block.n[i] * _block.z[i] # m^3/s
        
        def power_rule(_block, i):
            """Rule for the power input. (Elektrische Leistung  Verdichter in MW)"""
            return _block.power[i] * 1000  == _block.capacity_compressor[i] / _block.electrical_efficiency_compressor[i]

        
        def min_speed_rule(_block, i):
            """
            Variable: n (Drehzahl)
            Rule for the range of the speed.
            """
            return _block.n[i] >= 500 / 60
        
        def max_speed_rule(_block, i):
            """
            Variable: n (Drehzahl)
            Rule for the range of the speed.
            """
            return _block.n[i] <= 1500 / 60

        # Define constraints
        block.heat_pump_operation_constraint = Constraint(
            t,
            rule=heat_pump_operation_rule
        )

        block.capacity_compressor_constraint = Constraint(
            t,
            rule=capacity_compressor_rule
        )

        block.massflow_depends_on_heat_input_constraint = Constraint(
            t,
            rule=massflow_depends_on_heat_input_rule
        )

        block.power_constraint = Constraint(
            t,
            rule=power_rule
        )

        block.volume_flow_constraint = Constraint(
            t,
            rule=volume_flow_rule
        )

        block.swept_volume_constraint = Constraint(
            t,
            rule=swept_volume_rule
        )

        # block.min_speed_constraint = Constraint(
        #     t,
        #     rule=min_speed_rule
        # )

        # block.max_speed_constraint = Constraint(
        #     t,
        #     rule=max_speed_rule
        # )

        
        ############## OLD RULES ####################
        
        # def powers_rule(_block, i):
        #     """
        #     Andere Option um P_v zu berechnen. 
        #     Variable: P_v
        #     Rule for the power input. (Verdichterleistung in kW)
        #     """
        #     if easy_way == True:
        #         return _block.capacity_compressor[i] == 313 # in kW 
        #     else:
        #         return _block.capacity_compressor[i] == (_block.k[i]/(block.k[i] - 1))*_block.R[i]*_block.T_q[i]*((_block.p2[i] / _block.p1[i])**((block.k[i] - 1)/block.k[i]) - 1) * _block.massflow_refigerant[i] # in kW

        # def massflow_refigerante_rule(_block, i): 
        #     """
        #     Andere Option um m_0 zu berechnen.
        #     Variable: m_0
        #     Rule for the massflow of the refrigerant.
        #     """
        #     return _block.massflow_refigerant[i] == _block.p1[i] * (10**5) / (_block.R[i] * _block.T_q[i]) * _block.volume_flow[i]   # mass flow in  kg/s
        

        ############## OLD RULES ####################




   



       

