#!/usr/bin/env python
# coding: utf-8

from ast import literal_eval
import pandas as pd
import numpy as np
import re
import time
from numpy import array
from numpy import asarray
from numpy import zeros
import pickle
import random
from urllib.error import HTTPError, URLError
from qwikidata.sparql  import return_sparql_query_results
import sys
from SPARQLWrapper import SPARQLWrapper, JSON, SPARQLExceptions
import requests
from bs4 import BeautifulSoup

inputFile = sys.argv[1]
outputFile = sys.argv[2]

lines = []
with open(inputFile, "r") as a_file:
    for line in a_file:
        stripped_line = line.strip()
        lines.append(re.split(r'\t', stripped_line))


for i in range(len(lines)):
    try:
        if len(lines[i])<3:
            lines.remove(lines[i])
    except IndexError:
        lines.remove(lines[48593]) ###remove this later
        break
    if len(lines[i])>4:
        del lines[i][3:]
    if len(lines[i])==4:
        del lines[i][3]
node = []
key = []
value = []
for i in range(len(lines)):
    try:
        
        node.append(lines[i][0])
        key.append(lines[i][1])
        value.append(lines[i][2])
        
    except IndexError:
        print(i)
for i in range(len(node)):
    node[i] = node[i].replace('<https://www.openstreetmap.org/node/','')
    node[i] = node[i].replace('>', '')
for i in range(len(node)):
    key[i] = key[i].replace('<https://wiki.openstreetmap.org/wiki/Key:','')
    key[i] = key[i].replace('>', '')
data = pd.DataFrame(list(zip(node, key, value)),columns = ['node','key', 'value']) 

data['value'] = data['value'].str.replace('\"', '')
data['tagKey'] = data[['key', 'value']].apply(lambda x: '='.join(x), axis=1)
data = data[(data.key != '<http://www.w3.org/2003/01/geo/wgs84_pos#long') & (data.key != '<http://www.w3.org/2003/01/geo/wgs84_pos#Point')]
data = data[(data.key != '<http://www.w3.org/1999/02/22-rdf-syntax-ns#type') & (data.key != '<http://www.w3.org/2003/01/geo/wgs84_pos#lat')]
osmTag = pd.read_csv('osmTagKeyWiki.csv', sep=',', encoding='utf-8',)
osmKey = pd.read_csv('osmKeyWiki.csv', sep=',', encoding='utf-8',)
osmKey = osmKey.drop_duplicates(subset='Keys', keep="first")

keys = list(osmKey.Keys.values)
tags = list(osmTag.Tags.values)

osm_id = []
osmwiki_id = []
osmtagkey = []
wikipedia = []
for index, row in data.iterrows():
    if row['key'] == 'wikipedia':
        wikipedia.append(row['value'])
        osmwiki_id.append(row['node'])
    if row['tagKey'] in tags:
        osm_id.append(row['node'])
        osmtagkey.append(row['tagKey'])
    else:
        osm_id.append(row['node'])
        osmtagkey.append(row['key'])        

osmdata = pd.DataFrame(list(zip(osm_id, osmtagkey)),columns = ['osm_id','osmTagKey']) 
osmWiki = pd.DataFrame(list(zip(osmwiki_id, wikipedia)),columns = ['osm_id','wikipedia']) 
osmdata = pd.merge(osmWiki, osmdata, on = 'osm_id')

dbEnt= list(set(list(data.loc[data['key'] == 'wikipedia', 'value'])))
for i in range(len(dbEnt)):
    dbEnt[i] = dbEnt[i].replace('\"','')
    
def get_results(endpoint_url, query):
    user_agent = "WDQS-example Python/%s.%s" % (sys.version_info[0], sys.version_info[1])
    # TODO adjust user agent; see https://w.wiki/CX6
    sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()

wiki_Data = []
wiki_ent = []
for i in range(len(dbEnt)):
    print(dbEnt[i])
    language = dbEnt[i][0:2]
    #print(language)
    if language =='en':
        endpoint_url = 'http://dbpedia.org/sparql'
        query = """PREFIX db: <http://dbpedia.org/resource/>
        PREFIX prop: <http://dbpedia.org/property/>
        PREFIX onto: <http://dbpedia.org/ontology/>
        select distinct ?property ?value
        where { 
        {
           db:%s ?property ?value. 
        }
        union{
            ?value ?property db:%s. 
        }
        }"""%(dbEnt[i][3:].replace(' ','_'), dbEnt[i][3:].replace(' ','_'))
    
    elif language in ['de', 'fr']:#, 'sv', 'pl', 'de', 'nl', 'ar', 'eu','ca','cs','eo','el','id','ja','ko','pt','es','uk']:
        endpoint_url = 'http://%s.dbpedia.org/sparql'%language
        query = """PREFIX db: <http://%s.dbpedia.org/resource/>
        PREFIX prop: <http://%s.dbpedia.org/property/>
        PREFIX onto: <http://%s.dbpedia.org/ontology/>
        select distinct ?property ?value
        where { 
        {
           db:%s ?property ?value. 
        }
        union{
            ?value ?property db:%s. 
        }
        }"""%(language,language,language,dbEnt[i][3:].replace(' ','_'), dbEnt[i][3:].replace(' ','_'))
    #print(query)
    else:
        continue
    try:
        results = get_results(endpoint_url, query)
        wiki_Data.append(results)
        wiki_ent.append(dbEnt[i])
    except SPARQLExceptions.QueryBadFormed:
        SPARQLExceptions.QueryBadFormed
    
dbpediaEnt = []
wdLabel = []
ps_Label = []
for i in range(len(wiki_Data)):
    for j in range(len(wiki_Data[i]['results']['bindings'])):
        dbpediaEnt.append(wiki_ent[i])
        wdLabel.append(wiki_Data[i]['results']['bindings'][j]['property']['value'])
        ps_Label.append(wiki_Data[i]['results']['bindings'][j]['value']['value'])

for i in range(len(wdLabel)):
    try:
        wdLabel[i] = wdLabel[i].rsplit('/',1)[1]
    except IndexError:
        IndexError

for i in range(len(ps_Label)):
    try:
        ps_Label[i] = ps_Label[i].rsplit('/',1)[1]
    except IndexError:
        IndexError

wikiTable = pd.DataFrame(list(zip(dbpediaEnt, wdLabel, ps_Label)),columns = ['wikipedia','prop', 'value']) 
wikiTable = wikiTable.drop_duplicates()
wikiTable = wikiTable[wikiTable['prop'] != 'owl#sameAs']
wikiTable = wikiTable[wikiTable['prop'] != 'subject']
wikiTable = wikiTable[wikiTable['prop'] != 'wikiPageUsesTemplate']
wikiTable = wikiTable[wikiTable['prop'] != 'wikiPageWikiLink']
wikiTable = wikiTable[wikiTable['prop'] != 'rdf-schema#comment']
wikiTable = wikiTable[wikiTable['prop'] != 'abstract']
wikiTable = wikiTable[wikiTable['prop'] != 'rdf-schema#label']
wikiTable = wikiTable[wikiTable['value'] != 'France']
wikiTable = wikiTable[~wikiTable.prop.str.startswith('wikiPage')]
wikiTable = wikiTable[~wikiTable['value'].astype(str).str.match("Q[0-9]+")]

wikiTableClass = wikiTable[wikiTable['prop'] == '22-rdf-syntax-ns#type']
wikiTableClass = wikiTableClass[wikiTableClass['value'].isin(wikiTableClass['value'].value_counts()[wikiTableClass['value'].value_counts()> 100].index)]
wikiTableClass = wikiTableClass.drop(['prop'],axis = 1)
wikiTableClass = wikiTableClass.rename({'value': 'cls'}, axis=1)

wikiTest = pd.merge(wikiTable,wikiTableClass, on='wikipedia')
className = []
propName = []
tfidf = []
count = 0
for j in (list(wikiTest['cls'].unique())):
    if j == 'human':
        continue
    else:
        print(j)
        for i in (list(wikiTest[wikiTest['cls']==j]['prop'].unique())):
            tf = len(wikiTest[(wikiTest['cls']== j) & (wikiTest['prop']== i)])
            df = len(wikiTest[wikiTest['prop']== i]['cls'].value_counts())
            N = 40
            weight = tf * (np.log (N/df))
            if weight == 0:
                continue
            else:
                className.append(j)
                propName.append(i)
                tfidf.append(weight)
                
tfidfweights = pd.DataFrame(list(zip(className, propName, tfidf)),
                    columns = ['cls', 'prop', 'tfidfval'])
groupsort = tfidfweights.sort_values(['cls'], ascending=True).groupby(['cls'], sort=False).apply(lambda x: x.sort_values(['tfidfval'], ascending=False)).reset_index(drop=True)

groupsort = groupsort.groupby('cls').head(25)
currentList = list(groupsort.prop.unique())
wikiTable = wikiTable[wikiTable['prop'].isin(currentList)]

cat_columns = ["prop"]
oneHotWikiProp = pd.get_dummies(wikiTable, prefix_sep="_", columns=cat_columns)
oneHotWikiProp = oneHotWikiProp.groupby(oneHotWikiProp['wikipedia'], as_index = False).sum()

cat_columns = ["cls"]
onehotClass = pd.get_dummies(wikiTableClass, prefix_sep="_", columns=cat_columns)
onehotClass = onehotClass.groupby(onehotClass['wikipedia'], as_index = False).sum()

cat_columns = ["osmTagKey"]
onehotTags = pd.get_dummies(osmdata, prefix_sep="_", columns=cat_columns)
onehotTags = onehotTags.groupby(['osm_id','wikipedia'], as_index = False).sum()

tempMerge = pd.merge(oneHotWikiProp, onehotClass, on = 'wikipedia')
Data = pd.merge(onehotTags,tempMerge, on = 'wikipedia' )
Data =Data[Data['cls_wgs84_pos#SpatialThing'] == 1]
Data =Data.drop(['cls_wgs84_pos#SpatialThing'], axis = 1)
Data.to_csv(outputFile, sep='\t', encoding='utf-8', index=False)

