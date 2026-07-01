import 'package:service_manager/service_manager.dart';

abstract class NetworkProtocol extends ServiceProtocol {
  void post(Uri uri, Map params, void Function(String? body, Object? error) callback);
}