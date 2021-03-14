import os
import sqlite3
import psycopg2
import pandas as pd


APP_PATH = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(APP_PATH, 'data')
DATABASE_NAME = 'coffeemachine.db'
DATABASE_TABLES = ['machine_order', 'machine_state']


def read_from_sqlite(table_name, columns=None, index_col=None):
    conn, result = None, None
    columns = '*' if columns is None else columns
    try:
        with sqlite3.connect(DATABASE_NAME) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            query = f'SELECT {columns} FROM {table_name}'
            cur.execute(query)
            index_col = cur.fetchone().keys() if index_col is None else index_col
            result = pd.DataFrame(data=cur.fetchall(), columns=index_col)
            cur.close()
    except Exception as error:
        print(error)
    finally:
        return result


def read_from_postgres(table_name, columns=None):
    db_url = os.environ['DATABASE_URL']
    result = None
    columns = '*' if columns is None else columns
    try:
        with psycopg2.connect(db_url, sslmode='require') as conn:
            query = f'SELECT {columns} FROM {table_name}'
            result = pd.read_sql_query(query, conn)
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        return result
