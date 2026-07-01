import 'dart:convert';
import './BydInterface.dart';
import 'package:base_preferences/base_preferences.dart';
import 'package:base_database/base_database.dart';
import 'package:service_manager/service_manager.dart';
import 'package:service_interface/service_interface.dart';

class Car {
  late BaseDatabase database;

  void execute() async {
    print('base class');

    try {
      BasePreferences preferencesClient = BasePreferences.getInstance();
      bool status = await preferencesClient.setInt('uid', 123456);
      if (status) {
        preferencesClient.getInt('uid').then((int value) {
          print('get-uid: $value');
        });
      }

      this.database = BaseDatabase();
      await this.database.creatDB('db/db_base.db');
      await this.database.createTable('dbTable', {'name':'TEXT', 'age':'INTEGER', 'enjoy':'TEXT'}, true);
      await this.database.rawInsert('dbTable', {'name': 'lilylin', 'age': 27, 'enjoy': '踢足球，跑步，炒菜等等'});

      List list = await this.database.query('dbTable');
      final data = list[0] as Map;
      print('database: name-${data['name']}' + ', age-${data['age']}' + ', enjoy-${data['enjoy']}');

      await this.database.delete('dbTable');
      await this.database.close();

      final url = Uri.parse('https://m.baidu.com/staticConfig/getConfig.json');

      final networkClient = ServiceManager.getInstance().getProtocol(ServcieConstants.NETWORK) as NetworkProtocol;
      networkClient.post(url, {'key': 'value'}, (String? body, Object? error) {
        if (body != null) {
          print('body: ${jsonDecode(body)}');
        } else {
          print('error: $error');
        }
      });

      final pageRouter = ServiceManager.getInstance().getProtocol(ServcieConstants.PAGE_ROUTER) as PageRouterProtocol;
      pageRouter.openUrl(Uri.parse('https://m.baidu.com'));
    } catch(e) {
      print('catchError: $e');
    }
  }
}

class BydCar extends Car implements BydInterface {
  final String latestVersion;
  String? _name;

  BydCar(this.latestVersion);

  set name(String? value) => _name = value;
  String? get name => _name;

  @override
  void execute() {
    super.execute();

    this.name = 'setter + getter';
    print('${this.name}');

    Map jsonObject = jsonDecode('{"key":"value"}');
    print('jsonObject: $jsonObject');
  }

  void drive() {
    print('Car Interface: drive');
  }

  void automaticParking() {
    print('Byd Interface: automaticParking');
  }
}
