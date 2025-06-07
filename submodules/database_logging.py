import sqlite3
import pandas as pd
from PyQt5 import QtCore
from datetime import datetime
from PyQt5.QtCore import pyqtSignal


class DataBaseLog(QtCore.QObject):

    signal_request_dataframe = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.database = sqlite3.connect('database/warnings_sql.db')     # connect to database
        self.sql_cursor = self.database.cursor()                    # create cursor
        self.create_table()
        # self.read_all_rows_database()

    def create_table(self):
        """ This function creates table in database if it not exists """
        self.sql_cursor.execute("""CREATE TABLE IF NOT EXISTS warnings_table (
            date TEXT,
            time TEXT,
            name TEXT,
            angle INT
        )""")
        self.database.commit()      # confirm

    def append_table(self, data: list):
        for i in range(len(data)):
            self.sql_cursor.execute("INSERT INTO warnings_table VALUES (?, ?, ?, ?)",
                                    (data[i]['date'], data[i]['time'], data[i]['name'], data[i]['angle']))
            self.database.commit()

    def read_all_rows_database(self):
        # self.sql_cursor.execute("""SELECT * FROM warnings_table""")
        # rows = self.sql_cursor.fetchall()
        # for row in rows:
        #     print(row)
        query = """SELECT * FROM warnings_table"""
        result_df = pd.read_sql_query(query, self.sql_cursor.connection)
        # print(result_df)

    def get_data_from_database(self, cur_date: str, cur_time: str):
        """ This function convert selected time (cur_time) to datetime objects: start_time and end_time.
         Then read data from DataBase by request based on selected date (cur_date) and convert it to
          pandas dataframe. Then convert time from dataframe to datetime objects and check if every time is in
          range of start_time and end_time -- filtering time. Then dataframe from sql-request filtered by this
          filtered time and send pandas dataframe to DataBase Table """
        time_column = []
        filtered_time = []

        query = f"""SELECT * FROM warnings_table WHERE date = '{cur_date}'"""
        result_df = pd.read_sql_query(query, self.sql_cursor.connection)

        if cur_time != '24/7':
            start_time = datetime.strptime(cur_time, '%H:%M:%S')
            end_time = datetime.strptime((str(start_time.hour) + ':59:59'), '%H:%M:%S')

            time_column_from_DB = list(result_df['time'])

            for value in time_column_from_DB:
                time_datetime = datetime.strptime(value, '%H:%M:%S')
                time_column.append(time_datetime)

            for value in time_column:
                if start_time <= value <= end_time:
                    filtered_time.append(str(value.time()))

            filtered_df = result_df[result_df['time'].isin(filtered_time)]
        else:
            filtered_df = result_df

        self.signal_request_dataframe.emit(filtered_df)
