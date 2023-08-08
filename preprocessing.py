import os
import pandas as pd
from datetime import datetime

PATH_IN = 'data/raw/'
PATH_OUT = 'data/input/'

SCENARIOS = ['GEE23', 'KT23', 'UE23']
SHEETS = ['Gaspreise_Struktur_2016_', 'Strompreise_Strukt_2016_']

def get_data_from_xlsx(xlsx_file: pd.ExcelFile, sheet_name: str):
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

    for scenario in SCENARIOS:
        print(scenario)
        path_out = PATH_OUT + '/' + scenario + '/'

        if not os.path.exists(path_out):
            os.makedirs(path_out)
        
        xlsx_path = PATH_IN + 'Zeitreihen_Struktur_2016_' + scenario + '_nicht_freigegeben.xlsx'
        xlsx = pd.ExcelFile(xlsx_path)

        for sheet in SHEETS:
            print(sheet)
            data = get_data_from_xlsx(
                xlsx_file=xlsx,
                sheet_name=sheet + scenario.replace('23', '2023')
                )
        
            for key in data.keys():
                df = pd.DataFrame.from_dict(data[key], orient='index', columns=['value'])
                df.index.name='t'
                if sheet is SHEETS[0]:
                    df.to_csv(path_out + 'gas_price_' + key + '.csv')
                else:
                    df.to_csv(path_out + 'power_price_' + key + '.csv')


