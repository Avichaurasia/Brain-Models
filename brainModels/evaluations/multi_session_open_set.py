import logging
import os
from copy import deepcopy
from time import time
from typing import Optional, Union
import numpy as np
from mne.epochs import BaseEpochs
from sklearn.base import clone
from sklearn.metrics import get_scorer
from sklearn.model_selection import (
    GridSearchCV,
    LeaveOneGroupOut,
    StratifiedKFold,
    StratifiedShuffleSplit,
    RepeatedStratifiedKFold,
    GroupKFold,
    cross_val_score,
)
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from tqdm import tqdm
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from .base import BaseEvaluation
from sklearn import metrics
from sklearn.metrics import accuracy_score
import random
#from scipy.optimize import brentq
from scipy.interpolate import interp1d
from .metrics import Scores as score
from collections import OrderedDict
from sklearn.utils import shuffle
#from sklearn.mo
import mne
import tensorflow as tf
import pickle
import importlib
from .similarity import CalculateSimilarity

log = logging.getLogger(__name__)

Vector = Union[list, tuple, np.ndarray]

#########################################################################################################################################################
##########################################################################################################################################################
                                                    #Open-set Scenario
##########################################################################################################################################################
##########################################################################################################################################################

class MultiSessionOpenSet(BaseEvaluation):

    def __init__(
        self,
        n_perms: Optional[Union[int, Vector]] = None,
        data_size: Optional[dict] = None,
        # dataset=None,
        return_close_set=True,
        return_open_set=True,
        # paradigm=None,
        #paradigm=None,
        **kwargs
    ):
        # self.dataset = dataset
        # self.paradigm = paradigm
        #self.paradigm = paradigm
        self.n_perms = n_perms
        self.data_size = data_size
        self.return_close_set = return_close_set
        self.return_open_set = return_open_set
        super().__init__(**kwargs)

##########################################################################################################################################################
##########################################################################################################################################################
                                                #multi Session Evaluatiom for Siamese Network(Open-set Scenario)
##########################################################################################################################################################
##########################################################################################################################################################


    def _siamese_training(self, data, y, siamese, sessions):
        """
        Train Siamese networks for close-set authentication.

        Parameters:
            data (numpy.ndarray): The input data for training.
            y (numpy.ndarray): The labels/targets corresponding to the input data.
            siamese (Siamese): The Siamese network used for embeddings.

        Returns:
            tuple: A tuple containing dictionaries for different evaluation metrics.

        This method performs Open-Set Authentication using EEG-based data and Siamese networks. It utilizes GroupKFold
        cross-validation with 4 splits for training and evaluation. The function trains the Siamese network using the
        provided data, validates the model on test data, and collects results for each fold. The results are stored in
        dictionaries 'dicr3', which contain evaluation metrics for each fold of the cross-validation.
        Metrics include verification results like ROC-AUC, EER, and other relevant scores.
        """
        groupfold = GroupKFold(n_splits=4)
        count_cv=0
        dicr3={}
        dicr2={}
        dicr1={}
        mean_fpr = np.linspace(0, 1, 100)
        
        for train_index, test_index in groupfold.split(data, y, groups=y):
            x_train, x_test, y_train, y_test =data[train_index],data[test_index],y[train_index],y[test_index]
            train_sessions, test_sessions=sessions[train_index], sessions[test_index]

            scaler = StandardScaler()
            x_train = scaler.fit_transform(x_train.reshape((x_train.shape[0], -1))).reshape(x_train.shape)
            x_test = scaler.transform(x_test.reshape((x_test.shape[0], -1))).reshape(x_test.shape)
            tf.keras.backend.clear_session()
            if (siamese.user_siamese_path is None):

                # If the user siamese path is not provided, then we utilize the default siamese network
                model=siamese._siamese_embeddings(x_train.shape[1], x_train.shape[2])
            else:

                # If the user siamese path is provided, then we utilize the user siamese network
                model=siamese._user_embeddings(x_train.shape[1], x_train.shape[2])  
            embedding_network=model
            #early_stopping_callback = EarlyStopping(monitor='val_loss', patience=10)
            train_dataset = tf.data.Dataset.from_tensor_slices((x_train, y_train)).shuffle(1000).batch(siamese.batch_size)
            history = embedding_network.fit(train_dataset,
                                        workers=siamese.workers,
                                        epochs=siamese.EPOCHS,
                                        verbose=siamese.verbose)

            resutls3=CalculateSimilarity._multi_session_open_set_verification(model, x_test, y_test, test_sessions) 
            dicr3.update(dict(resutls3))
            count_cv=count_cv+1
        return dicr3

    def deep_learning_method(self, X, dataset, metadata, key, features):

        """Perform deep learning-based evaluation on provided datasets using Siamese networks.

        Parameters:
            dataset (Dataset): The dataset to be evaluated.
            pipelines (dict): Dictionary containing Siamese networks for evaluation.

        Returns:
            list: List containing evaluation results for the Siamese networks.

        This method conducts within-session evaluation of Siamese networks for provided datasets. It retrieves necessary data
        from the dataset and organizes the results for both open and close set evaluations. For each session in the metadata,
        it iterates through the provided pipelines (Siamese networks) and performs training and evaluation using the
        '_siamese_training' method. The results are saved in 'd1_dicr1.pkl', 'd1_dicr2.pkl', and 'd1_dicr3.pkl' files for
        each session within the 'open_set' directory. Evaluation metrics including AUC, EER, FRR_1_FAR, TPR, and the number of
        samples are recorded for each pipeline and session, then appended to 'results_close_set' for subsequent analysis.
        """
        #X, _, metadata=self.paradigm.get_data(dataset)
        results_saving_path=os.path.join(
            dataset.dataset_path,
            "Results",
            "SiameseMultiSessionEvaluation"
        )
        if not os.path.exists(results_saving_path):
            os.makedirs(results_saving_path)

        metadata=metadata[metadata['event_id']=="Deviant"]
        metadata=self._valid_subject_samples(metadata)
        target_index=metadata['event_id'].index.tolist()
        data=X[target_index]
        y=np.array(metadata["subject"])
        results_open_set=[]
        groups = metadata.session.values
        siamese = features[0]
        le = LabelEncoder()
        X_=data
        y_=y
        open_dicr3=self._siamese_training(X_, y_, siamese, groups)
        open_set_path=os.path.join(results_saving_path,"open_set")
        if not os.path.exists(open_set_path):
            os.makedirs(open_set_path)

        with open(os.path.join(open_set_path, "d1_dicr3.pkl"), 'wb') as f:
            pickle.dump(open_dicr3, f)

        for sub in open_dicr3.keys():
            #print("subject ", sub)
            result=open_dicr3[sub]
            result=np.array(result)
            true_lables=np.array(result[:,1])
            true_lables=true_lables.astype(np.float64)
            #print("true labels", true_lables)
            predicted_scores=np.array(result[:,0])
            #print("predicted scores", predicted_scores)
            inter_tpr, auc, eer, frr_1_far=score._calculate_siamese_scores(true_lables, predicted_scores)
            res_open_set = {
            'evaluation': 'Multi Session',
                "eval Type": "Open Set",
                "dataset": dataset.code,
                "pipeline": key,
                "subject": sub,
                #"session": session,
                "frr_1_far": frr_1_far,
                #"accuracy": mean_accuracy,
                "auc": auc,
                "eer": eer,
                "tpr": inter_tpr,
                #"std_auc": std_auc,
                "n_samples": len(X_)  # not training sample
                #"n_channels": data.columns.size
                }
            results_open_set.append(res_open_set)

        return results_open_set
    
##########################################################################################################################################################
##########################################################################################################################################################
                                        #Multi Session Evaluatiom for State-of-the-algorithms(Open-set Scenario)
##########################################################################################################################################################
##########################################################################################################################################################
    

    def _authenticate_single_subject_open_set(self, X,labels, subject_ids, features, session_groups):
               
        return 0
   
    def _prepare_data(self, dataset, features, subject_dict):
        """Prepares and combines data from various features for the given dataset.

        Parameters:
            dataset (str): dataset instance.
            features (list): A list of feature objects.

        Returns:
            pandas.DataFrame: A DataFrame containing the combined data from different features.

        Description:
            This function fetches data from each feature in the provided list for a given dataset.
            It concatenates the retrieved data into a single DataFrame. Then, it performs data cleaning
            by removing duplicate columns and filtering out rows with invalid subject and session
            combinations based on a minimum row count criterion.

        """
        df_final=pd.DataFrame()
        for feat in range(0, len(features)-1):
            df=features[feat].get_data(dataset, subject_dict)

            #print("length of features", len(df))
            #print("subject sample count", df['Subject'].value_counts())
            df_final = pd.concat([df_final, df], axis=1)

        if df_final.columns.duplicated().any():
            df_final = df_final.loc[:, ~df_final.columns.duplicated(keep='first')]

        subject_session_counts = df_final.groupby(['subject', 'session']).size().reset_index(name='counts')

        # Identify subjects with sessions having fewer than 4 rows
        invalid_subject_sessions = subject_session_counts[subject_session_counts['counts'] < 4][['subject', 'session']]
        
        # Filter out rows with invalid subject and session combinations
        df_final = df_final[~df_final.set_index(['subject', 'session']).index.isin(invalid_subject_sessions.set_index(['subject', 'session']).index)]
        #print(df_final[['session', 'Subject']].value_counts())

        #print(df[['session', 'Subject']].value_counts())

        return df_final
    
    def traditional_authentication_methods(self, dataset, subject_dict, key, features): 
        """
        Perform traditional authentication methods for single-session close-set evaluation.

        Parameters:
            dataset (Dataset): The dataset to be evaluated.
            subject_dict (dict): A dictionary containing subject information.
            key (str): The key identifier for the authentication method.
            features (list): A list of features used for authentication.

        Returns:
            list: A list of dictionaries containing evaluation metrics for each subject's session.


        Description:
            This method executes traditional authentication methods for single-session close-set evaluation.
            It prepares the data for evaluation and iterates through each subject in the dataset. For each 
            subject, it assigns label 1 to the sessions belonging to the subject being authenticated and 
            label 0 to the rest. The method then authenticates each subject using the provided features and gathers 
            evaluation metrics. Metrics include accuracy, AUC, EER, TPR, among others.
        """ 
        results_open_set=[]
        data=self._prepare_data(dataset, features, subject_dict)
        for subject in tqdm(np.unique(data.subject), desc=f"{key}-MultiSessionOpenSet"):
            df_subj=data.copy(deep=True)

            # Assign label 0 to all subjects
            df_subj['Label']=0

            # Updating the label to 1 for the subject being authenticated
            df_subj.loc[df_subj['subject'] == subject, 'Label'] = 1
            session_groups = df_subj.session.values
            subject_ids=df_subj.Subject.values
            labels=np.array(df_subj['Label'])
            X=np.array(df_subj.drop(['Label','Event_id','Subject','session'],axis=1))

            open_set_scores=self._authenticate_single_subject_open_set(X,labels, subject_ids, features, session_groups=session_groups)
            mean_accuracy, mean_auc, mean_eer, mean_tpr, tprs_upper, tprr_lower, std_auc, mean_frr_1_far=open_set_scores
            res_open_set = {
            # "time": duration / 5.0,  # 5 fold CV
            'evaluation': 'Multi Session',
            "eval Type": "Open Set",
            "dataset": dataset.code,
            "pipeline": key,
            "subject": subject,
            #"session": session,
            "frr_1_far": mean_frr_1_far,
            "accuracy": mean_accuracy,
            "auc": mean_auc,
            "eer": mean_eer,
            "tpr": mean_tpr,
            "tprs_upper": tprs_upper,
            "tprs_lower": tprr_lower,
            "std_auc": std_auc,
            "n_samples": len(df_subj)
            #"n_samples": len(data)  # not training sample
            #"n_channels": data.columns.size
                }
            #print(res_close_set)
            results_open_set.append(res_open_set)
        return results_open_set 

    def _evaluate(self, dataset, pipelines):

        """
        Evaluates authentication methods on a given dataset using specified pipelines.

        Parameters:
            dataset (str): The dataset for evaluation.
            pipelines (dict): A dictionary containing authentication and feature methods as keys
                              and their corresponding features as values.
                              For example: {'AR+PSD+LR': [AutoRegressive(order=6), PowerSpectralDensity(), LogisticRegression()],
                                            'AR+PSD+SVM': [AutoRegressive(order=6), PowerSpectralDensity(), SVC(kernel='rbf', probability=True)],
                                             'Siamese': Siamese()}


        Returns:
            list: A list containing the evaluation results for each specified authentication method.
        """

        X, subject_dict, metadata=self.paradigm.get_data(dataset)
        results_pipeline=[]
        for key, features in pipelines.items():   
            if (key.upper()=='SIAMESE'):

                # If the key is Siamese, then we use the deep learning method
                results=self.deep_learning_method(X, dataset, metadata, key, features)
                results_pipeline.append(results) 
            else:

                # If the key is not Siamese, then we use the traditional authentication methods
                results=self.traditional_authentication_methods(dataset, subject_dict, key, features)
                results_pipeline.append(results)
        return results_pipeline
   
    
    def evaluate(self, dataset, pipelines):

            """
            Evaluate a dataset using a set of pipelines.

            Parameters:
                - dataset: The dataset for evaluation.
                - pipelines (dict): A dictionary containing authentication and feature methods as keys
                                and their corresponding features as values.
                                For example: {'AR+PSD+LR': [AutoRegressive(order=6), PowerSpectralDensity(), LogisticRegression()],
                                                'AR+PSD+SVM': [AutoRegressive(order=6), PowerSpectralDensity(), SVC()],
                                                'Siamese': Siamese()}
            
            Returns:
                - results: Evaluation results.
                - results_path: Path to save the results.
                - scenario: Evaluation scenario (Open-set).
            """

            results=self._evaluate(dataset, pipelines)
            scenario="open_Set"
            results_path=os.path.join(
                dataset.dataset_path,
                "Results",
                "MultiSessionEvaluation"
            )
            return results, results_path, scenario
    
    def _valid_subject_samples(self, metadata):

        """
        Filter out subjects with sessions having fewer than 4 samples.

        Parameters:
            - metadata: DataFrame containing metadata.

        Returns:
            - metadata: Filtered metadata.
        """

        subject_session_counts = metadata.groupby(['subject', 'session']).size().reset_index(name='counts')

        # Identify subjects with sessions having fewer than 4 samples
        invalid_subject_sessions = subject_session_counts[subject_session_counts['counts'] < 4][['subject', 'session']]
        
        # Filter out rows with invalid subject and session combinations
        metadata = metadata[~metadata.set_index(['subject', 'session']).index.isin(invalid_subject_sessions.set_index(['subject', 'session']).index)]  
        return metadata
    
    def _valid_subject_session(self, df, subject, session):
    
        """
        Check if a subject has the required session for single-session evaluation.

        Parameters:
            - df: The data for the subject.
            - subject: The subject to be evaluated.
            - session: The session to be evaluated.

        Returns:
            - valid: A boolean indicating if the subject has the required session.
        """

        df_subject=df[df['subject']==subject]
        sessions=df_subject.session.values
        if (session not in sessions):
            return False
        
        else:
            return True
    
    def is_valid(self, dataset):

        """
        Check if a dataset is valid for evaluation.

        Parameters:
            - dataset: The dataset for evaluation.

        Returns:
            - True if the dataset is valid, otherwise False.
        """

        return True




    