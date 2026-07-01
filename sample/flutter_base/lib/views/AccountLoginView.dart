import 'package:flutter/material.dart';

class AccountLoginView extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(height: 48),
        Image.asset('images/login_logo.png',
          width: 155,
          height: 76,
          fit: BoxFit.contain,
        ),
        SizedBox(height: 38),
      ],
    );
  }
}