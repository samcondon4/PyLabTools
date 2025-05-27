""" slt_db
"""
import pymysql
import sshtunnel
import sqlalchemy
import urllib.parse
import pandas as pd


class SltDb:
    ssh_host = ''
    ssh_username = ''
    ssh_password = ''
    remote_bind_address = ()

    db_host = ''
    db_name = ''
    db_username = ''
    db_password = ''

    dtypes = {
        'RecordGroup': sqlalchemy.String(255),
        'RecordGroupInd': sqlalchemy.String(255),
        'RecordRow': sqlalchemy.String(255)
    }

    def __init__(self):
        self.tunnel = None
        self.engine = None

    def connect(self):
        # - Open the ssh connection ------------------------------------------------------------------------------ #
        self.tunnel = sshtunnel.SSHTunnelForwarder(
            (self.ssh_host, 22),
            ssh_username=self.ssh_username,
            ssh_password=self.ssh_password,
            remote_bind_address=self.remote_bind_address
        )
        self.tunnel.start()

        # - Create the sqlalchemy engine ------------------------------------------------------------------------- #
        engine_str = 'mysql+pymysql://%s:%s@%s:%s/%s' % (
            self.db_username, urllib.parse.quote_plus(self.db_password), self.db_host, self.tunnel.local_bind_port,
            self.db_name
        )
        self.engine = sqlalchemy.create_engine(engine_str)

    def close(self):
        """ Close the ssh connection on the SLT database.
        """
        self.tunnel.close()

    def query(self, query_string, table, filter_str=None):
        """ Run a query on the SLT database.

        :param query_string: String of the sql query to run.
        :param table: String identifying the table to query.
        :param filter_str: String to filter the basic sql query.
        """
        query_str = '%s from %s' % (query_string, table)
        query_str += filter_str if filter_str is not None else ''
        df = pd.read_sql_query(query_str, self.engine)
        return df

    def query_speccal(self, query_string, filter_str=None):
        """ Wrapper around *query* to run a query on the 'spectral_cal' table.
        """
        query_str = '%s from spectral_cal' % query_string
        query_str += f' {filter_str}' if filter_str is not None else ''
        df = pd.read_sql_query(query_str, self.engine)
        return df

    def append(self, table, append_df):
        """ Append a dataframe to the specified table. RecordGroup, RecordGroupInd, and RecordRow are modified to match
        the current state and format of the table keys.

        :param table: Table to append the dataframe to.
        :param append_df: Dataframe to append.
        """
        # - normalize the append_df RecordGroup values --------------------------------------------- #
        append_df.RecordGroup -= append_df.RecordGroup.min()

        # - get the latest record group ------------------------------------------------------------ #
        rg_query = 'select RecordGroup from %s ORDER BY RecordGroup DESC LIMIT 1' % table
        latest_rg = pd.read_sql_query(rg_query, self.engine).RecordGroup.values[0]
        latest_rg_char, latest_rg_int = latest_rg.split('_')
        latest_rg_int = int(latest_rg_int)

        # - set the append_df RecordGroup, RecordGroupInd, and RecordRow values -------------------- #
        rg_apply = lambda rg, **kwargs: '_'.join([latest_rg_char, '%06i' % (latest_rg_int + rg + 1)])
        append_df.RecordGroup = append_df.RecordGroup.apply(rg_apply, axis=1)

        rgi_rr_apply = lambda val, **kwargs: '%06i' % val
        append_df.RecordGroupInd = append_df.RecordGroupInd.apply(rgi_rr_apply, axis=1)
        append_df.RecordRow = append_df.RecordRow.apply(rgi_rr_apply, axis=1)

        append_df.set_index(['RecordGroup', 'RecordGroupInd', 'RecordRow'], inplace=True)

        # - append the dataframe to the existing table --------------------------------------------- #
        append_df.to_sql(table, self.engine, if_exists='append', dtype=self.dtypes)

    def append_speccal(self, append_df):
        """ Wrapper around *append* for the 'spectral_cal' table.

        :param append_df: Dataframe to append.
        """
        pass

    def get_col_diff(self, table, df):
        """ Check the difference in columns between the specified table and the passed in dataframe.

        :param table: Database table to check.
        :param df: Dataframe to check against.
        """
        # - get the latest record from the table -------------------------------------- #
        last_query = 'select * from %s ORDER BY timestamp DESC LIMIT 1' % table
        table_cols = list(pd.read_sql_query(last_query, self.engine).columns)
        df_cols = list(df.columns)
        col_diff = {
            'table - df': [tcol for tcol in table_cols if tcol not in df_cols],
            'df - table': [dfcol for dfcol in df_cols if dfcol not in table_cols]
        }

        return col_diff
