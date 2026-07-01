import 'dart:async';
import 'package:sqflite/sqflite.dart';

abstract class DatabaseProtocol {
  Future<void> creatDB(String file);

  /* 数据类型：INTEGER TEXT DOUBLE LONG SINGLE */
  Future<void> createTable(String table, Map keyTypes, bool isPRIMARY);

  Future<void> insert(String table, Map<String, Object?> values);

  /* 调用示例
  this.rawInsert('dbTable', {'name': 'lilylin', 'age': 27, 'enjoy': '踢足球，跑步，炒菜等等'});
  this.rawInsert('insert into dbTable (name, age, enjoy) VALUES (?, ?, ?)', ['lilylin', 27, '踢足球，跑步，炒菜等等']);
  this.rawInsert('insert into dbTable (name, age, enjoy) VALUES ("lilylin", 27, "踢足球，跑步，炒菜等等")');
  */
  Future<void> rawInsert(String query, [params]);

  Future<void> update(String table, Map<String, Object?> values, {String? where, List? whereArgs});

  Future<void> rawUpdate(String query);

  Future<List> query(String table, {String? where, List? whereArgs});

  Future<List> rawQuery(String query);

  Future<void> delete(String table);

  Future<void> rawDelete(String query);

  Future<void> close();
}

class BaseDatabase implements DatabaseProtocol {
  late Database database;

  Future<void> creatDB(String file) async {
    String path = await getDatabasesPath();
    String dirPath = path + file;
    this.database = await openDatabase(dirPath);
  }

  /* 数据类型：INTEGER TEXT DOUBLE LONG SINGLE */
  Future<void> createTable(String table, Map keyTypes, bool isPRIMARY) async {
    String queryParams = isPRIMARY ? 'id INTEGER PRIMARY KEY' : '';
    for (var key in keyTypes.keys) {
      var value = keyTypes[key];
      queryParams = queryParams + ', $key $value';
    }
    String query = 'create table if not exists $table ($queryParams)';
    await this.database.execute(query);
  }

  Future<void> insert(String table, Map<String, Object?>  parmas) async {
    await this.database.insert(table, parmas);
  }

  /* 调用示例
  this.rawInsert('dbTable', {'name': 'lilylin', 'age': 27, 'enjoy': '踢足球，跑步，炒菜等等'});
  this.rawInsert('insert into dbTable (name, age, enjoy) VALUES (?, ?, ?)', ['lilylin', 27, '踢足球，跑步，炒菜等等']);
  this.rawInsert('insert into dbTable (name, age, enjoy) VALUES ("lilylin", 27, "踢足球，跑步，炒菜等等")');
  */
  Future<void> rawInsert(String query, [params]) async {
    if (params != null) {
      if (params.runtimeType.toString().contains('Map')) {
        params = params as Map;
        String keys = '';
        List values = [];
        String zwf = '';
        for (var key in params.keys) {
          var value = params[key];
          keys = keys + (keys.isEmpty?key:', '+key);
          values.add(value);
          zwf = zwf + (zwf.isEmpty?'':', ') + '?';
        }
        String table = query;
        await this.database.rawInsert('insert into $table ($keys) VALUES ($zwf)', values);
      } else if (params.runtimeType.toString().contains('List')) {
        params = params as List;
        await this.database.rawInsert(query, params);
      } else {
        print('rawInsert:====插入数据格式有误');
      }
    } else {
      await this.database.rawInsert(query);
    }
  }

  Future<void> update(String table, Map<String, Object?> values, {String? where, List? whereArgs}) async {
    await this.database.update(table, values, where: where, whereArgs: whereArgs);
  }

  Future<void> rawUpdate(String query) async {
    await this.database.rawUpdate(query);
  }

  Future<List> query(table, {String? where, List? whereArgs}) async {
    List list = await this.database.query(table, where: where, whereArgs: whereArgs);
    return list;
  }

  Future<List> rawQuery(String query) async {
    List list = await this.database.rawQuery(query);
    return list;
  }

  Future<void> delete(String table) async {
    await this.database.delete(table);
    this.database.delete(table);
  }

  Future<void> rawDelete(String query) async {
    await this.database.rawDelete(query);
  }

  Future<void> close() async {
    await this.database.close();
  }
}
