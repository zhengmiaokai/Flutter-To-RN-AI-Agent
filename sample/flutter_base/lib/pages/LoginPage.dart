import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../views/LoginHeader.dart';
import '../views/LoginMainView.dart';
import '../views/AccountLoginView.dart';
import '../view_models/LoginViewModel.dart';

class LoginPage extends StatefulWidget {
  final String name;
  const LoginPage({required String name}) : name = name;

  @override
  State<StatefulWidget> createState() => LoginPageState();
}

class LoginPageState extends State<LoginPage> {
  final viewModel = LoginViewModel();

  @override
  void initState() {
    // TODO: implement initState
    super.initState();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    return MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (context) => this.viewModel),
          ChangeNotifierProvider(create: (context) => this.viewModel.mainViewModel),
        ],
        child: Scaffold(
          backgroundColor: Colors.white,
          resizeToAvoidBottomInset: true,
          body: Column(
            children: [
              LoginHeader(closeClick: () => closeAction(context)),
              Consumer<LoginViewModel>(builder: (context, viewModel, child) {
                return viewModel.loginScence == LoginScence.MainView ? LoginMainView() : AccountLoginView();
              })
            ],
          ),
          floatingActionButton: FloatingActionButton(onPressed: () {
            this.viewModel.changeLoginScence();
          }),
        ),
    );
  }

  void closeAction(BuildContext context) {
    Navigator.pop(context);
  }
}