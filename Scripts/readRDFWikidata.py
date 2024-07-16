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
from SPARQLWrapper import SPARQLWrapper, JSON


inputFile = sys.argv[1]
outputFile = sys.argv[2]


lines = []
with open(inputFile, "r", encoding = 'utf8') as a_file:
    for line in a_file:
        stripped_line = line.strip()
        lines.append(re.split(r'\t', stripped_line))


for i in range(len(lines)):
    try:
        if len(lines[i])<3:
            lines.remove(lines[i])
    except IndexError:
        #lines.remove(lines[i]) ###remove this later
        break
    if len(lines[i])>4:
        del lines[i][3:]
    if len(lines[i])==4:
        del lines[i][3]


node = []
key = []
value = []
for i in range(len(lines)):
    node.append(lines[i][0])
    key.append(lines[i][1])
    value.append(lines[i][2])


for i in range(len(node)):
    node[i] = node[i].replace('<https://www.openstreetmap.org/node/','')
    node[i] = node[i].replace('>', '')


for i in range(len(node)):
    key[i] = key[i].replace('<https://wiki.openstreetmap.org/wiki/Key:','')
    key[i] = key[i].replace('>', '')


data = pd.DataFrame(list(zip(node, key, value)),columns = ['node','key', 'value']) 


data['value'] = data['value'].str.replace('\"', '')


data['tagKey'] = data[['key', 'value']].apply(lambda x: '='.join(x), axis=1)


#data = data[(data.key != '<http://www.w3.org/2003/01/geo/wgs84_pos#long') & (data.key != '<http://www.w3.org/2003/01/geo/wgs84_pos#Point')]
#data = data[(data.key != '<http://www.w3.org/1999/02/22-rdf-syntax-ns#type') & (data.key != '<http://www.w3.org/2003/01/geo/wgs84_pos#lat')]


#get the data for tags and keys of OSM.
osmTag = pd.read_csv('osmTagKeyWiki.csv', sep=',', encoding='utf-8',)
osmKey = pd.read_csv('osmKeyWiki.csv', sep=',', encoding='utf-8',)


osmKey = osmKey.drop_duplicates(subset='Keys', keep="first")


keys = list(osmKey.Keys.values)
tags = list(osmTag.Tags.values)


#create tags for key-value pair
osm_id = []
osmwiki_id = []
osmtagkey = []
osmvalue = []
wikidata = []
for index, row in data.iterrows():
    if row['key'] == 'wikidata':
        wikidata.append(row['value'])
        osmwiki_id.append(row['node'])
    if row['tagKey'] in tags:
        osm_id.append(row['node'])
        osmtagkey.append(row['tagKey'])
        osmvalue.append(row['value'])
    else:
        osm_id.append(row['node'])
        osmtagkey.append(row['key'])
        osmvalue.append(row['value'])        


osmdata = pd.DataFrame(list(zip(osm_id, osmtagkey, osmvalue)),columns = ['osm_id','osmTagKey', 'value']) 


osmWiki = pd.DataFrame(list(zip(osmwiki_id, wikidata)),columns = ['osm_id','wikidata']) 


osmdata = pd.merge(osmWiki, osmdata, on = 'osm_id')


wikiEnt= list(set(list(data.loc[data['key'] == 'wikidata', 'value'])))
for i in range(len(wikiEnt)):
    wikiEnt[i] = wikiEnt[i].replace('\"','')
#remove values which do not have wikidata format: Q----
regex = re.compile('(Q)[0-9]+')
wikiEnt = [x for x in wikiEnt if regex.match(x)]


def get_results(endpoint_url, query):
    user_agent = "WDQS-example Python/%s.%s" % (sys.version_info[0], sys.version_info[1])
    # TODO adjust user agent; see https://w.wiki/CX6
    sparql = SPARQLWrapper(endpoint_url, agent=user_agent)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()


endpoint_url = "https://query.wikidata.org/sparql"
wiki_Data = []
i=0
while  i < len(wikiEnt):
    new_lst = wikiEnt[i:i+300]
    mystring = ''.join('wd:{0} '.format(w) for w in new_lst)
    query = """SELECT ?kgentity  ?wdLabel ?ps_Label {
  VALUES ?kgentity {wd:%s}
  ?kgentity ?p ?statement .
  ?statement ?ps ?ps_ .
  
  ?wd wikibase:claim ?p.
  ?wd wikibase:statementProperty ?ps.
  
  OPTIONAL {
  ?statement ?pq ?pq_ .
  ?wdpq wikibase:qualifier ?pq .
  }
  
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
} ORDER BY ?wd ?statement ?ps_"""%mystring

    results = get_results(endpoint_url, query)
    wiki_Data.append(results)
    #print('itt'+ str(i))
    i=i+300


kgentity = []
wdLabel = []
ps_Label = []
for i in range(len(wiki_Data)):
    for j in range(len(wiki_Data[i]['results']['bindings'])):
        kgentity.append(wiki_Data[i]['results']['bindings'][j]['kgentity']['value'])
        wdLabel.append(wiki_Data[i]['results']['bindings'][j]['wdLabel']['value'])
        ps_Label.append(wiki_Data[i]['results']['bindings'][j]['ps_Label']['value'])


for i in range(len(kgentity)):
    kgentity[i] = kgentity[i].replace('http://www.wikidata.org/entity/','')


wikidataTable = pd.DataFrame(list(zip(kgentity, wdLabel, ps_Label)),columns = ['wikidata','prop', 'value']) 


wikidataTable = wikidataTable.drop_duplicates()


wikiForClass = []
temp = []
cls = []
wikidata = []
for i in range(len(wiki_Data)):
    for j in range(len(wiki_Data[i]['results']['bindings'])):
        temp.append(wiki_Data[i]['results']['bindings'][j]['wdLabel']['value'])
        wikidata.append(wiki_Data[i]['results']['bindings'][j]['kgentity']['value'].replace('http://www.wikidata.org/entity/',''))
        if (wiki_Data[i]['results']['bindings'][j]['wdLabel']['value'] == 'instance of'):
            cls.append(wiki_Data[i]['results']['bindings'][j]['ps_Label']['value'])
            wikiForClass.append(wiki_Data[i]['results']['bindings'][j]['kgentity']['value'].replace('http://www.wikidata.org/entity/',''))


wikidatacls = pd.DataFrame(list(zip(wikiForClass, cls)),
                    columns = ['wikidata', 'cls'])


wikidataToConsider = wikidatacls[wikidatacls['cls'].isin(wikidatacls['cls'].value_counts()[wikidatacls['cls'].value_counts()> 100].index)]


wikidataTest = pd.merge(wikidataTable,wikidataToConsider, on='wikidata')


tfidf = []
className = []
propName = []
for j in (list(wikidataTest['cls'].unique())):
    if j == 'human':
        continue
    else:
        for i in (list(wikidataTest[wikidataTest['cls']==j]['prop'].unique())):
            tf = len(wikidataTest[(wikidataTest['cls']== j) & (wikidataTest['prop']== i)])
            df = len(wikidataTest[wikidataTest['prop']== i]['cls'].value_counts())
            N = 40
            weight = tf * (np.log (N/df))
            if weight == 0:
                continue
            else:
                tfidf.append(weight)
                className.append(j)
                propName.append(i)


tfidfweights = pd.DataFrame(list(zip(className, propName, tfidf)),
                    columns = ['cls', 'prop', 'tfidfval'])


groupsort = tfidfweights.sort_values(['cls'], ascending=True).groupby(['cls'], sort=False).apply(lambda x: x.sort_values(['tfidfval'], ascending=False)).reset_index(drop=True)

groupsort = groupsort.groupby('cls').head(25)
currentList = list(groupsort.prop.unique())
wikidataTable = wikidataTable[wikidataTable['prop'].isin(currentList)]
osmdata = pd.merge(osmdata, wikidataToConsider, on = 'wikidata')

cat_columns = ["osmTagKey"]
onehotTags = pd.get_dummies(osmdata, prefix_sep="_", columns=cat_columns)
onehotTags = onehotTags.groupby(['osm_id','wikidata'], as_index = False).sum()

cat_columns = ["prop"]
oneHotWikiProp = pd.get_dummies(wikidataTable, prefix_sep="_", columns=cat_columns)
oneHotWikiProp = oneHotWikiProp.groupby(oneHotWikiProp['wikidata'], as_index = False).sum()


cat_columns = ["cls"]
onehotClass = pd.get_dummies(wikidataToConsider, prefix_sep="_", columns=cat_columns)
onehotClass = onehotClass.groupby(onehotClass['wikidata'], as_index = False).sum()

tempMerge = pd.merge(oneHotWikiProp, onehotClass, on = 'wikidata')
Data = pd.merge(onehotTags,tempMerge, on = 'wikidata' )
#save the data for the particular country and the KG
Data.to_csv(outputFile, sep='\t', encoding='utf-8', index=False)

