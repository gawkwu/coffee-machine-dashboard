# encoding=utf-8

# === Todo list ===
# Graph: count of consumed supplies
# Make a flask server, allow others can view the website by  their browser.
# Make summary page, should be a overview for all machines and products.
# Make alert tool, to inform user real-time problem.
# User system, switch user to get different view (products and machines).


try:
    # built-in
    from datetime import datetime, date, time
    import os
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
    from connector import SQLiteConnector, connect
except ImportError as err:
    print(err)
    sys.exit(2)

# -------------------------------------------------------------------------------
# Global variables and constants
# -------------------------------------------------------------------------------
APP_PATH = os.path.dirname(os.path.abspath(__file__))
UPDATE_INTERVAL = 1  # sec
today = date(2021, 1, 1)
business_hour = {'open': time(9, 0, 0), 'close': time(21, 0, 0)}
menu = Menu()


# -------------------------------------------------------------------------------
# Functions
# -------------------------------------------------------------------------------
def join_paths(paths):
    """ Return a path string, which combine from given paths. """
    path = ''
    for p in paths:
        path = os.path.join(path, p)
    return path


def init_coffee_machine_data():
    result = dict()
    # connector = SQLiteConnector('coffee-machine-data.db')

    for key, table in [('order', 'coffee_machine_order'), ('state', 'coffee_machine_state')]:
        # df = connector.read_sql_table(table)
        df = connect(table)
        df['datetime'] = pd.to_datetime(df['date'] + ' ' + df['time'])
        df = df.drop(['date', 'time'], axis=1)
        result[key] = df

    return result


coffee_machine_data = init_coffee_machine_data()


def read_machine_df(key, mach_num, start_dt, end_dt):
    if key not in list(coffee_machine_data):
        raise KeyError(f"No dataframe named {key} in coffee-machine-data.")

    df = coffee_machine_data[key]
    if mach_num:
        mask = (df['mach_num'] == mach_num) & (df['datetime'] >= start_dt) & (df['datetime'] < end_dt)
        return df.loc[mask]
    # Default dataframes.
    if key == 'state':
        return pd.DataFrame(columns=df.columns, data=[['2021-01-01', '00:00:00', 0, 0, 0, 0, 0, 0, 0]])
    elif key == 'order':
        return pd.DataFrame(columns=df.columns, data=[['2021-01-01', '00:00:00', '', '', '']])


def create_machine_options():
    """ Return a dict of machines, use shop name as key to get machines belong to it. """
    result = {None: []}
    df = coffee_machine_data['order']
    for shop in df['shop'].unique():
        machines = list(df[df['shop'] == shop]['mach_num'].unique())
        result[shop] = machines
        result[None].extend(machines)
    return result


def reform_options(options):
    """ Return a list of dict that suit dash html components,
    which is reform from given options. """
    return [{'label': i, 'value': i} for i in options]


mach_in_shop = create_machine_options()  # Use 'None' as key will return all machines.
SHOP_OPTIONS = reform_options([i for i in mach_in_shop if i is not None])
MACHINE_OPTIONS = {shop: reform_options(mach_in_shop[shop]) for shop in list(mach_in_shop)}


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
            interval=UPDATE_INTERVAL * 1000,
            n_intervals=0,
        ),
        dcc.Store(id='mach-order-data', storage_type='session'),
        dcc.Store(id='mach-state-data', storage_type='session')
    ], id='internal-content')


def build_filter():
    """ Components let user change web content. """
    return html.Div([
        html.Div(
            dcc.Dropdown(
                id='shop-flt',
                options=SHOP_OPTIONS,
                multi=True
            ), className='navbar-1-item'),
        html.Div([
            dcc.Dropdown(
                id='mach-flt',
                options=MACHINE_OPTIONS[None],
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
                       size=32, color='#333333')
    ], className='navbar-2')


def build_card(title, content):
    """ The container of exhibits, such as graph, value, text, etc. """
    return html.Div([
        html.H4(title),
        content
    ], className='card')


# Build graphs
def get_sales_df(df=None, period=(9, 21)):
    if df is None:  # Return a default dataframe.
        df = pd.DataFrame()
        for choice in menu.Choices:
            dff = pd.DataFrame({
                'time_period': np.arange(period[0], period[1]+1),
                'flavor': choice.name.capitalize(),
                'amount': 0,
                'sales': 0
            })
            df = pd.concat([df, dff])
        return df

    df['time_period'] = df['datetime'].apply(lambda t: t.hour)
    dff = df.drop(['mach_num', 'shop'], axis=1)
    dff = dff.groupby(['time_period', 'flavor']).count()
    dff = dff.rename(columns={'datetime': 'amount'}).reset_index()
    # Except rows in given period, set amount to 0.
    mask = (dff['time_period'] >= period[0]) & (dff['time_period'] < period[1])
    dff.loc[~mask, 'amount'] = 0
    for choice in menu.Choices:
        mask = dff['flavor'] == choice.value
        dff.loc[mask, ['sales']] = dff['amount'] * menu.cost[choice]
    return dff.loc[dff['time_period'] < period[1]]


def get_time_flavor_graph(df):
    """ Return a figure that shows the flavor sales per hour. """
    fig = px.bar(df, x='time_period', y='amount', color='flavor', range_x=[6, 24], range_y=[0, 150],
                 labels={'time_period': 'Time Period', 'amount': 'Amount', 'flavor': 'Flavors'},
                 height=400, template='simple_white')
    fig.update_xaxes(dtick=3, showgrid=True)
    return fig


def get_sales_perf_graph(df, cum=True):
    """ Return a figure that shows the sales performance. """
    df = df.groupby(['time_period']).sum()
    df = df.reset_index().drop(['amount'], axis=1)
    if cum:
        mask = (df['sales'] > 0)
        df.loc[mask, ['sales']] = df.loc[mask, ['sales']].cumsum()
    range_x = [6, 24]
    range_y = [-100, 5000]
    fig = px.line(df, x='time_period', y='sales', range_x=range_x, range_y=range_y,
                  labels={'time_period': 'Time Period', 'sales': 'Sales'},
                  height=400, template='simple_white')
    fig.update_xaxes(dtick=3, showgrid=True)
    fig.update_yaxes(showgrid=True)
    fig.update_traces(mode='markers+lines')
    # Add text and line for sales target
    fig.add_annotation(text='Target', x=range_x[1], y=3000, showarrow=False, bgcolor='salmon')
    fig.add_shape(
        type='line', line_color='salmon', line_width=3, opacity=1, line_dash='dot',
        x0=range_x[0], x1=range_x[1], y0=3000, y1=3000
    )
    # Add text and line for shop's open and close time
    fig.add_annotation(text='Open', x=business_hour['open'].hour, y=range_y[1], showarrow=False)
    fig.add_shape(
        type='line', line_color='gray', line_width=2, opacity=.5,
        x0=business_hour['open'].hour, x1=business_hour['open'].hour, y0=range_y[0], y1=(range_y[1]-200)
    )
    fig.add_annotation(text='Close', x=business_hour['close'].hour, y=range_y[1], showarrow=False)
    fig.add_shape(
        type='line', line_color='gray', line_width=2, opacity=.5,
        x0=business_hour['close'].hour, x1=business_hour['close'].hour, y0=range_y[0], y1=(range_y[1]-200)
    )
    return fig


dcc_graphs = {
    'time_flavor': dcc.Graph(id='fig-time-flavor',
                             figure=get_time_flavor_graph(get_sales_df())),
    'sales_perf': dcc.Graph(id='fig-sales-perf',
                            figure=get_sales_perf_graph(get_sales_df()))
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
        daq.Tank(id='tank-water', label='Water', min=0, max=1600, value=0,
                 scale={'interval': 100, 'labelInterval': 4}),
        daq.Tank(id='tank-milk', label='Milk', min=0, max=1200, value=0,
                 scale={'interval': 100, 'labelInterval': 3}, color='#ffbf80'),
        daq.Tank(id='tank-beans', label='Beans', min=0, max=1000, value=0,
                 scale={'interval': 100, 'labelInterval': 2}, color='#b33c00')
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
def is_changed(html_id_):
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    return html_id_ in changed_id


def is_on_the_hour(time_):
    return (time_.minute + time_.second) == 0


@app.callback(
    Output('start-btn', 'children'),
    Output('interval-component', 'disabled'),
    Input('start-btn', 'n_clicks'),
    State('interval-component', 'disabled')
)
def start_app(start_btn_n, disabled):
    if start_btn_n == 0:
        return 'Start', True
    return 'Stop' if disabled else 'Start', not disabled


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
            opt.extend(MACHINE_OPTIONS[shop])
        return opt
    return MACHINE_OPTIONS[None]


# On click button 'previous' or 'next'.
@app.callback(
    [Output('mach-flt', 'value'), Output('content-title', 'children')],
    Input('mach-prev-btn', 'n_clicks'),
    Input('mach-next-btn', 'n_clicks'),
    Input('mach-flt', 'options'),
    Input('mach-flt', 'value')
)
def update_machine_value(prev_btn, next_btn, mach_opt, mach_val):
    """ Return new machine filter value, when click prev or next button. """
    changed_id = [p['prop_id'] for p in dash.callback_context.triggered][0]
    index = next((i for i, item in enumerate(mach_opt)
                  if item['label'] == mach_val), 0)
    if mach_val is None:
        return [mach_opt[0]['label']] * 2
    if 'mach-prev-btn' in changed_id and index > 0:
        return [mach_opt[index - 1]['label']] * 2
    elif 'mach-next-btn' in changed_id and index < (len(mach_opt) - 1):
        return [mach_opt[index + 1]['label']] * 2
    else:
        return [mach_opt[index]['label']] * 2


# Create callbacks for update each machine data.
def create_refresh_data_callback(df_key_):
    def refresh_mach_data(clock_val, mach_val):
        now = time().fromisoformat(clock_val)
        on_the_hour = (now.minute + now.second) == 0
        if mach_val or on_the_hour:
            data = read_machine_df(df_key_, mach_val,
                                   datetime.combine(today, business_hour['open']),
                                   datetime.combine(today, business_hour['close']))
            data = data.to_json()
            return [data]
        raise PreventUpdate

    return refresh_mach_data


# At interval time.
for df_key in list(coffee_machine_data):
    update_mach_data_func = create_refresh_data_callback(df_key)
    app.callback(
        output=[Output(f'mach-{df_key}-data', 'data')],
        inputs=[Input('clock', 'value'), Input('mach-flt', 'value')],
    )(update_mach_data_func)


# Create callbacks for update machine states.
def create_state_callback(table_head):
    def callback(n, data, clock_val):
        if data:
            df = pd.read_json(data)
            now = datetime.combine(today, time().fromisoformat(clock_val))
            daq_val = list(df.loc[df['datetime'] == now, table_head])
            daq_val = daq_val if daq_val else [0]
            return daq_val
        raise PreventUpdate

    return callback


# At interval time.
for html_id, col_name in convert_of_state_daq[:]:
    update_machine_state_func = create_state_callback(col_name)
    app.callback(
        output=[Output(html_id, 'value')],
        inputs=[Input('interval-component', 'n_intervals'), Input('mach-state-data', 'data')],
        state=[State('clock', 'value')]
    )(update_machine_state_func)


# When on the hour or change mach filter value.
@app.callback(
    Output('fig-time-flavor', 'figure'), Output('fig-sales-perf', 'figure'),
    [Output('led-espresso', 'value'), Output('led-latte', 'value'),
     Output('led-cappuccino', 'value'), Output('led-today', 'value')],
    Input('mach-order-data', 'data'),
    State('clock', 'value'),
)
def update_machine_sales_info(data, clock_val):
    if data:
        now = time().fromisoformat(clock_val)
        period = (business_hour['open'].hour, now.hour)
        sales = get_sales_df(pd.read_json(data), period)
        if sales['amount'].any():
            # Prepare figures
            fig_time_flavor = get_time_flavor_graph(sales)
            fig_sales_perf = get_sales_perf_graph(sales)
            # Prepare counter values
            fla_amount = sales.loc[:, ['flavor', 'amount']].groupby(['flavor']).sum()
            fla_counter = [fla_amount.loc[choice.value][0] for choice in menu.Choices]
            fla_counter += [sum(fla_counter)]
            return fig_time_flavor, fig_sales_perf, *fla_counter
    raise PreventUpdate


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
    print('Launch app server...')
    app.run_server(debug=True)
