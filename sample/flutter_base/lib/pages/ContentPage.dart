import 'package:flutter/material.dart';

class ContentPage extends StatefulWidget {
  final String name;
  const ContentPage({super.key, required this.name});

  @override
  State<StatefulWidget> createState() => ContentPageState();
}

class ContentPageState extends State<ContentPage> {
  double opacity = 0.5;
  final controller = TextEditingController();
  final focusNode = FocusNode();

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        title: Text(widget.name),
      ),
      body: Container(
        color: Colors.white,
        width: size.width,
        height: size.height,
        alignment: Alignment.topLeft, // 向左|顶对齐
        padding: EdgeInsets.symmetric(horizontal: 20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.start,
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 8,
          children: [
            SizedBox(height: 6),
            this.SizeRow(),
            this.PasswordInput(),
            this.FirstText(),
            this.AssetImage(size),
            this.NetworkImage(size),
            this.SizeStack(),
            this.SizeFlex(),
            this.SizeText(),
          ],
        ),
      ),
    );
  }

  Widget SizeRow() {
    return Container(
      height: 40,
      width: 160,
      decoration: BoxDecoration(color: Colors.black12, borderRadius: BorderRadius.circular(6),),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        textDirection: TextDirection.ltr,
        verticalDirection: VerticalDirection.down,
        children: [
          SizedBox(width: 10,), Container(width: 20, height: 20, color: Colors.blue,),
          SizedBox(width: 10,), Container(width: 20, height: 20, color: Colors.brown,),
          SizedBox(width: 10,), Container(width: 20, height: 20, color: Colors.green,), SizedBox(width: 10,),
        ],
      ),
    );
  }

  Widget PasswordInput() {
    return TextField(
      controller: this.controller, // 文本编辑
      focusNode: this.focusNode, // 焦点节点
      decoration: InputDecoration( // 内容装饰
        hintText: '请输入密码',
        hintStyle: TextStyle(fontSize: 16, color: Colors.black12),
      ),
      style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
      keyboardType: TextInputType.visiblePassword, // 键盘类型
      textInputAction: TextInputAction.done, // 完成按钮
      obscureText: true, // 是否隐藏内容
      onChanged: (value) => print('文本变化-$value'),
      onEditingComplete: () => print('编辑完成'),
      onSubmitted: (value) {
        this.focusNode.unfocus(); // 隐藏键盘
      },
    );
  }

  void changeText() {
    this.controller.text = '123456'; // 文本赋值
  }

  Widget FirstText() {
    return Text('掌握Flutter布局需深入理解约束传递机制，合理组合Row/Column/Stack/Flex等核心组件，并通过动画微交互提升体验。',
      style: TextStyle(color: Color(0xFF333333), fontSize: 16),
      overflow: TextOverflow.ellipsis,
      maxLines: 2,
    );
  }

  Widget AssetImage(Size size) {
    return GestureDetector(
      onTap: () => print('单击'),
      onDoubleTap: () => print('双击'),
      onLongPress: () => print('长按'),
      child: Image.asset('images/logo.png',
        width: size.width-40,
        height: 40,
        fit: BoxFit.contain,
      ),
    );
  }

  Widget NetworkImage(Size size) {
    return GestureDetector(
      onTap: () {
        setState(() {
          this.opacity = 1;
        });
      },
      child: AnimatedOpacity(
        opacity: this.opacity,
        duration: Duration(milliseconds: 500),
        onEnd: () => print('动画结束'),
        child: Image.network('http://gips2.baidu.com/it/u=195724436,3554684702&fm=3028&app=3028&f=JPEG&fmt=auto?w=1280&h=960',
          width: size.width-40,
          height: 80,
          fit: BoxFit.cover,
        ),
      ),
    );
  }

  Widget SizeStack() {
    return Visibility(
      visible: true,
      child: Stack(
        children: [
          Container(height: 44, color: Colors.blue),
          Positioned(top: 10, left: 10, child: Icon(Icons.star)), // 定位组件
          Positioned.fill(child: Container(color: Color(0x33000000))), // 半透明遮罩
        ],
      ),
    );
  }

  Widget SizeFlex() {
    return Container(
      height: 60,
      color: Colors.black12,
      child: Flex(
        direction: Axis.horizontal,
        spacing: 20,
        children: [
          Flexible(flex: 1, child: Container(color: Colors.grey)), // 填充剩余空间
          Expanded(flex: 2, child: Container(color: Colors.red)), // 强制填满剩余空间
        ],
      ),
    );
  }

  Widget SizeText() {
    return SizedBox(
      width: 180,
      height: 20,
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text('SizeText'),
      ),
    );
  }
}
