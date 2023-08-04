import pandas as pd
from datetime import datetime
from pyomo.environ import *


def get_prices(xlsx_file: pd.ExcelFile, sheet_name: str):
    """ Reads a xlsx file according to the template of the Zukunftsbilder. """

    # Reading spreadsheet from the xlsx
    gas_df = pd.read_excel(
        xlsx_file,
        sheet_name=sheet_name,
        skiprows=9)
    
    # Increasing index by 1
    gas_df.index += 1

    # Preparing variables
    column_names = gas_df.columns
    data_dict = {}

    # Iterating through spreadsheet data
    for pos, name in enumerate(column_names):
        data = gas_df.loc[:, name]

        # Checking if actual column contains timestamps
        if isinstance(data.iloc[0], datetime):
            year = str(data.iloc[0].year)

            # Adding data to result dictionary
            data_dict[year] = gas_df.loc[:, column_names[pos + 1]].dropna().to_dict()      
        else:
            continue
    
    return data_dict


if __name__ == '__main__':
    xlsx = pd.ExcelFile('data\input\Zeitreihen_UE23.xlsx')

    gas_data = get_prices(xlsx, 'Gaspreise_Struktur_2016_UE2023')
    power_data = get_prices(xlsx, 'Strompreise_Strukt_2016_UE2023')

    print(gas_data.keys())
    print([len(gas_data[key]) for key in gas_data.keys()])

    print(power_data.keys())
    print([len(power_data[key]) for key in power_data.keys()])

    print(list(power_data['2024'].keys()))