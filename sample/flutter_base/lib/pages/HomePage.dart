import 'package:flutter/material.dart';
import 'package:service_manager/service_manager.dart';
import 'package:service_interface/service_interface.dart';
import '../tests/BydCar.dart';

class HomePage extends StatefulWidget {
  final String name;
  const HomePage({super.key, required this.name});

  @override
  State<HomePage> createState() => HomePageState();
}

class HomePageState extends State<HomePage> {
  int _counter = 0;
  String _listName = '列表页';
  final BydCar _bydCar = BydCar('1.0.0');

  @override
  void initState() {
    super.initState();
  }

  @override void didUpdateWidget(covariant HomePage oldWidget) {
    super.didUpdateWidget(oldWidget);
  }

  void _incrementCounter() {
    setState(() {
      _counter++;
    });

    final modalRoute = ModalRoute.of(context);
    if (modalRoute != null) {
      final settings = modalRoute.settings;
      print('settings: name-${settings.name}, arguments-${settings.arguments}');
    }

    _bydCar
      ..execute()
      ..drive()
      ..automaticParking();
  }

  void _jumpContentPage() {
    final pageRouter = ServiceManager.getInstance().getProtocol(ServcieConstants.PAGE_ROUTER) as PageRouterProtocol;
    pageRouter.pushNamed(context, '/ContentPage', arguments: {'title': '内容'});
  }

  void _jumpListPage() {
    final pageRouter = ServiceManager.getInstance().getProtocol(ServcieConstants.PAGE_ROUTER) as PageRouterProtocol;
    pageRouter.pushNamed(context, '/ListPage', arguments: {'title': '列表'});
  }

  void _jumpMinePage() {
    final pageRouter = ServiceManager.getInstance().getProtocol(ServcieConstants.PAGE_ROUTER) as PageRouterProtocol;
    pageRouter.pushNamed(context, '/LoginPage', arguments: null);
  }

  void _jumpDetailPage() {
    print('DetailPage is building!');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.name),
      ),
      body: Container(
        alignment: Alignment.center, // 水平|垂直居中对齐
        padding: EdgeInsetsGeometry.directional(top: 50), // 内边距
        child: Column(
          mainAxisAlignment: MainAxisAlignment.start, // 水平向顶对齐
          crossAxisAlignment: CrossAxisAlignment.center, // 垂直居中对齐
          spacing: 50,
          children: [
            ElevatedButton(
              onPressed: _incrementCounter,
              child: Text('Click: ${_counter}', style: TextStyle(fontSize: 20, color: Colors.white)),
              style: ElevatedButton.styleFrom(
                backgroundColor: Color(0xFF52d0c2), // 背景色
                elevation: 3, // 阴影高度
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20), // 圆角
                ),
                padding: EdgeInsets.symmetric(horizontal: 30, vertical: 15), // 内边距
              ),
            ),
            TextButton(
              onPressed: _jumpContentPage,
              child: Text('内容页', style: TextStyle(fontSize: 20, color: Colors.black)),
              style: TextButton.styleFrom(
                side: BorderSide(width: 1, color: Colors.black), // 边框属性
                backgroundColor: Colors.white, // 背景色
                padding: EdgeInsets.symmetric(horizontal: 30, vertical: 15), // 内边距
              ),
            ),
            FilledButton(
              onPressed: _jumpListPage,
              child: Text(_listName, style: TextStyle(fontSize: 20, color: Colors.white)),
              style: FilledButton.styleFrom(
                elevation: 3, // 阴影高度
                backgroundColor: Colors.black, // 背景色
                padding: EdgeInsets.symmetric(horizontal: 30, vertical: 15), // 内边距
              ),
            ),
            OutlinedButton(
              onPressed: _jumpMinePage,
              child: SizedBox(
                width: 100,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  spacing: 10,
                  children: [Icon(Icons.camera) , Text('登录页', style: TextStyle(fontSize: 18))],
                ),
              ),
              style: OutlinedButton.styleFrom(
                side: BorderSide(width: 1, color: Colors.black),
                backgroundColor: Colors.white, // 背景色
                padding: EdgeInsets.symmetric(horizontal: 10, vertical: 15), // 内边距
              ),
            ),
            ElevatedButton(
              onPressed: _jumpDetailPage,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Image.network('http://gips2.baidu.com/it/u=195724436,3554684702&fm=3028&app=3028&f=JPEG&fmt=auto?w=1280&h=960', width: 200, height: 80, fit: BoxFit.cover),
                  Text('图文按钮', style: TextStyle(fontSize: 20, color: Colors.white)),
                ],
              ),
              style: ElevatedButton.styleFrom(
                padding: EdgeInsets.all(0), // 内边距
              ),
            ),
          ],
        ),
      ),
    );
  }
}