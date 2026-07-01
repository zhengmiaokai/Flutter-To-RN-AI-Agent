import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:service_interface/service_interface.dart';

class CommonNetwork implements NetworkProtocol  {
  void onLoad() { }

  void onUnLoad() { }

  void post(Uri uri, Map params, void Function(String? body, Object? error) callback) {
    final headers = {'Content-Type': 'application/json'};
    final body = jsonEncode(params);
    http.post(uri, headers: headers, body: body, encoding: utf8).then((final response) {
      if (response.statusCode >= 200 && response.statusCode <= 299) {
        callback(response.body, null);
      } else {
        callback(null, response.body);
      }
    }).catchError((Object error) {
      callback(null, error);
    });
  }
}