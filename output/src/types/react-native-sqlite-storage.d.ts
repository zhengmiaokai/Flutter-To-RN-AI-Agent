declare module 'react-native-sqlite-storage' {
  namespace SQLite {
    interface SQLiteDatabase {
      executeSql(sql: string, params?: any[]): Promise<[SQLiteResultSet]>;
      close(): Promise<void>;
    }

    interface SQLiteResultSet {
      rows: SQLiteResultSetRowList;
    }

    interface SQLiteResultSetRowList {
      length: number;
      item(index: number): any;
    }
  }

  var SQLite: {
    enablePromise(enable: boolean): void;
    openDatabase(params: { name: string; location: string }): Promise<SQLite.SQLiteDatabase>;
  };

  export default SQLite;
}
