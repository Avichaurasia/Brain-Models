#!/usr/bin/env python
# coding: utf-8
import glob
import os
import os.path as osp
from pathlib import Path
import shutil
import zipfile as z
from distutils.dir_util import copy_tree
import mne
import numpy as np
import yaml
from mne.channels import make_standard_montage
from mne import get_config, set_config
from mne.datasets.utils import _get_path
from mne.utils import _url_to_local_path, verbose
import pooch
from pooch import file_hash, retrieve
from requests.exceptions import HTTPError
from scipy.io import loadmat
from deeb.datasets import download as dl
from deeb.datasets.base import BaseDataset
from collections import OrderedDict
from mne.utils import _url_to_local_path, verbose
import shutil
import io
from pooch import Unzip, retrieve

Mantegna2019_URL = "https://files.de-1.osf.io/v1/resources/rp4jy/providers/osfstorage/5c7651cf62c82a0018dc5cf7/?zip="
class Mantegna2019(BaseDataset):

    path_to_dataset=" "
    def __init__(self):
        super().__init__(
            subjects=list(range(1, 32)),
            sessions_per_subject=1,
            events=dict(Inconsistent=9, Consistent=7),
            code="mantegna 2019",
            interval=[-0.1, 0.9],
            paradigm="n400",
            doi=None,
            dataset_path=None
            )
    # This function has been sourced from the BDS-3 licensed repository at https://github.com/NeuroTechX/moabb    
    @verbose
    def download_dataset(self, url, sign, path=None, force_update=False, verbose=None):
        """
        This function has been sourced from the BDS-3 licensed repository at https://github.com/NeuroTechX/moabb

        References
        ----------
        [1] Vinay Jayaram and Alexandre Barachant. MOABB: trustworthy algorithm benchmarking for BCIs. 
        Journal of neural engineering 15.6 (2018): 066011. DOI:10.1088/1741-2552
        """
        path = Path(dl.get_dataset_path(sign, path))
        print(f"path: {path}")

        key_dest = f"MNE-{sign.lower()}-data"
        destination = _url_to_local_path(url, path / key_dest)
        
        destination = str(path) + destination.split(str(path))[1]
        table = {ord(c): "-" for c in ':*?"<>|'}
        destination = Path(str(path) + destination.split(str(path))[1].translate(table))

        if not destination.is_file() or force_update:
            if destination.is_file():
                destination.unlink()
            if not destination.parent.is_dir():
                destination.parent.mkdir(parents=True)
            known_hash = None
        else:
            known_hash = file_hash(str(destination))

        dlpath = retrieve(
            url,
            known_hash,
            fname="raw_data.zip",
            path=str(destination.parent),
            progressbar=True,
        )

        return dlpath

    
    def _get_single_subject_data(self, subject):
        """return data for a single subject"""

        file_path_list = self.data_path(subject)
        sessions = {}
        session_name = 'session_1'
        sessions[session_name] = {}
        run_name = 'run_1'

        raw=mne.io.read_raw_brainvision(file_path_list,eog=('LEOG', 'LBEOG', 'REOG'), preload=True, verbose=False)

        raw.rename_channels({'LEOG':'LO1','LBEOG':'IO1','REOG':'LO2','C64':'SO1','RM':'A2'})
        raw.set_channel_types({'LO1':'eog','IO1':'eog','LO2':'eog','SO1':'misc',"A2":'misc'})
        events, events_id=mne.events_from_annotations(raw, verbose=False)
        #montage = mne.channels.make_standard_montage('standard_1020')

        #stim_channels = mne.utils._get_stim_channel(None, raw.info, raise_error=False)        
        #raw.set_montage(montage, on_missing='ignore')

        sessions[session_name][run_name] = raw, events
        return sessions
    
    def data_path(self, subject, path=None, force_update=False,
                  update_path=None, verbose=None): 
        
        if subject not in self.subject_list:
            raise ValueError("Invalid subject number")
        else:
            if(subject<10):
                subject="0"+str(subject)
            else:
                subject=str(subject) 

        # define url and paths
        url = Mantegna2019_URL
        zip_filename = f"raw_data.zip"
        main_directory='raw_data'
        path_zip = self.download_dataset(url, "Mantegna2019")
        # if(Mantegna2019.path_to_dataset==" "):
        #     path_zip = self.download_dataset(url, "Mantegna2019")
        #     Mantegna2019.dataset_path=path_zip
        # else:
        #     path_zip=Mantegna2019.dataset_path

        #self.dataset_path=os.path.dirname(Path(path_zip.strip(zip_filename)))
        self.dataset_path=os.path.dirname(Path(path_zip))
        subject_dir = Path(path_zip.strip(zip_filename))/main_directory
        print("")
        if not subject_dir.exists():
            with z.ZipFile(path_zip, "r") as zip_ref:
                zip_ref.extractall(subject_dir)

        raw_data_path = os.listdir(subject_dir)
        for sub in raw_data_path:
            if sub.endswith(".vhdr") and sub.split("_")[0] == subject:
                return os.path.join(subject_dir, sub)
            