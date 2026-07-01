import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:service_manager/service_manager.dart';
import 'package:service_interface/service_interface.dart';
import 'package:common_network/common_network.dart';
import 'package:page_router/page_router.dart';
import './channels/GlobalChannel.dart';
import './pages/HomePage.dart';
import './pages/ContentPage.dart';
import './pages/ListPage.dart';
import './pages/LoginPage.dart';

class Application {
  static void init() {
    // 注册SDK|组件服务
    registerService();

    // 运行应用
    String initialRoute = ui.PlatformDispatcher.instance.defaultRouteName;
    runApp(AppContainer(initialRoute: initialRoute));
  }

  static void registerService() {
    ServiceManager.getInstance().setProtocol(ServcieConstants.NETWORK, CommonNetwork());
    ServiceManager.getInstance().setProtocol(ServcieConstants.PAGE_ROUTER, Pagerouter());

    GlobalChannel.setMethodCallHandler();
    GlobalChannel.setMessageHandler();
  }
}

class AppContainer extends StatelessWidget {
  final String initialRoute;
  const AppContainer({super.key, required this.initialRoute});

  @override
  Widget build(BuildContext context) {
    /* 静态路由：目标页面通过 ModalRoute.of(context) 获取 settings 参数 */
    return MaterialApp(
      debugShowCheckedModeBanner: true,
      title: 'Application',
      initialRoute: this.initialRoute,
      routes: {
        '/': (context) => const HomePage(name: '首页'),
        '/HomePage': (context) => const HomePage(name: '首页'),
        '/ContentPage': (context) => const ContentPage(name: '内容'),
        '/ListPage': (context) => const ListPage(name: '列表'),
        '/LoginPage': (context) => const LoginPage(name: '登录'),
      }
    );

    /* 动态路由：通过页面构造函数传递 settings 参数 */
    return MaterialApp(
      title: 'Application',
      onGenerateRoute: (settings) {
        if  (settings.name == '/' || settings.name == '/HomePage') {
          String? _title;
          if (settings.arguments != null) {
            final arguments = settings.arguments as Map<String, dynamic>;
            _title = arguments['title'];
          }
          return MaterialPageRoute(builder: (context) => HomePage(name: (_title ?? '首页')));
        }
      },
      onUnknownRoute: (settings) => MaterialPageRoute(builder: (context) => HomePage(name: '首页'))
    );
  }
}