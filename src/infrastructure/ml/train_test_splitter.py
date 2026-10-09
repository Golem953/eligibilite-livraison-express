from sklearn.model_selection import train_test_split

from config.settings import RANDOM_STATE


class TrainTestSplitter:
    def __init__(self, X, y):
        self.X = X
        self.y = y

    def split(self):
        X = self.X
        y = self.y
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=0.20,
            random_state=RANDOM_STATE,
            stratify=y
        )
        return X_train, X_test, y_train, y_test
