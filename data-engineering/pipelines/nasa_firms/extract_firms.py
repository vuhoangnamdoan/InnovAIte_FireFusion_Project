import pandas as pd

def extract_data(path):
    df = pd.read_csv(path)
    print("Data loaded successfully")
    print(df.head())
    return df

if __name__ == "__main__":
    df = extract_data("../../data/raw/firms_data.csv")