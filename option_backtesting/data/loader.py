import pandas as pd

'''
load underlying data and option data
'''
FILE_PATH_UNDERLYING = "~/Desktop/50ETF Data/510050SH.xlsx"
FILE_PATH_OPTION = "~/Desktop/50ETF Data/Optiondata/option_from_2015-2026.xlsx"

def load_underlying_data(FILE_PATH_UNDERLYING):
    df = pd.read_excel(FILE_PATH_UNDERLYING)
    return df

def load_option_data(FILE_PATH_OPTION):
    df = pd.read_excel(FILE_PATH_OPTION)
    return df


if __name__ == "__main__":
    df_underlying = load_underlying_data(FILE_PATH_UNDERLYING)
    df_option = load_option_data(FILE_PATH_OPTION)
    print(df_underlying.shape)
    print(df_option.shape)