import 'package:flutter/cupertino.dart';
import '../view_models/LoginMainViewModel.dart';

enum LoginScence {
  MainView,
  AccountLogin,
}

class LoginViewModel with ChangeNotifier {
  LoginScence loginScence = LoginScence.MainView;
  LoginMainViewModel mainViewModel = LoginMainViewModel();

  void changeLoginScence() {
    loginScence = (loginScence == LoginScence.MainView ? LoginScence.AccountLogin : LoginScence.MainView);
    notifyListeners();
  }
}