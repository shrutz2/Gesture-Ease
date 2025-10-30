import pickle
import numpy as np
from pathlib import Path

artifacts = Path('artifacts')
artifacts.mkdir(exist_ok=True)

class DummyScaler:
    def transform(self, arr):
        # return input unchanged (assumes numpy array)
        return arr

with open(artifacts / 'scaler.pkl', 'wb') as f:
    pickle.dump(DummyScaler(), f)

print('Created dummy scaler at artifacts/scaler.pkl')
