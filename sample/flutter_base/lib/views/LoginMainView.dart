import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import '../view_models/LoginMainViewModel.dart';

class LoginMainView extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final mainViewModel = Provider.of<LoginMainViewModel>(context);
    return GestureDetector(
      behavior: HitTestBehavior.translucent,
      onTap: () {
        mainViewModel.phoneFocusNode.unfocus();
        mainViewModel.codeFocusNode.unfocus();
      },
      child: SingleChildScrollView(
        scrollDirection: Axis.vertical,
        physics: Platform.isIOS
            ? BouncingScrollPhysics()  // iOS弹性效果
            : ClampingScrollPhysics(), // Android夹紧效果
        child: Column(
          children: [
            SizedBox(height: 48),
            Image.asset('images/login_logo.png',
              width: 155,
              height: 76,
              fit: BoxFit.contain,
            ),
            SizedBox(height: 38),
            Container(
              height: 56,
              padding: EdgeInsetsGeometry.symmetric(horizontal: 24),
              child: TextField(
                controller: mainViewModel.phoneController,
                focusNode: mainViewModel.phoneFocusNode,
                decoration: InputDecoration(
                  hintText: '请输入手机号',
                  hintStyle: TextStyle(fontSize: 15, fontWeight: FontWeight.normal, color: Color(0xFFABADB2)),
                  border: InputBorder.none,
                  contentPadding: EdgeInsetsGeometry.directional(top: 6),
                ),
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Color(0xFF1D1E1F)),
                inputFormatters: [
                  LengthLimitingTextInputFormatter(11),
                  FilteringTextInputFormatter.digitsOnly,
                ],
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.done,
                onChanged: (value) => mainViewModel.phoneInputChange(),
                onSubmitted: (value) => mainViewModel.phoneFocusNode.unfocus(),
              ),
            ),
            Divider(
              height: 0.5,
              thickness: 0.5,
              color: Color(0xFFEDEDEE),
              indent: 24,
              endIndent: 24,
            ),
            Container(
              height: 56,
              padding: EdgeInsetsGeometry.symmetric(horizontal: 24),
              child: Row(
                children: [
                  Expanded(
                    flex: 2,
                    child: TextField(
                      controller: mainViewModel.codeController,
                      focusNode: mainViewModel.codeFocusNode,
                      decoration: InputDecoration(
                        hintText: '请输入验证码',
                        hintStyle: TextStyle(fontSize: 15, fontWeight: FontWeight.normal, color: Color(0xFFABADB2)),
                        border: InputBorder.none,
                      ),
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold, color: Color(0xFF1D1E1F)),
                      inputFormatters: [
                        LengthLimitingTextInputFormatter(6),
                        FilteringTextInputFormatter.digitsOnly,
                      ],
                      keyboardType: TextInputType.phone,
                      textInputAction: TextInputAction.done,
                      onChanged: (value) => mainViewModel.codeInputChange(),
                      onSubmitted: (value) =>  mainViewModel.codeFocusNode.unfocus(),
                    ),
                  ),
                  Expanded(
                    flex: 1,
                    child: Container(
                      alignment: Alignment.centerRight,
                      padding: EdgeInsetsGeometry.symmetric(vertical: 14),
                      child: TextButton(
                        onPressed: () => print('获取验证码'),
                        child: Text(mainViewModel.model.obtainCodeTitle, style: TextStyle(fontSize: 12, color: mainViewModel.model.obtainCodeEnable ? Color(0xFF267DFF) : Color(0xFFABADB2))),
                        style: TextButton.styleFrom(
                          overlayColor: Colors.white,
                          side: BorderSide(width: 0.5, color: mainViewModel.model.obtainCodeEnable ? Color(0xFF407AFF) : Color(0xFFDCDCDE)),
                          backgroundColor: Colors.white,
                          padding: EdgeInsets.symmetric(horizontal: 8, vertical: 0),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Divider(
              height: 0.5,
              thickness: 0.5,
              color: Color(0xFFEDEDEE),
              indent: 24,
              endIndent: 24,
            ),
            Container(
              padding: EdgeInsetsGeometry.symmetric(horizontal: 24, vertical: 8),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: () => print('账号密码登录'),
                    child: Text('账号密码登录', style: TextStyle(fontSize: 13, color: Color(0xFF267DFF), fontWeight: FontWeight.bold)),
                  ),
                  Spacer(),
                  GestureDetector(
                    onTap: () => print('登录遇到问题'),
                    child: Text('登录遇到问题', style: TextStyle(fontSize: 13, color: Color(0xFFABADB2), fontWeight: FontWeight.bold)),
                  ),
                ],
              ),
            )
          ],
        ),
      ),
    );
  }
}