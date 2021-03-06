#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import pandas as pd
import numpy as np
import mplleaflet as mpl
import traceback
import time
import gc
import os
import itertools
import collections
import itertools
from os import path
from tqdm.notebook import tqdm
from glob import glob
from joblib import load, dump
from pymove.models.classification import DeepestST as DST
from pymove.models import datautils
from pymove.core import utils
import json
from sklearn.preprocessing import LabelEncoder
from pymove.models.classification import Tulvae as tva

paper = 'SAC'
dataset = 'brightkite' #['fousquare_nyc', 'brightkite', 'foursquare_global', gowalla,'criminal_id', 'criminal_activity']
file_train = 'data/{}/train.csv.gz'.format(dataset)
file_val = 'data/{}/val.csv.gz'.format(dataset)
file_test = 'data/{}/test.csv.gz'.format(dataset)
dir_validation = '{}/{}/tulvae/validation/'.format(paper, dataset)
dir_evaluation = '{}/{}/tulvae/'.format(paper, dataset)


df_train = pd.read_csv(file_train)
df_val = pd.read_csv(file_val)
df_test = pd.read_csv(file_test)
df = pd.concat([df_train, df_val, df_test])

le = LabelEncoder()
df['day'] = le.fit_transform(df['day'])
df_train['day'] = le.transform(df_train['day'])
df_val['day'] = le.transform(df_val['day'])
df_test['day'] = le.transform(df_test['day'])


# ## Get trajectories

label_poi = 'poi'
features = ['poi', 'label', 'tid']
data = [df_train[features], df_val[features], df_test[features]]


X, y, dic_parameters = datautils.generate_X_y_rnn(data=data,
                           features_encoding=True,
                           y_one_hot_encodding=False,
                           label_y='label',
                           label_segment='tid')


X_train = X[0]
X_val = X[1]
X_test = X[2]
y_train = y[0]
y_val = y[1]
y_test = y[2]


# ## GRID SEARCH TO TULER
num_classes = dic_parameters['num_classes']
max_lenght = dic_parameters['max_lenght']
vocab_size = dic_parameters['vocab_size']['poi']
rnn= ['bilstm']
units = [100, 200, 300]
stack = [1]
dropout =[0.5]
embedding_size = [100, 200, 300]
z_values = [100,200,300]
batch_size = [64]
epochs = [1000]
patience = [20]
monitor = ['val_acc']
optimizer = ['ada']
learning_rate = [0.001]

total = len(rnn)*len(units)*len(stack)* len(dropout)* len(embedding_size)*         len(z_values) * len(batch_size)*len(epochs) * len(patience) *len(monitor)         * len(learning_rate) 
print('There are {} iteration'.format(total))

for c in tqdm(itertools.product(rnn, units, stack, dropout, embedding_size, 
                                z_values, batch_size,epochs, patience, monitor, 
                                learning_rate), total=total):
    nn=c[0]
    un=c[1]
    st=c[2]
    dp=c[3]
    es=c[4]
    zv=c[5]
    bs=c[6]
    epoch=c[7]
    pat=c[8]
    mon=c[9]
    lr=c[10]

    filename = dir_validation + 'tuvae-{}-{}-{}-{}-{}-{}-{}-{}-{}-{}-{}-{}.csv'.format(nn, un, st, dp, es,                                                                                zv, bs,epoch, pat, mon,                                                                                 lr, features)
    if not path.exists(dir_validation):
        print('this directory {} is not exist'.format(dir_validation))
        break
    elif path.exists(filename):
        print('skip ---> {}\n'.format(filename))
    else:
        print('Creating model...')
        print(filename)
        try:
            tulvae = tva.TulvaeClassier(max_lenght=max_lenght,    
                        num_classes=num_classes,
                        vocab_size=vocab_size,
                        rnn_units=un,
                        dropout=dp,
                        embedding_size=es,
                        z_values=zv,
                        stack=st)

            tulvae.fit(X_train, y_train,
                        X_val, y_val,
                        batch_size=bs,
                        epochs=epoch,
                        learning_rate=lr,
                        save_model=False,
                        save_best_only=False,
                        save_weights_only=False)

            validation_report = tulvae.predict(X_val, y_val)
            validation_report.to_csv(filename, index=False)
            tulvae.free()
        except:
            print('ERRO')
            pass


files = utils.get_filenames_subdirectories(dir_validation)


data = []
marksplit = '-'
for f in files:
    df_ = pd.read_csv(f)
    df_['nn']=   f.split(marksplit)[1]
    df_['un']=     f.split(marksplit)[2]
    df_['st']=     f.split(marksplit)[3]
    df_['dp'] = f.split(marksplit)[4]
    df_['es'] = f.split(marksplit)[5]
    df_['zv'] = f.split(marksplit)[6]
    df_['bs'] = f.split(marksplit)[7]
    df_['epoch'] = f.split(marksplit)[8]
    df_['pat'] = f.split(marksplit)[9]
    df_['mon'] = f.split(marksplit)[10]
    df_['lr'] = f.split(marksplit)[11]
    df_['fet'] = f.split(marksplit)[12].split('.csv')[0]
    data.append(df_)
    

df_result = pd.concat(data)
df_result.reset_index(drop=True, inplace=True)
df_result.sort_values('acc', ascending=False, inplace=True)

model = 0
nn = df_result.iloc[model]['nn']
un = int(df_result.iloc[model]['un'])
st = int(df_result.iloc[model]['st'])
dp = float(df_result.iloc[model]['dp'])
es = int(df_result.iloc[model]['es'])
zv = int(df_result.iloc[model]['es'])
bs = int(df_result.iloc[model]['bs'])
epoch = int(df_result.iloc[model]['epoch'])
pat = int(df_result.iloc[model]['pat'])
mon = df_result.iloc[model]['mon']
lr = float(df_result.iloc[0]['lr'])

filename = dir_evaluation + 'eval_tuvae-{}-{}-{}-{}-{}-{}-{}-{}-{}-{}-{}-{}.csv'.format(nn, un, st, dp, es,                                                                            zv, bs,epoch, pat, mon,                                                                             lr, features)
filename

print("filename: {}".format(filename))

if not path.exists(filename):
    print('Creating a model to test set')

    evaluate_report = []
    rounds = 10


    for e in tqdm(range(rounds)):
        print('Rounds {} de {}'.format(rounds, e))
        tulvae = tva.TulvaeClassier(max_lenght=max_lenght,    
                    num_classes=num_classes,
                    vocab_size=vocab_size,
                    rnn_units=un,
                    dropout=dp,
                    embedding_size=es,
                    z_values=zv,
                    stack=st)

        tulvae.fit(X_train, y_train,
                    X_val, y_val,
                    batch_size=bs,
                    epochs=epoch,
                    learning_rate=lr,
                    save_model=False,
                    save_best_only=False,
                    save_weights_only=False)

        evaluate_report.append(tulvae.predict(X_test, y_test))
        tulvae.free()
        
    evaluate_report = pd.concat(evaluate_report)
    evaluate_report.to_csv(filename, index=False)
else:
    print('... there are a model on disk to this parameters')