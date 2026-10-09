from domain.ml_feature import FEATURE_COLUMNS, TARGET_COLUMN


class DataSplitter:
    def __init__(self, df):
        self.df = df

    def split_data(self, X, Y):
        X = self.df[FEATURE_COLUMNS]
        y = self.df[TARGET_COLUMN]
        return X, y
