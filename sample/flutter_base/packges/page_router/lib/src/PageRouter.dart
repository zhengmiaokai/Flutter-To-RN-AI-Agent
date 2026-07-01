import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:service_interface/service_interface.dart';

class Pagerouter implements PageRouterProtocol {
  void onLoad() { }

  void onUnLoad() { }

  void openUrl(Uri uri) {
    print('welcome to page router');
  }

  void pushNamed(BuildContext context, String routeName, {Object? arguments}) {
    Navigator.pushNamed(context, routeName, arguments: arguments);
  }
}
