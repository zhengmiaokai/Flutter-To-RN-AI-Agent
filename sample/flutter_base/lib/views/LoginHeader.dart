import 'package:flutter/material.dart';

class LoginHeader extends StatelessWidget {
  Function? closeClick;
  LoginHeader({this.closeClick});

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    double statusBarHeight = MediaQuery.of(context).padding.top;
    return SizedBox(
      width: size.width,
      height: 44 + statusBarHeight,
      child: Row(
        children: [
          SizedBox(width: 14,),
          GestureDetector(
            onTap: () {
              if (closeClick != null) {
                closeClick!();
              }
            },
            child: SizedBox(
              width: 26,
              height: 44 + statusBarHeight,
              child: Column(
                children: [
                  SizedBox(height: statusBarHeight + 9),
                  Container(
                    color: Colors.white,
                    padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    child: Image.asset('images/login_back.png', width: 11, height: 18),
                  )
                ],
              ),
            ),
          )
        ],
      ),
    );
  }

}