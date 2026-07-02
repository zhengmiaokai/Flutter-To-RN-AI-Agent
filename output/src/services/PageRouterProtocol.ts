import { ServiceProtocol } from './service_manager';

// In React Native, Uri is typically represented as a string.
// No direct equivalent to Flutter's Uri class; we use string instead.
export abstract class PageRouterProtocol implements ServiceProtocol {
  abstract onLoad(): void;
  abstract onUnLoad(): void;

  /** Open a URL, e.g. with Linking.openURL */
  abstract openUrl(url: string): void;

  /**
   * Navigate to a named route, similar to pushing a named route in Flutter.
   * The `context` parameter from Flutter is omitted because a navigation
   * service should hold the navigation reference internally.
   */
  abstract pushNamed(routeName: string, params?: any): void;
}