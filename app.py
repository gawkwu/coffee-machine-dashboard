# encoding=utf-8

# === Todo list ===
# Graph: sales performance
# Graph: count of consumed supplies
# Make a flask server, allow others can view the website by  their browser.
# Make summary page, should be a overview for all machines and products.
# Make alert tool, to inform user real-time problem.
# User system, switch user to get different view (products and machines).


try:
    # built-in
    from datetime import date, time
    import os
    import pathlib
    import sys
    # extend lib
    import numpy as np
    import pandas as pd
    # extend lib: dash
    import dash
    import dash_core_components as dcc
    import dash_html_components as html
    import dash_daq as daq
    from dash.dependencies import Input, Output, State
    from dash.exceptions import PreventUpdate
    import plotly.express as px
    # local lib
    from coffeemachine import Menu
except ImportError as err:
    print(err)
    sys.exit(2)


APP_PATH = str(pathlib.Path(__file__).parent.resolve())
mach_df = pd.read_csv(os.path.join(APP_PATH, os.path.join('assets', 'machines.csv')))
menu = Menu()
date_stamp = date(2021, 1, 1).isoformat()
update_interval = 1  # sec


# -------------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------------
def join_paths(paths):
    """ Return a path string, which combine from given paths. """
    path = ''
    for p in paths:
        path = os.path.join(path, p)
    return path


def read_machine_state(mach_num, date_str):
    """ Return machine states data, which is read from server. """
    if mach_num and date_str:
        df = pd.read_csv(join_paths([APP_PATH, 'assets', mach_num, 'state', f'state_{date_str}.csv']))
        print(df.head(5))
        return df
    # Default dataframe with 0 values.
    return pd.DataFrame(
        columns=['date', 'time', 'total_count', 'today_count', 'tank_beans',
                 'tank_water', 'tank_milk', 'barometer', 'thermometer'],
        data=[['2021-01-01', '00:00:00', 0, 0, 0, 0, 0, 0, 0]]
    )


def read_machine_order(mach_num, date_str):
    """ Return machine price data, which is read from server. """
    df = pd.read_csv(join_paths([APP_PATH, 'assets', mach_num, 'order', f'order_{date_str}.csv']))
    print(df.head(5))
    return df


def get_machine_options(shop=None):
    """ Return a list of machines, which is filtered by given shop. """
    if shop:
        return mach_df[mach_df['shop'] == shop]['machine'].unique()
    return mach_df['machine'].unique()


def reform_options(options):
    """ Return a list of dict that suit dash html components,
    which is reform from given options. """
    return [{'label': i, 'value': i} for i in options]


shops = mach_df['shop'].unique()
option_map = {shop: reform_options(get_machine_options(shop)) for shop in shops}
option_map[None] = reform_options(get_machine_options())


# HTML component generators
# About the function name :
# * "build_..." means return is a "dash html component",
#   can put in app.layout directly.
# * "generate_..." means return is a "list of dash html components",
#   can not put in app.layout directly, should wrap in a html component.
def build_internal_content():
    """ Components run in background, for web app's operation. """
    return html.Div([
        dcc.Interval(
            id='interval-component',
            interval=update_interval * 1000,
            n_intervals=0,
            disabled=True
        ),
        dcc.Store(id='mach-sales-data', storage_type='session'),
        dcc.Store(id='mach-state-data', storage_type='session')
    ], id='internal-content')


def build_filter():
    """ Components let user change web content. """
    return html.Div([
        html.Div(
            dcc.Dropdown(
                id='shop-flt',
                options=reform_options(mach_df['shop'].unique()),
                multi=True
            ), className='navbar-1-item'),
        html.Div([
            dcc.Dropdown(
                id='mach-flt',
                options=reform_options(mach_df['machine'].unique()),
                clearable=False
            ),
            html.Div([
                html.Button('<', id='mach-prev-btn'),
                html.Button('>', id='mach-next-btn')
            ], className='mach-flt-btns')
        ], className='navbar-1-item dir-row')
    ], className='navbar-1')


def build_clock():
    """ Display a pseudo clock, for better understand web's work.
    (Apply in demonstration only) """
    return html.Div([
        daq.LEDDisplay(id='clock', label='Pseudo Clock', value='00:00:00',
                       size='32', color='#333333')
    ], className='navbar-2')


def build_card(title, content):
    """ The container of exhibits, such as graph, value, text, etc. """
    return html.Div([
        html.H4(title),
        content
    ], className='card')


# Build graphs
def get_flavors_at_hour(df, clock):
    """ Return a count result of each flavor. """
    dff = df.loc[:, ['time', 'flavor']]
    clock_str = str(clock).rjust(2, '0')
    mask = dff['time'].str.startswith(clock_str)
    result = dff[mask].groupby('flavor').count()
    result = result.reset_index()
    result = result.rename(columns={'time': 'amount'})
    result['time_period'] = clock
    return result


def create_mach_sales_data():
    """ Return a empty dataframe of sales performance. """
    df = pd.DataFrame()
    for choice in menu.Choices:
        dff = pd.DataFrame({
            'time_period': np.arange(9, 22, 1),
            'flavor': choice.name.capitalize(),
            'price': menu.cost[choice],
            'amount': 0,
            'sales': 0
        })
        df = pd.concat([df, dff])
    return df


def update_mach_sales_data(order, start, end):
    """ Return a updated sales performance data. """
    df = create_mach_sales_data()
    for clock in range(start, end):
        df = pd.merge(df, get_flavors_at_hour(order, clock),
                      how='left', on=['time_period', 'flavor'],
                      suffixes=('', '_y'), copy=False)
        df['amount'] += df['amount_y'].fillna(0).astype('int64')
        df = df.drop(['amount_y'], axis=1)
    df['sales'] = df['price'] * df['amount']
    return df


def get_flavor_count(sales_data):
    """ Return a dict of sales of flavor. """
    result = {}
    for choice in menu.Choices:
        choice_name = choice.name.capitalize()
        mask = sales_data['flavor'] == choice_name
        result[choice_name] = sales_data[mask]['amount'].sum()
    return result


def get_time_flavor_graph(df):
    """ Return a figure that shows the flavor sales per hour. """
    return px.bar(df, x='time_period', y='amount', color='flavor',
                  range_y=[0, 150])


def get_sales_count(sales_data):
    """ Return a dict of sales performance. """
    data = sales_data.loc[:, ('time_period', 'sales')]
    data = data.groupby('time_period').sum()
    data['sales'] = data['sales'].cumsum()
    data = data.reset_index()
    return data


def get_sales_perf_graph(df):
    """ Return a figure that shows the sales performance. """
    return px.line(df, x='time_period', y='sales', range_y=[0, 10000])


dcc_graphs = {
    'time_flavor': dcc.Graph(id='fig-time-flavor',
                             figure=get_time_flavor_graph(create_mach_sales_data())),
    'sales_perf': dcc.Graph(id='fig-sales-perf',
                            figure=get_sales_perf_graph(create_mach_sales_data()))
}

daq_dict = {
    'gradbar': [
        daq.GraduatedBar(id='gradbar-target', label='Target', value=0),
        daq.GraduatedBar(id='gradbar-current', label='Current', value=0)
    ],
    'led': [
        daq.LEDDisplay(id='led-today', label='Today', value=0),
        daq.LEDDisplay(id='led-espresso', label='Espresso', value=0),
        daq.LEDDisplay(id='led-latte', label='Latte', value=0),
        daq.LEDDisplay(id='led-cappuccino', label='Cappuccino', value=0)
    ],
    'tank': [
        daq.Tank(id='tank-water', label='Water', min=0, max=1600, value=0),
        daq.Tank(id='tank-milk', label='Milk', min=0, max=1200, value=0,
                 color='#ffbf80'),
        daq.Tank(id='tank-beans', label='Beans', min=0, max=1000, value=0,
                 color='#b33c00')
    ],
    'gauge': [
        daq.Gauge(id='gauge-bar', label='Barometer', min=0, max=30, value=0,
                  color='#4d88ff', units='Bar', showCurrentValue=True,
                  scale={'start': 0, 'interval': 1, 'labelInterval': 5}),
        daq.Gauge(id='gauge-temp', label='Thermometer', min=0, max=120, value=0,
                  color='#ff6666', units='°C', showCurrentValue=True,
                  scale={'start': 0, 'interval': 5, 'labelInterval': 2})
    ]
}
# For reference, which is: (HTML_ID, DATA_COLUMN_NAME)
convert_of_state_daq = [
    ('tank-water', 'tank_water'), ('tank-milk', 'tank_milk'),
    ('tank-beans', 'tank_beans'), ('gauge-bar', 'barometer'),
    ('gauge-temp', 'thermometer')
]

# -------------------------------------------------------------------------------
# Styles and CSS
# -------------------------------------------------------------------------------
external_stylesheets = [
    'https://codepen.io/chriddyp/pen/bWLwgP.css',
    {
        "href": "https://fonts.googleapis.com/css2?family=Noto+Sans&display=swap",
        "rel": "stylesheet"
    },
    '/assets/style.css'
]

# -------------------------------------------------------------------------------
# Web app
# -------------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
server = app.server
app.config.suppress_callback_exceptions = True

app.title = "Coffee Machine Espresso"
app.layout = html.Div([
    build_internal_content(),

    # Navigation bar
    html.Div([
        build_filter(),
        html.Button('Start', id='start-btn'),
        build_clock()
    ], className='navbar'),

    # Content
    html.Div([
        html.H3("Title", id='content-title'),
        # Left column, mainly for plots and tables.
        html.Div([
            build_card(
                'Counters',
                html.Div([
                    html.Div(daq_dict['led'], className='led')
                ])
            ),
            build_card('Flavor Sales Per Hour', html.Div(dcc_graphs['time_flavor'])),
            build_card('Sales Performance', html.Div(dcc_graphs['sales_perf']))
        ], className='left-col'),
        # Right column, mainly for states, comment, small figure, etc.
        html.Div([
            build_card('Tanks', html.Div(daq_dict['tank'], className='tank')),
            build_card('Gauges', html.Div(daq_dict['gauge'], className='gauge'))
        ], className='right-col'),
    ], id='content'),
])


# -------------------------------------------------------------------------------
# Callbacks
# -------------------------------------------------------------------------------
@app.callback(
    Output('start-btn', 'children'),
    Output('interval-component', 'disabled'),
    Input('start-btn', 'n_clicks'),
    State('start-btn', 'children'),
    State('interval-component', 'disabled')
)
def start_app(start_btn, start_btn_val, disabled):
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    if 'start-btn' in changed_id:
        start_btn_val = 'Stop' if start_btn_val == 'Start' else 'Start'
        disabled = not disabled
        return start_btn_val, disabled
    else:
        raise PreventUpdate


# On change shop filter.
@app.callback(
    Output('mach-flt', 'options'),
    Input('shop-flt', 'value')
)
def update_machine_options(shop_list):
    """ Return new machine option list, when change shop filter. """
    if shop_list:
        opt = []
        for shop in shop_list:
            opt.extend(option_map[shop])
        return opt
    return option_map[None]


# On click button 'previous' or 'next'.
@app.callback(
    [Output('mach-flt', 'value'), Output('content-title', 'children')],
    Input('mach-prev-btn', 'n_clicks'),
    Input('mach-next-btn', 'n_clicks'),
    Input('mach-flt', 'options'),
    State('mach-flt', 'value')
)
def update_machine_value(prev_btn, next_btn, mach_opt, mach_val):
    """ Return new machine filter value, when click prev or next button. """
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    index = next((i for i, item in enumerate(mach_opt)
                  if item['label'] == mach_val), 0)
    if 'mach-prev-btn' in changed_id and index > 0:
        return [mach_opt[index - 1]['label']] * 2
    elif 'mach-next-btn' in changed_id and index < (len(mach_opt) - 1):
        return [mach_opt[index + 1]['label']] * 2
    return [mach_opt[0]['label']] * 2


# On change machine filter value.
@app.callback(
    Output('mach-state-data', 'data'),
    Input('mach-flt', 'value'),
    State('mach-state-data', 'data')
)
def load_mach_state(mach_val, data):
    """ Read data of current machine state from server to session. """
    data = read_machine_state(mach_val, date_stamp)
    data = data.set_index('time')
    data = data.to_dict(orient='index')
    return data


# Create callbacks for update machine states.
def create_state_callback(th):
    def callback(n, clock_val, data):
        try:
            daq_val = data[clock_val][th]
        except (KeyError, TypeError):
            raise PreventUpdate
        return [daq_val]

    return callback


for html_id, col_name in convert_of_state_daq:
    update_machine_state_func = create_state_callback(col_name)
    app.callback(
        output=[Output(html_id, 'value')],
        inputs=[Input('interval-component', 'n_intervals')],
        state=[State('clock', 'value'), State('mach-state-data', 'data')]
    )(update_machine_state_func)


# On change machine filter value.
@app.callback(
    Output('mach-sales-data', 'data'),
    Input('mach-flt', 'value'),
    State('mach-sales-data', 'data')
)
def load_machine_sales(mach_val, data):
    """ Read data of current machine's sales from server to session. """
    data = read_machine_order(mach_val, date_stamp)
    data = data.to_dict(orient='index')
    return data


@app.callback(
    [Output('fig-time-flavor', 'figure'),
     Output('fig-sales-perf', 'figure'),
     Output('led-today', 'value'), Output('led-espresso', 'value'),
     Output('led-latte', 'value'), Output('led-cappuccino', 'value')],
    Input('interval-component', 'n_intervals'),
    State('clock', 'value'),
    State('mach-sales-data', 'data')
)
def update_machine_graphs(n, clock_val, data):
    try:
        order = pd.DataFrame.from_dict(data, orient='index')
        clock = time.fromisoformat(clock_val).hour
        if 9 < clock < 23:
            data = update_mach_sales_data(order, 9, clock)
        else:
            data = create_mach_sales_data()
    except (ValueError, TypeError) as e:
        print('Function "update_machine_graphs": ', e)
        raise PreventUpdate

    # Prepare output data
    fla = get_flavor_count(data)
    output = [
        get_time_flavor_graph(data),
        get_sales_perf_graph(get_sales_count(data)),
        sum(fla.values()), fla['Espresso'],
        fla['Latte'], fla['Cappuccino']
    ]
    return output


# At interval time.
@app.callback(
    Output('clock', 'value'),
    # Output('interval-component', 'disabled'),
    Input('interval-component', 'n_intervals'),
)
def update_pseudo_time(n):
    """ Return a new time that increase by interval.
    (Apply in demonstration only) """
    # Normal version
    # h, m = (n // 60), (n % 60)
    # disabled = True if h > 21 else False
    # return time(9+h, 0+m).strftime('%H:%M:%S'), disabled

    # Debug/Demo version, boost time flow (x10)
    h = 13 if n > 72 else (n // 6)
    m = 0 if n > 72 else ((n * 10) % 60)
    # disabled = True if h > 12 else False
    return time(9 + h, 0 + m).strftime('%H:%M:%S')  # , disabled


if __name__ == '__main__':
    app.run_server()
