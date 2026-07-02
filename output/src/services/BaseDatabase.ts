import SQLite from 'react-native-sqlite-storage';

SQLite.enablePromise(true);

interface DatabaseProtocol {
  creatDB(file: string): Promise<void>;
  createTable(table: string, keyTypes: Record<string, string>, isPRIMARY: boolean): Promise<void>;
  insert(table: string, values: Record<string, any>): Promise<void>;
  rawInsert(query: string, params?: any): Promise<void>;
  update(table: string, values: Record<string, any>, where?: string, whereArgs?: any[]): Promise<void>;
  rawUpdate(query: string): Promise<void>;
  query(table: string, where?: string, whereArgs?: any[]): Promise<any[]>;
  rawQuery(query: string): Promise<any[]>;
  delete(table: string): Promise<void>;
  rawDelete(query: string): Promise<void>;
  close(): Promise<void>;
}

class BaseDatabase implements DatabaseProtocol {
  private database!: SQLite.SQLiteDatabase;

  async creatDB(file: string): Promise<void> {
    this.database = await SQLite.openDatabase({ name: file, location: 'default' });
  }

  /* 数据类型：INTEGER TEXT DOUBLE LONG SINGLE */
  async createTable(table: string, keyTypes: Record<string, string>, isPRIMARY: boolean): Promise<void> {
    let queryParams = isPRIMARY ? 'id INTEGER PRIMARY KEY' : '';
    for (const key of Object.keys(keyTypes)) {
      const value = keyTypes[key];
      queryParams += `, ${key} ${value}`;
    }
    const query = `CREATE TABLE IF NOT EXISTS ${table} (${queryParams})`;
    await this.database.executeSql(query);
  }

  async insert(table: string, values: Record<string, any>): Promise<void> {
    const keys = Object.keys(values);
    const placeholders = keys.map(() => '?').join(', ');
    const params = keys.map((k) => values[k]);
    const sql = `INSERT INTO ${table} (${keys.join(', ')}) VALUES (${placeholders})`;
    await this.database.executeSql(sql, params);
  }

  /*
  调用示例
  this.rawInsert('dbTable', {'name': 'lilylin', 'age': 27, 'enjoy': '踢足球，跑步，炒菜等等'});
  this.rawInsert('insert into dbTable (name, age, enjoy) VALUES (?, ?, ?)', ['lilylin', 27, '踢足球，跑步，炒菜等等']);
  this.rawInsert('insert into dbTable (name, age, enjoy) VALUES ("lilylin", 27, "踢足球，跑步，炒菜等等")');
  */
  async rawInsert(query: string, params?: any): Promise<void> {
    if (params !== undefined) {
      if (typeof params === 'object' && !Array.isArray(params)) {
        // 参数为 Map 时自动生成 INSERT 语句
        const map: Record<string, any> = params;
        const keys = Object.keys(map);
        const values = Object.values(map);
        const placeholders = keys.map(() => '?').join(', ');
        const table = query;
        const sql = `INSERT INTO ${table} (${keys.join(', ')}) VALUES (${placeholders})`;
        await this.database.executeSql(sql, values);
      } else if (Array.isArray(params)) {
        // 参数为 List 时直接作为参数化查询参数
        await this.database.executeSql(query, params);
      } else {
        console.log('rawInsert:====插入数据格式有误');
      }
    } else {
      await this.database.executeSql(query);
    }
  }

  async update(
    table: string,
    values: Record<string, any>,
    where?: string,
    whereArgs?: any[],
  ): Promise<void> {
    const setClause = Object.keys(values)
      .map((key) => `${key} = ?`)
      .join(', ');
    const params = Object.values(values);
    let sql = `UPDATE ${table} SET ${setClause}`;
    if (where) {
      sql += ` WHERE ${where}`;
      if (whereArgs && whereArgs.length > 0) {
        params.push(...whereArgs);
      }
    }
    await this.database.executeSql(sql, params);
  }

  async rawUpdate(query: string): Promise<void> {
    await this.database.executeSql(query);
  }

  async query(table: string, where?: string, whereArgs?: any[]): Promise<any[]> {
    let sql = `SELECT * FROM ${table}`;
    if (where) {
      sql += ` WHERE ${where}`;
    }
    const params = whereArgs && whereArgs.length > 0 ? whereArgs : [];
    const [results] = await this.database.executeSql(sql, params);
    const list: any[] = [];
    for (let i = 0; i < results.rows.length; i++) {
      list.push(results.rows.item(i));
    }
    return list;
  }

  async rawQuery(query: string): Promise<any[]> {
    const [results] = await this.database.executeSql(query);
    const list: any[] = [];
    for (let i = 0; i < results.rows.length; i++) {
      list.push(results.rows.item(i));
    }
    return list;
  }

  async delete(table: string): Promise<void> {
    // 原 Dart 实现两次 delete，为保留逻辑照做
    await this.database.executeSql(`DELETE FROM ${table}`);
    await this.database.executeSql(`DELETE FROM ${table}`);
  }

  async rawDelete(query: string): Promise<void> {
    await this.database.executeSql(query);
  }

  async close(): Promise<void> {
    await this.database.close();
  }
}

export type { DatabaseProtocol };
export { BaseDatabase };
