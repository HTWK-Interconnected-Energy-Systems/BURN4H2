import os
import pandas as pd
from datetime import datetime


def get_prices(xlsx_file: pd.ExcelFile, sheet_name: str):
    """ Reads a xlsx file according to the template of the Zukunftsbilder. """

    # Reading spreadsheet from the xlsx
    price_df = pd.read_excel(
        xlsx_file,
        sheet_name=sheet_name,
        skiprows=9)
    
    # Increasing index by 1
    price_df.index += 1

    # Preparing variables
    column_names = price_df.columns
    data_dict = {}

    # Iterating through spreadsheet data
    for pos, name in enumerate(column_names):
        data = price_df.loc[:, name]

        # Checking if actual column contains timestamps
        if isinstance(data.iloc[0], datetime):
            year = str(data.iloc[0].year)

            # Adding data to result dictionary
            data_dict[year] = price_df.loc[:, column_names[pos + 1]].dropna().to_dict()      
        else:
            continue
    
    return data_dict


if __name__ == '__main__':

    PATH_IN = 'data/raw/'
    PATH_OUT = 'data/input/'

    scenarios = ['GEE23', 'KT23', 'UE23']
    sheets = ['Gaspreise_Struktur_2016_', 'Strompreise_Strukt_2016_']

    for scenario in scenarios:
        print(scenario)
        path_out = PATH_OUT + '/' + scenario + '/'

        if not os.path.exists(path_out):
            os.makedirs(path_out)

        xlsx = pd.ExcelFile(PATH_IN + 'Zeitreihen_Struktur_2016_' + scenario + '_nicht_freigegeben.xlsx')

        for sheet in sheets:
            print(sheet)
            data = get_prices(xlsx, sheet + scenario.replace('23', '2023'))
        
            for key in data.keys():
                df = pd.DataFrame.from_dict(data[key], orient='index', columns=['value'])
                df.index.name='t'
                if sheet is sheets[0]:
                    df.to_csv(path_out + 'gas_price_' + key + '.csv')
                else:
                    df.to_csv(path_out + 'power_price_' + key + '.csv')
    #     power_data = get_prices(xlsx, 'Strompreise_Strukt_2016_UE2023')


    # gas_df = pd.DataFrame(gas_data)
    # gas_df.index.name = 't'

    # power_df = pd.DataFrame(power_data)
    # power_df.index.name = 't'

    # for year in gas_data.keys():
    #     gas_df[year].to_csv('data/input/gas_prices_' + year + '.csv')
    #     power_df[year].to_csv('data/input/power_prices_' + year + '.csv')


