#!/usr/bin/env python
# coding: utf-8




from sklearn.model_selection import KFold
import pandas as pd
import numpy as np
from keras.preprocessing.sequence import pad_sequences
from skmultilearn.problem_transform import LabelPowerset
from imblearn.over_sampling import RandomOverSampler
from keras.models import Model
from keras.losses import binary_crossentropy
from keras.optimizers import Adam
from keras.layers import Input, Dense
import pickle
import scipy
import keras
from tqdm import tqdm
from keras import activations
from keras.models import load_model
from keras import backend as K
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf
import random as rn
import os
import sys

inputFile = sys.argv[1]
outputFile = sys.argv[2]
threshold = sys.argv[3]


data = pd.read_csv(inputFile, sep='\t', encoding='utf-8',)
latentSpace = 30


num = data._get_numeric_data()
num[num > 1] = 1
labelName = []
colNameOsm = []
colNameWiki = []
for col in data.columns:
    if 'cls_' in col:
        labelName.append(col)
    if 'osmTagKey_' in col:
        try:
            if data[col].value_counts()[1]>50:
                colNameOsm.append(col)
        except KeyError:
            KeyError
    elif 'prop_' in col and 'prop_instance of' not in col:
        colNameWiki.append(col)
labels =  data[labelName]
columnsOSM = data[colNameOsm]
columnsWiki = data[colNameWiki]
labelNameDict = {}
for i in range(len(labelName)):
    labelNameDict[i] = labelName[i]
columnsWikiDict = {}
for i in range(len(colNameWiki)):
    columnsWikiDict[i] = colNameWiki[i]
colNameOsmDict = {}
for i in range(len(colNameOsm)):
    colNameOsmDict[i] = colNameOsm[i]
        #print(c)
columns = colNameOsm+colNameWiki
columnsDict = {}
for i in range(len(columns)):
    columnsDict[i] = columns[i]

fold_var = 1
kf = KFold(n_splits = 3, random_state = 42, shuffle = True)
train_index, val_index = list(kf.split(columnsOSM,labels))[0]
osm_train = columnsOSM.iloc[train_index].values
osm_test = columnsOSM.iloc[val_index].values
wiki_train = columnsWiki.iloc[train_index].values
wiki_test = columnsWiki.iloc[val_index].values
y_train = labels.iloc[train_index].values
y_test = labels.iloc[val_index].values


# generate training data for discriminator
def generate_adverse_labels(osm, wiki):
    osm_part = np.ones((osm.shape[0], 1))
    wiki_part = np.zeros((wiki.shape[0], 1))
    return np.concatenate((osm_part, wiki_part))


def balance(x,y):
    # Import a dataset with X and multi-label y

    lp = LabelPowerset()
    ros = RandomOverSampler(random_state=42)

    # Applies the above stated multi-label (ML) to multi-class (MC) transformation.
    yt = lp.transform(y)

    X_resampled, y_resampled = ros.fit_sample(x, yt)
    # Inverts the ML-MC transformation to recreate the ML set
    y_resampled = lp.inverse_transform(y_resampled)
    y_resampled = y_resampled.toarray()
    return X_resampled, y_resampled





def transform_input(osm_train, osm_test, wiki_train, wiki_test, y_train, y_test):
    
    #total length of the input = OSM tags + OSM keys + KG properties
    maxlen =osm_train.shape[1]+wiki_train.shape[1]
    osm_train_pad = pad_sequences(osm_train, padding='post', maxlen=maxlen)
    osm_test_pad = pad_sequences(osm_test, padding='post', maxlen=maxlen)
    wiki_train_pad = pad_sequences(wiki_train, padding='pre', maxlen=maxlen)
    wiki_test_pad = pad_sequences(wiki_test, padding='pre', maxlen=maxlen)
    
    print("osm_train", osm_train_pad.shape, "wiki_train", wiki_train_pad.shape)
    x_train = np.concatenate((osm_train_pad, wiki_train_pad))
    print("x_train", x_train.shape)

    print("osm_test", osm_test_pad.shape, "wiki_test", wiki_test_pad.shape)
    x_test = np.concatenate((osm_test_pad, wiki_test_pad))
    print("x_test", x_test.shape)

    print("y_train", y_train.shape)
    y_train = np.concatenate((y_train, y_train))
    print("y_train", y_train.shape)

    print("y_test", y_test.shape)
    y_test = np.concatenate((y_test, y_test))
    print("y_test", y_test.shape)

    adverse_train = generate_adverse_labels(osm_train, wiki_train)
    print("adverse_train", adverse_train.shape)
    adverse_test = generate_adverse_labels(osm_test, wiki_test)
    print("adverse_test", adverse_test.shape)

    
    return x_train, y_train, adverse_train, x_test, y_test, adverse_test


x_train, y_train, adverse_train, x_test, y_test, adverse_test = transform_input(osm_train, osm_test, wiki_train, wiki_test, y_train, y_test)

#loss for adversarial component
def maxLoss(y_true, y_pred):
    return -1.0 * binary_crossentropy(y_true, y_pred)



class SchemaModel:

    def __init__(self, no_inputs, no_outputs):
        optimizer = Adam(0.0001, 0.5)
        self.model = self.define_discriminator(no_inputs, no_outputs)
        
        losses = {
                "class": 'binary_crossentropy',
                "adverse": maxLoss,
                }
        self.model.compile(loss=losses,
                                   optimizer=optimizer,
                                   metrics=['accuracy'])
        
        
    def define_discriminator(self, no_inputs, no_outputs):
        inputs = Input(shape=(no_inputs,), name = 'input')
        
        X_1 = Dense(100, activation='relu', name = 'layer1')(inputs)
        latent_rep = Dense(latentSpace, activation='relu', name = 'latentRep')(X_1)

        # KG classfication
        fc_1 = Dense(latentSpace, activation='relu', name = 'layer3')(latent_rep)
        fc_2 = Dense(latentSpace , activation='relu', name = 'layer4')(fc_1)
        
        classifier = Dense(no_outputs, activation='sigmoid', name = 'class')(fc_2)
        
        #adversarial compenent
        adverse= Dense(1, activation='softmax', name = 'adverse')(latent_rep)
        
        
        model = Model(inputs, [classifier, adverse])
        return model





os.environ['PYTHONHASHSEED'] = '0'

# Setting the seed for numpy-generated random numbers
np.random.seed(0)

# Setting the seed for python random numbers
rn.seed(1254)

# Setting the graph-level random seed.
tf.set_random_seed(89)

from keras import backend as K

session_conf = tf.ConfigProto(
      intra_op_parallelism_threads=1,
      inter_op_parallelism_threads=1)

#Force Tensorflow to use a single thread
sess = tf.Session(graph=tf.get_default_graph(), config=session_conf)

K.set_session(sess)


m = SchemaModel(x_train.shape[1], y_train.shape[1])


m.model.summary()

hist = m.model.fit(x=x_train, y=[y_train, adverse_train], epochs=100, shuffle=True)

def getClassIndex(clsId, y_test):
    t = np.argwhere(y_test>0)
    clsIndex = []
    for i in range(len(t)):
        if t[i][1] == clsId:
            clsIndex.append(t[i][0])
    return clsIndex

def getClassAcc(y_test, y_pred, cls, threshold):
    indexes = getClassIndex(cls, y_test)
    total_number = len(indexes)
    fn = 0
    tp = 0
    fp = 0
    for i in range(len(y_pred)):
        if i in indexes:
            if y_pred[i][cls]>threshold:
                tp = tp+1
            elif y_pred[i][cls]<threshold:
                fn = fn+1
        elif i not in indexes:
            if y_pred[i][cls]>threshold:
                fp = fp+1
    try:
        precision = tp/(tp+fp)
    except ZeroDivisionError:
        precision = 0
    try:
        recall = tp/(tp+fn)
    except ZeroDivisionError:
        recall = 0
    return cls, total_number, precision, recall
    

#a = m.model.predict(x_test)


#get per class accuracy
#for i in range(y_test.shape[1]):
#    print(getClassAcc(y_test, a[0],i , 0.9))

#create the array for testing with one row for 1 input
testKeyTag = np.zeros((x_train.shape[1], x_train.shape[1]))
for i in range(len(testKeyTag)):
    testKeyTag[i][i] = 1

#get the activations of the last layer
get_layer_output = K.function([m.model.layers[0].input],
                                  [m.model.layers[5].output])

layer_output = get_layer_output(testKeyTag)[0]
def getMatches():
    listPrecRecall = []
    for i in range(len(testKeyTag)):
        if '=' in columnsDict[np.argmax(testKeyTag[i])] and not any(map(str.isdigit, columnsDict[np.argmax(testKeyTag[i])]))  and '=yes' not in columnsDict[np.argmax(testKeyTag[i])] and '=no' not in columnsDict[np.argmax(testKeyTag[i])]:
            for j in range(len(layer_output[i])):
                listPrecRecall.append((columnsDict[np.argmax(testKeyTag[i])].replace('osmTagKey_',''),labelNameDict[j].replace('cls_',''), layer_output[i][j]))
    return listPrecRecall

matches = getMatches()
matchDF = pd.DataFrame(matches, columns=['tag', 'cls', 'value'])
matchDF = matchDF[matchDF['value']>threshold]
matchDF.to_csv(outputFile, sep='\t', encoding='utf-8', index=False)

