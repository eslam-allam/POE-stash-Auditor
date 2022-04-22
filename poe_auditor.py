from secrets import token_urlsafe
import requests
import os
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import numpy as np
from subprocess import CREATE_NO_WINDOW

logging.getLogger('selenium').propagate = False
mylogs = logging.getLogger('poe_auditor')
mylogs.addHandler(logging.NullHandler())

token = ''
state = ''
token_file = './token.txt'
league = 'Archnemesis'

apis = [
     f'https://poe.ninja/api/data/currencyoverview?league={league}&type=Currency',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=Essence',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=Scarab',
     f'https://poe.ninja/api/data/currencyoverview?league={league}&type=Fragment',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=Oil',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=Incubator',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=Fossil',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=Resonator',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=DivinationCard',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=UniqueJewel',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=UniqueWeapon',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=UniqueArmour',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=DivinationCard',
     f'https://poe.ninja/api/data/itemoverview?league={league}&type=UniqueAccessory'
]

def get_leagues():
    logging.info('IMPORTING LEAGUE LIST')
    url = 'https://eslam-allam.herokuapp.com/poegetleagues'
    response = requests.get(url)
    response = response.json()
    logging.info('LEAGUE LIST IMPORTED')
    return response

def poe_login(state):
    service = Service('./chromedriver.exe')
    service.creationflags = CREATE_NO_WINDOW
    chrome_options = Options()
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-extensions")

    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        driver.get('https://eslam-allam.herokuapp.com/poerequesttoken{}'.format(state))
        WebDriverWait(driver, timeout=900).until(EC.text_to_be_present_in_element((By.ID, 'recieved'),'TOKEN ADDED TO DATABASE'))
        driver.quit()
    except Exception as e:
        mylogs.warning('FAILED TO RETRIEVE TOKEN')
        return False


    
    # Make the tests...
    response = requests.get('https://eslam-allam.herokuapp.com/tokendelivery{}'.format(state))
    response = response.text
    token = response
    

    with open(token_file, 'w+') as f:
        f.write('{}:{}'.format(state,token))
        mylogs.info('TOKEN SAVED SUCCESSFULLY')
    
    del driver, service, chrome_options
    return token

def get_token(token_file, expired= False):
    global state
    token = ''
    if expired:
        token = poe_login(state)
        return token

    exists = os.path.exists(token_file)
    if not exists:
        mylogs.warning('TOKEN NOT FOUND! REQUESTING ACCESS TOKEN')
        state = token_urlsafe(16)
        token = poe_login(state)
    else:
        with open(token_file, 'r') as f:
            mylogs.info('TOKEN FILE FOUND. IMPORTING TOKEN')
            state, token = f.readline().split(':')
            mylogs.info('TOKEN IMPORTED')
    return token




def get_stash_list(token, league):
    headers = ['id', 'name','metadata.colour', 'type']
    params = {'token':token, 'league':league}
    logging.info(f'REQUESTING STASH LIST FROM SERVER FROM LEAGUE: {league[0]}')
    response = requests.get('https://eslam-allam.herokuapp.com/requeststashlist', params=params)
    
    if response.text == 'EXPIRED':
        logging.warning('TOKEN EXPIRED: REQUESTING REFRESH')
        token = get_token(token_file, expired=True)
        return token

    logging.info('STASH LIST ACQUIRED - PROCESSING')
    response = response.json()
    response = pd.json_normalize(response['stashes'])
    
    if response.empty : 
        logging.warning('NO STASH FOR THIS LEAGUE')
        return  False

    if 'children' in response.columns:
        stash_list = response.loc[response['children'].isnull()]
        stash_list = stash_list[headers]
        folders = response.loc[~response['children'].isnull()]
        folders = folders['children']
        for child in folders:
            if type(child) == list:
                for c in child:
                    
                    c =  pd.json_normalize(c)[headers]
                    stash_list = pd.concat([stash_list,c])
            else:
                c =  pd.json_normalize(child)[headers]
                stash_list = pd.concat([stash_list,c])
        del folders
    else:
        stash_list = response[headers]
    
    
    stash_list = stash_list.rename(columns={'metadata.colour':'colour'})
    stash_list = stash_list.loc[stash_list['type'] != 'MapStash']
    stash_list = stash_list.drop(columns=['type'])
    logging.info('PROCESSING FINISHED')

    del response, headers, params
    return stash_list

def get_stash_items(token, league, stash_id):
    logging.info('REQUESTING STASH ITEMS FROM SERVER')
    params = {'token':token, 'league':league, 'stashid':stash_id}
    response = requests.get('https://eslam-allam.herokuapp.com/requeststashtab', params=params)

    if response == 'EXPIRED':
        logging.warning('TOKEN EXPIRED: REQUESTING REFRESH')
        get_token(token_file, expired=True)
        return False

    logging.info('ITEMS FETCHED - PROCESSING')
    response = response.json()
    response = pd.json_normalize(response['stash']['items'])
    
    if 'stackSize' in response.columns:
        
        response = response[['baseType', 'stackSize', 'name']]
        response['baseType'] = np.where(~(response['name'] == ''),response['name'],response['baseType'])
        response['stackSize'] = response['stackSize'].fillna(1)
        
    else:
        response2 = pd.DataFrame()
        response2[['baseType', 'name']] = response[['baseType', 'name']]
        response2['stackSize'] = 1
        response = response2
        response['baseType'] = np.where(~(response['name'] == ''),response['name'],response['baseType'])
        del response2

    response.pop('name')

    response = response.rename(columns ={'baseType':'name'})
    
    response.sort_values('name',ascending=False, inplace=True, ignore_index=True)
    

    duplicates = response.duplicated(subset='name')
    dup_count = 1
    for i,duplicate in enumerate(duplicates):
        if duplicate:
            response.loc[i-dup_count,'stackSize'] = int(response.loc[i-dup_count,'stackSize']) + int(response.loc[i,'stackSize'])
            dup_count += 1
        else: dup_count = 1
    response.drop_duplicates('name',inplace=True, ignore_index=True)


    if response.empty:
        logging.warning('FETCHED EMPTY TABLE')
        return False
    logging.info('PROCESSING FINISHED')

    del params, duplicates, dup_count
    return response

def get_all_prices():
    prices = pd.DataFrame()
    logging.info('REQUESTING PRICES FROM POE NINJA (CLIENT SIDE)')
    for i, link in enumerate(apis):
        price = requests.get(link)
        price = price.json()
        price = pd.json_normalize(price['lines'])

        logging.info(f'FETCHED: {i}')

        if i == 0 or i == 3:
            price = price[['currencyTypeName','chaosEquivalent']]
            price.rename(columns= {'currencyTypeName':'name', 'chaosEquivalent':'value'}, inplace=True)
        else:
            price = price[['name','chaosValue']]
            price.rename(columns= {'chaosValue':'value'}, inplace=True)
        prices = pd.concat([prices,price], axis=0)

    
    logging.info('PRICES UPDATED - DONE')

    del price
    return prices

def get_stash_prices(stash,prices, threshold=False):
    logging.info('MATCHING ITEMS LIST WITH POE NINJA PRICES')
    spreadsheet = pd.DataFrame(columns=['name','value', 'stack_size', 'Total_value'])
    for i, row in stash.iterrows():
        value = prices.loc[prices['name'] == row['name']]
        if value.empty: continue
        for v in value['value']:
            value = v
            break
        if pd.notna(row['stackSize']): total_value = value * int(row['stackSize'])
        else: total_value = value

        if threshold:
            if total_value < threshold: continue

        new_row = {'name': row['name'], 'value':value, 'stack_size':row['stackSize'], 'Total_value':total_value}
        new_row = pd.DataFrame(new_row, index=[0])
        spreadsheet = pd.concat([spreadsheet, new_row], ignore_index=True)
        spreadsheet.sort_values('Total_value',ascending=False, inplace=True, ignore_index=True)
    
    logging.info('PRICES MATCHED - DONE')

    del value, total_value, new_row
    return spreadsheet

# %%
