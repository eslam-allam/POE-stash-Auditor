import PySimpleGUI as sg
import poe_auditor
import logging
import pandas as pd
import traceback



logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S', handlers=[])
token_file = './token.txt'
logging.getLogger('selenium').propagate = False
mylogs = logging.getLogger()

file = logging.FileHandler("program_logs.log",encoding='utf-8')
file.setLevel(logging.INFO)
fileformat = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s',datefmt='%Y-%m-%d %H:%M:%S')
file.setFormatter(fileformat)
mylogs.addHandler(file)

class Handler(logging.StreamHandler):

    def __init__(self):
        logging.StreamHandler.__init__(self)

    def emit(self, record):
        global buffer
        message = f'{record.asctime} {record.levelname:<10}{record.getMessage()}'
        buffer = f'{buffer}\n{message}'
        window['log'].update(value=buffer)

buffer = ''
ch = Handler()
mylogs.addHandler(ch)


leagues = list(poe_auditor.get_leagues().values())
stashes = []
token = ''
prices = None
stashesdf= None
selected = ''
console = False

def change_color(index,color, listBox_key):
    listbox = window[listBox_key].Widget
    listbox.itemconfigure(index, bg=color, fg='black')

table_headings = ['      Name      ', 'Value', 'Stack size', 'Total value']
table = sg.Table(values=[], headings=table_headings,
                                    max_col_width=200,
                                    col_widths=(50,2,2,11),
                                    justification='left',
                                    num_rows=10, key='_pricesTable_', expand_x=True, expand_y=True,  size=(300,50))
sg.theme('DarkBlue')   # Add a touch of color
# All the stuff inside your window.
layout = [  [sg.Button('Get Token',expand_x=True), sg.Button('Show/Hide console',expand_x=True)],
            [sg.Text('League: ', font=('font', 15, 'bold'))],
            [sg.Listbox(leagues, default_values='Standard', size=(100,4), enable_events=False, key='_LIST_', font=('font', 10,'roman'), expand_x=True)],
            [sg.Button('Ok', expand_x=True), sg.Button('Exit', expand_x=True)],
            [sg.Listbox(values=stashes, select_mode='extended', key='fac', size=(30, 6),expand_x=True, font=('Verdana', 11,'normal'))], 
            [sg.Button('Get Prices', auto_size_button=True) , sg.Text('Threshold: '),sg.InputText()],
            [table],
            [sg.Multiline(size=(100,6), key='log', expand_x=True, visible=False, autoscroll=True, auto_refresh=True, disabled=True)] ]

# Create the Window
window = sg.Window('POE Stash Auditor', layout, finalize=True)

token = poe_auditor.get_token(token_file)

# Event Loop to process "events" and get the "values" of the inputs
while True:
    try:
        event, values = window.read(20)
        
        if event == sg.WIN_CLOSED or event == 'Exit': # if user closes window or clicks cancel
            break
        if event == 'Get Token':
            token = poe_auditor.get_token(token_file)
        if event == 'Ok':
            selected = values['_LIST_']
            stashesdf = poe_auditor.get_stash_list(token, selected)
            if type(stashesdf) == str: 
                token = stashesdf
                continue
            if type(stashesdf) == bool:
                continue
            prices = poe_auditor.get_all_prices()
            stashes = stashesdf['name']
            colors = stashesdf['colour']
            window['fac'].update(stashes)
            for i, color in enumerate(colors):
                color = str(color)
                if len(color) < 6:
                    zeroes = 6 - len(color)
                    color = color + '0'*zeroes
                change_color(i, f'#{color}', 'fac')
        
        if event == 'Get Prices':
            id=stashesdf[stashesdf['name']==values["fac"][0]]['id'].values[0]
            tab = poe_auditor.get_stash_items(token, selected, id)
            
            if values[0]:
                try:
                    threshold = float(values[0])
                    stashprices = poe_auditor.get_stash_prices(tab, prices, threshold)
                except:
                    logging.warning('THRESHOLD NEEDS TO BE A NUMBER')
                    window[0].update('')
                    continue
            else:
                stashprices = poe_auditor.get_stash_prices(tab, prices)
            
            priceslist = stashprices.values.tolist()
            window['_pricesTable_'].update(priceslist)

        if event == 'Show/Hide console':
            if console:
                window['log'].update(visible= False)
                window['log'].hide_row()
                console = False
            else:
                window['log'].update(visible= True)
                window['log'].unhide_row()
                console = True
    except Exception as e:
        logging.error(traceback.format_exc())

window.close()