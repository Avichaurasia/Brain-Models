#!/usr/bin/env python
import glob
import os
import os.path as osp
import shutil
import zipfile as z
from distutils.dir_util import copy_tree
from pathlib import Path
import mne
import numpy as np
import yaml
from mne.channels import make_standard_montage
from scipy.io import loadmat
from deeb.datasets import download as dl
from deeb.datasets.base import BaseDataset


BI2015a_URL = "https://zenodo.org/record/3266930/files/"

class BrainInvaders2015a(BaseDataset):

    """P300 dataset bi2015a from a "Brain Invaders" experiment
    This dataset contains electroencephalographic (EEG) recordings
    of 43 subjects playing to a visual P300 Brain-Computer Interface (BCI)
    videogame named Brain Invaders. The interface uses the oddball paradigm
    on a grid of 36 symbols (1 Target, 35 Non-Target) that are flashed
    pseudo-randomly to elicit the P300 response. EEG data were recorded using
    32 active wet electrodes with three conditions: flash duration 50ms, 80ms
    or 110ms. The experiment took place at GIPSA-lab, Grenoble, France, in 2015.
    A full description of the experiment is available at [1]_. The ID of this
    dataset is bi2015a.
    :Investigators: Eng. Louis Korczowski, B. Sc. Martine Cederhout
    :Technical Support: Eng. Anton Andreev, Eng. Grégoire Cattan, Eng. Pedro. L. C. Rodrigues,
                        M. Sc. Violette Gautheret
    :Scientific Supervisor: Ph.D. Marco Congedo
    Notes
    -----
    .. versionadded:: 0.4.6
    References
    ----------
    .. [1] Korczowski, L., Cederhout, M., Andreev, A., Cattan, G., Rodrigues, P. L. C.,
           Gautheret, V., & Congedo, M. (2019). Brain Invaders calibration-less P300-based
           BCI with modulation of flash duration Dataset (bi2015a)
           https://hal.archives-ouvertes.fr/hal-02172347
    """
    def __init__(self):
        super().__init__(
            subjects=list(range(1, 44)),
            sessions_per_subject=3,
            events=dict(Target=2, NonTarget=1),
            code="Brain Invaders 2015a",
            interval=[-0.1, 0.9],
            paradigm="p300",
            doi="https://doi.org/10.5281/zenodo.3266929",
            )
            
    def _get_single_subject_data(self, subject):
        """return data for a single subject"""
         
        file_path_list = self.data_path(subject)
        all_sessions_data=[]
        sessions = {}
        for file_path, session in zip(file_path_list, [1, 2, 3]):
            #session_name = f'session_{str(file_path).split("_")[-1][1:2]}'
            session_name = "session_1"
            if session_name not in sessions.keys():
                sessions[session_name] = {}
            #sessions[session_name] = {}
            run_name = 'run_1'
            chnames = [
                'Fp1', 'Fp2', 'AFz', 'F7', 'F3', 'F4', 'F8', 'FC5', 'FC1', 'FC2', 'FC6',
                'T7', 'C3', 'Cz', 'C4', 'T8', 'CP5', 'CP1', 'CP2', 'CP6', 'P7', 'P3',
                'Pz', 'P4', 'P8', 'PO7', 'O1', 'Oz', 'O2', 'PO8', 'PO9', 'PO10', 'STI 014'
            ]

            chtypes = ['eeg'] * 32 + ['stim']
            D = loadmat(file_path)['DATA'].T
            S = D[1:33, :]
            stim = D[-2, :] + D[-1, :]
            
            X = np.concatenate([S, stim[None, :]])
            info = mne.create_info(ch_names=chnames, sfreq=512, ch_types=chtypes, 
                                   verbose=False)

            # make standard montage before read raw data
            montage=mne.channels.make_standard_montage('standard_1020')
            info.set_montage(montage, match_case=False)
            raw = mne.io.RawArray(data=X, info=info, verbose=False)
            all_sessions_data.append(raw)
            #sessions[session_name][run_name] = raw

        # Concetenating the three sessions data since there was no break between each session
        sessions[session_name][run_name]=mne.concatenate_raws(all_sessions_data, preload=True, verbose=True)
        return sessions

    
    def data_path(self, subject, path=None, force_update=False,
                  update_path=None, verbose=None): 
        ############### Original Code from Moabb Github  #################################
        # if subject not in self.subject_list:
        #     raise (ValueError("Invalid subject number"))

        # subject_paths = []
        # url = f"{BI2015a_URL}subject_{subject:02}_mat.zip"
        # path_zip = dl.data_dl(url, "BRAININVADERS2015A")
        # path_folder = path_zip.strip(f"subject_{subject:02}.zip")

        # # check if has to unzip
        # path_folder_subject = f"{path_folder}subject_{subject:02}"
        # if not (osp.isdir(path_folder_subject)):
        #     os.mkdir(path_folder_subject)
        #     zip_ref = z.ZipFile(path_zip, "r")
        #     zip_ref.extractall(path_folder_subject)

        # # filter the data regarding the experimental conditions
        # subject_paths = []
        # for session in [1, 2, 3]:
        #     subject_paths.append(
        #         osp.join(
        #             path_folder_subject, f"subject_{subject:02}_session_{session:02}.mat"
        #         )
        #     )                    
        # return subject_paths


        ############### Rephrased Code  #################################
        if subject not in self.subject_list:
            raise ValueError("Invalid subject number")

        # define url and paths
        base_url = BI2015a_URL
        subject_str = f"subject_{subject:02}"
        #print("Subject_str", subject_str)
        url = f"{base_url}{subject_str}_mat.zip"
        zip_filename = f"{subject_str}.zip"
        #print("zip file dir:", zip_filename)

        # download and extract data if needed
        path_zip = dl.data_dl(url, "BRAININVADERS2015A")
        subject_dir = Path(path_zip.strip(zip_filename)) / subject_str
        # #print("subject directory:", subject_dir)
        # with open(path_zip, 'rb') as f:
        #     first_bytes = f.read(4)
        #     print("First 4 bytes", first_bytes)

        if not subject_dir.exists():
            with z.ZipFile(path_zip, "r") as zip_ref:
                #print("zip ref:",zip_ref.read(4))
                zip_ref.extractall(subject_dir)

        # get paths to relevant files
        session_paths = [
            subject_dir / f"{subject_str}_session_{session:02}.mat" for session in [1, 2, 3]
    ]

        return session_paths
                                
#if __name__ == "__main__":
 #   bi15a=BrainInvaders2015a()
  #  print(bi15a.get_data())



