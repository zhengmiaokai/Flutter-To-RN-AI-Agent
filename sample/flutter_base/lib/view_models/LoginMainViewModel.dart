import 'package:flutter/cupertino.dart';
import '../models/LoginMainModel.dart';

class LoginMainViewModel with ChangeNotifier {
  final model = LoginMainModel();

  final phoneController = TextEditingController();
  final codeController = TextEditingController();

  final phoneFocusNode = FocusNode();
  final codeFocusNode = FocusNode();

  void phoneInputChange() {
    model.phoneNumber = phoneController.text;
    if (model.phoneNumber.length == 11) {
      model.obtainCodeEnable = true;
      if (model.verifyCode.length == 6) {
        model.verifyLoginEnable = true;
      } else {
        model.verifyLoginEnable = false;
      }
    } else {
      model.obtainCodeEnable = false;
      model.verifyLoginEnable = false;
    }
    notifyListeners();
  }

  void codeInputChange() {
    model.verifyCode = codeController.text;
    if (model.phoneNumber.length == 11 && model.verifyCode.length == 6) {
      model.verifyLoginEnable = true;
    } else {
      model.verifyLoginEnable = false;
    }
    notifyListeners();
  }

  void changeObtainCodeState(Function callBack) {
    model.obtainCodeTitle = '重新获取';
    notifyListeners();
    callBack();
  }
}