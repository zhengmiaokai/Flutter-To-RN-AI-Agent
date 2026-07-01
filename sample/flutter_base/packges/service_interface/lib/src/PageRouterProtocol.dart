import 'package:flutter/cupertino.dart';
import 'package:service_manager/service_manager.dart';

abstract class PageRouterProtocol extends ServiceProtocol {
  void openUrl(Uri uri);

  void pushNamed(BuildContext context, String routeName, {Object? arguments});
}