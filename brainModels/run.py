import numpy as np
import sys
sys.path.append("./")
from brainModels.benchmark import benchmark
from brainModels.analysis import Plots
#from benchmark import benchmark

if __name__ == "__main__":
    #print("Running benchmark")
    result=benchmark()

    
    grouped_df=result.groupby(['evaluation','pipeline', 'eval Type','dataset']).agg({
                "subject": 'nunique',
                'auc': lambda x: f'{np.mean(x):.3f} ± {np.std(x):.3f}',
                'eer': lambda x: f'{np.mean(x)*100:.3f} ± {np.std(x)*100:.3f}',
                'frr_1_far': lambda x: f'{np.mean(x)*100:.3f}'
            }).reset_index()
    
    print(grouped_df)
    plots = Plots()
    plots._plot_eer(result)
   
    
