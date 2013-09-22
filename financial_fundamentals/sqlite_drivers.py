'''
Created on Aug 21, 2013

@author: akittredge
'''

import numpy as np
import sqlite3

import pytz
import datetime

class SQLiteDriver(object):
    def __init__(self, connection, table, metric):
        connection.row_factory = sqlite3.Row
        self._connection = connection
        self._table = table
        self._metric = metric
        self._ensure_table_exists(connection, table)

    @classmethod
    def _ensure_table_exists(cls, connection, table):
        with connection:
            cursor = connection.cursor()
            cursor.execute(cls._create_stmt.format(table_name=table))
            
class SQLiteTimeseries(SQLiteDriver):
    _create_stmt = '''CREATE TABLE IF NOT EXISTS {table_name}
                    (date timestamp, symbol text, metric text, value real);
                 '''
    _create_index_stmt = '''
                        CREATE INDEX IF NOT EXISTS 
                        time_series_index ON {table_name} (date, symbol, metric);
                        '''

    @classmethod
    def _ensure_table_exists(cls, connection, table):
        super(cls, SQLiteTimeseries)._ensure_table_exists(connection,
                                                          table)
        with connection:
            cursor = connection.cursor()
            cursor.execute(cls._create_index_stmt.format(table_name=table))

    _get_query = '''SELECT value, date from {} 
                    WHERE symbol = ?
                    AND date BETWEEN ? AND ?
                    AND metric =  ?
                '''
    def get(self, symbol, dates):
        '''return all stored symbol metric values for dates between min(dates) and max(dates).
        
        '''
        with self._connection:
            qry = self._get_query.format(self._table)
            cursor = self._connection.cursor()
            args = [symbol, min(dates), max(dates), self._metric]
            cursor.execute(qry, args)
            for row in cursor.fetchall():
                #should be equivalent to but faster than  
                # date = datetime.datetime.strptime(row['date'], '%Y-%m-%d %H:%M:%S+00:00')
                date = datetime.datetime(*map(int, row['date'][:11].split('-')),
                                         tzinfo=pytz.UTC)
                value = np.float(row['value'])
                yield date, value
       
    _insert_query = 'INSERT INTO {} (symbol, date, metric, value) VALUES (?, ?, ?, ?)'
    def set(self, symbol, records):
        '''records is a sequence of date, value items.'''
        with self._connection:
            for date, value in records:
                args = (symbol, date, self._metric, value)
                self._connection.execute(self._insert_query.format(self._table), 
                                         args)
    
class SQLiteIntervalseries(SQLiteDriver):
    _create_stmt = '''CREATE TABLE IF NOT EXISTS {table_name} 
                        (start timestamp, 
                        end timestamp, 
                        symbol text, 
                        metric text, 
                        value real)
                    '''
    _get_qry = '''SELECT value FROM {} 
                    WHERE metric = ? AND symbol = ? AND start <= ? AND ? <= end
                    '''
    def get(self, symbol, date):
        '''return the metric value of symbol on date.'''
        qry = self._get_qry.format(self._table)
        with self._connection:
            row = self._connection.execute(qry, (self._metric,
                                                 symbol,
                                                 date,
                                                 date)).fetchone()
        return row and (np.float(row['value']) if row['value'] else np.NaN)

    _insert_query = '''INSERT INTO {} 
                        (symbol, start, end, metric, value) VALUES (?, ?, ?, ?, ?)
                        '''
    def set_interval(self, symbol, start, end, value):
        '''set value for interval start and end.'''
        qry = self._insert_query.format(self._table)
        with self._connection:
            self._connection.execute(qry, (symbol, start, end, 
                                           self._metric, value))
        