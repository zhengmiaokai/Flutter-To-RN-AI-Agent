import 'dart:async';
import 'package:shared_preferences/shared_preferences.dart';

abstract class PreferencesProtocol {
  Future<bool> setInt(String key, int value);
  Future<int> getInt(String key);

  Future<bool> setDouble(String key, double value);
  Future<double> getDouble(String key);

  Future<bool> setBool(String key, bool value);
  Future<bool> getBool(String key);

  Future<bool> setString(String key, String value);
  Future<String> getString(String key);
}

class BasePreferences implements PreferencesProtocol {
  static late final BasePreferences sInstance = BasePreferences();
  static BasePreferences getInstance() => sInstance;

  Future<bool> setInt(String key, int value) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.setInt(key, value);
  }

  Future<int> getInt(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getInt(key) ?? 0;
  }

  Future<bool> setDouble(String key, double value) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.setDouble(key, value);
  }

  Future<double> getDouble(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getDouble(key) ?? 0;
  }

  Future<bool> setBool(String key, bool value) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.setBool(key, value);
  }

  Future<bool> getBool(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(key) ?? false;
  }

  Future<bool> setString(String key, String value) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.setString(key, value);
  }

  Future<String> getString(String key) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(key) ?? '';
  }
}
