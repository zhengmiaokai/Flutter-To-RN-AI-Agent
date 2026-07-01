import 'package:flutter/services.dart';

final t_methodChannel = const MethodChannel('global_method_channel'); // 默认是StandardMethodCodec
final t_messageChannel = const BasicMessageChannel('global_message_channel', StandardMessageCodec());

class GlobalChannel {
  /* Flutter调用APP方法 */
  static void invokeMethod({required String method, Map? arguments, void Function(dynamic? result, Object? error)? callback}) {
    t_methodChannel.invokeMethod(method, arguments).then((dynamic? result) {
      if (callback != null) {
        callback(result, null);
      }
    }).catchError((Object? error) {
      if (callback != null) {
        callback(null, error);
      }
    });
  }

  /* Flutter向APP发送广播 */
  static void send({Object? message, void Function(dynamic? result, Object? error)? callback}) {
    t_messageChannel.send(message).then((dynamic? result){
      if (callback != null) {
        callback(result, null);
      }
    }).catchError((Object? error) {
      if (callback != null) {
        callback(null, error);
      }
    });
  }

  /* 监听APP调用Flutter的方法 */
  static void setMethodCallHandler() {
    t_methodChannel.setMethodCallHandler(_methodCallHandler);
  }

  /* 监听APP向Flutter发送的广播 */
  static void setMessageHandler() {
    t_messageChannel.setMessageHandler(_messageHandler);
  }

  static Future<dynamic> _methodCallHandler(MethodCall call) async {
    if (call.method != null && call.arguments != null ) {
      print('setMethodCallHandler: method-${call.method}, arguments-${call.arguments}');
    }
    return {'code': 0, 'message': 'success'};
  }

  static Future<dynamic> _messageHandler(dynamic? message) async {
    print('setMessageCallHandler: message-$message');
    return  {'code': 0, 'message': 'success'};
  }
}