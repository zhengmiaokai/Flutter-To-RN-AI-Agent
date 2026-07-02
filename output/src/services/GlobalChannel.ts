// src/services/GlobalChannel.ts
// Native module registration required; see the bottom of the file for native bridging notes.
import { NativeModules, NativeEventEmitter } from 'react-native';

interface MethodCall {
  method: string;
  args: any;
}

type NativeCallback = (result: any, error?: any) => void;
type MethodCallHandler = (call: MethodCall) => Promise<{ code: number; message: string }>;
type MessageHandler = (message: any) => Promise<{ code: number; message: string }>;

// NativeModules must be linked accordingly:
// - GlobalMethodChannel: exposes invokeMethod(method, args) => Promise<any>
//                        and resolveMethodCall(requestId, result) if two-way
// - GlobalMessageChannel: exposes send(message) => Promise<any>
//                        and resolveMessage(requestId, result) if two-way

const MethodChannel = NativeModules.GlobalMethodChannel ?? {
  invokeMethod: () => Promise.reject(new Error('GlobalMethodChannel not linked')),
};
const MessageChannel = NativeModules.GlobalMessageChannel ?? {
  send: () => Promise.reject(new Error('GlobalMessageChannel not linked')),
};

const methodChannelEmitter = new NativeEventEmitter(MethodChannel);
const messageChannelEmitter = new NativeEventEmitter(MessageChannel);

let _methodCallHandler: MethodCallHandler | null = null;
let _messageHandler: MessageHandler | null = null;

// Listeners for incoming calls from native
methodChannelEmitter.addListener('methodCall', (data: { method: string; arguments: any; requestId?: string }) => {
  if (_methodCallHandler && data.method !== undefined && data.arguments !== undefined) {
    console.log(`setMethodCallHandler: method-${data.method}, arguments-${JSON.stringify(data.arguments)}`);
    _methodCallHandler({ method: data.method, args: data.arguments }).then((result) => {
      if (data.requestId && MethodChannel.resolveMethodCall) {
        MethodChannel.resolveMethodCall(data.requestId, result);
      }
    });
  }
});

messageChannelEmitter.addListener('message', (data: { message: any; requestId?: string }) => {
  if (_messageHandler) {
    console.log(`setMessageCallHandler: message-${JSON.stringify(data.message)}`);
    _messageHandler(data.message).then((result) => {
      if (data.requestId && MessageChannel.resolveMessage) {
        MessageChannel.resolveMessage(data.requestId, result);
      }
    });
  }
});

export class GlobalChannel {
  /* Flutter调用APP方法 */
  static invokeMethod({
    method,
    args,
    callback,
  }: {
    method: string;
    args?: Record<string, any>;
    callback?: NativeCallback;
  }): void {
    MethodChannel.invokeMethod(method, args)
      .then((result: any) => {
        callback?.(result, undefined);
      })
      .catch((error: any) => {
        callback?.(undefined, error);
      });
  }

  /* Flutter向APP发送广播 */
  static send({ message, callback }: { message?: any; callback?: NativeCallback }): void {
    MessageChannel.send(message)
      .then((result: any) => {
        callback?.(result, undefined);
      })
      .catch((error: any) => {
        callback?.(undefined, error);
      });
  }

  /* 监听APP调用Flutter的方法 */
  static setMethodCallHandler(): void {
    // The listener is already attached via NativeEventEmitter (see top of file).
    // This method exists for API parity with the original Dart code.
  }

  /* 监听APP向Flutter发送的广播 */
  static setMessageHandler(): void {
    // Same as above – listener is attached at module scope.
  }

  /* 
   * These are the handler implementations – they replace the original Dart private functions.
   * In the original, the handlers returned a default success response.
   * For full two‑way communication, the native side must send a 'methodCall' or 'message' event
   * with a requestId, and the JS side will call the native resolve method.
   * If that mechanism is not needed (only invoking/sending, no incoming calls), 
   * the emitter and handler logic can be removed.
   */
  static async _methodCallHandler(call: MethodCall): Promise<{ code: number; message: string }> {
    if (call.method != null && call.args != null) {
      console.log(`setMethodCallHandler: method-${call.method}, arguments-${JSON.stringify(call.args)}`);
    }
    return { code: 0, message: 'success' };
  }

  static async _messageHandler(message?: any): Promise<{ code: number; message: string }> {
    console.log(`setMessageCallHandler: message-${JSON.stringify(message)}`);
    return { code: 0, message: 'success' };
  }
}

// Initialize handlers to the default implementations
_methodCallHandler = GlobalChannel._methodCallHandler;
_messageHandler = GlobalChannel._messageHandler;

// TODO: [Flutter→RN] Native modules "GlobalMethodChannel" and "GlobalMessageChannel" must be
// implemented on the native side. The exact method names and event names ('methodCall', 'message')
// must match those expected by this service. Optional: implement resolveMethodCall / resolveMessage
// for two‑way communication.