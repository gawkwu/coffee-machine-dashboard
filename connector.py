import os
import sqlite3
import psycopg2
import pandas as pd


APP_PATH = os.path.dirname(os.path.abspath(__file__))
DATABASE_DIR = os.path.join(APP_PATH, 'data')
DATABASE_NAME = 'coffee-machine-data.db'
DATABASE_TABLES = ['coffee_machine_order', 'coffee_machine_state']


class SQLiteConnector:
    def __init__(self, db_name):
        self.db_name = db_name

    def read_sql_table(self, table_name, index_col=None, columns=None):
        conn, result = None, None
        try:
            conn = sqlite3.connect(self.db_name)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            columns = '*' if columns is None else columns
            query = f'SELECT {columns} FROM {table_name}'
            cur.execute(query)
            index_col = cur.fetchone().keys() if index_col is None else index_col
            result = pd.DataFrame(data=cur.fetchall(), columns=index_col)
            cur.close()
        except Exception as error:
            print(error)
        finally:
            if conn is not None:
                conn.close()
            return result


def connect():
    DATABASE_URL = os.environ['DATABASE_URL']
    conn = None
    try:
        print('Connecting to PostgreSQL database server...')
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        cur = conn.cursor()
        print('PostgreSQL database version:')
        cur.execute('SELECT version()')
        db_version = cur.fetchone()
        print(db_version)
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(error)
    finally:
        if conn is not None:
            conn.close()
            print('Database connection closed.')
