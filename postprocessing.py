import pandas as pd
import numpy as np

PATH_IN = 'data/output/'

SCENARIO = 'testing'
YEAR = '2024'

if SCENARIO == 'testing':
    path_input = PATH_IN + SCENARIO + '/'
else:
    path_input = PATH_IN + SCENARIO + '/' + YEAR + '/'

output_df = pd.read_csv(path_input + 'output_time_series.csv', index_col=0)
output_df.index.name = 't'
print(output_df.columns)

class Asset:
    """Class for evaluating bhkw output data."""

    def __init__(self, asset_id) -> None:
        self.id: str = asset_id
        self.postprocess_data: dict = {}
        self.asset_data: pd.DataFrame = pd.DataFrame()

    def get_asset_data(self, output_df: pd.DataFrame):
        """ Gets all columns from output_df with the asset id in it. """

        for column_name in output_df.columns:
            if self.id in column_name:
                self.asset_data[column_name] = output_df[column_name]
        
        if self.asset_data.empty:
            print(f'Found no data for {self.id}.')
    
    def calc_costs(self, output_df: pd.DataFrame):
        """ Calculates costs for the asset."""

        for column in self.asset_data.columns:
            if '_gas' in column:
                self.asset_data[f'{self.id}_gas_cost'] = (
                    self.asset_data[f'{self.id}_gas'] 
                    * output_df['gas_price']
                )

            elif '_power' in column:
                self.asset_data[f'{self.id}_power_cost'] = (
                    self.asset_data[f'{self.id}_power'].where(
                    self.asset_data[f'{self.id}_power'] <= 0                    
                    )
                    * output_df['power_price']
                )

                self.asset_data[f'{self.id}_power_revenue'] = (
                    self.asset_data[f'{self.id}_power'].where(
                    self.asset_data[f'{self.id}_power'] >= 0                    
                    )
                    * output_df['power_price']
                ) 

    def calc_postprocess_data(self):
        """ Calculates the sum of all columns in the asset data."""

        for column in self.asset_data.columns:
            column_sum = self.asset_data[column].sum()
            key_name = column.replace((self.id + '_'), '')
            self.postprocess_data[key_name] = column_sum


assets_dict = {}
for asset in ['bhkw', 'storage', 'plant', 'price']:
    assets_dict[asset] = Asset(asset)
    assets_dict[asset].get_asset_data(output_df)
    assets_dict[asset].calc_costs(output_df)
    assets_dict[asset].calc_postprocess_data()


postprocess_dict = {}
for asset in assets_dict.keys():
    postprocess_dict[asset] = assets_dict[asset].postprocess_data

print(postprocess_dict)

df = pd.DataFrame(postprocess_dict)
print(df)


def check_objective_value(output_dict):
    result = (output_dict['bhkw']['gas_cost'] 
              - output_dict['plant']['power_revenue']
              )
    obj_value = (pd.read_csv(path_input + 'results.csv', index_col=0)).iloc[0].values[0]
    print(obj_value)
    
    if result == obj_value:
        print('Objective value and calculated value are the same.')
        print(f'{obj_value} == {result}')
    
    else:
        print('Objective value and calculated value are not identical!')
        print(f'{obj_value} =/= {result}')


check_objective_value(postprocess_dict)
