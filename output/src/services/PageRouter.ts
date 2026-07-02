import { PageRouterProtocol } from './PageRouterProtocol';
import { createNavigationContainerRef } from '@react-navigation/native';

const navigationRef = createNavigationContainerRef<any>();

export class PageRouter implements PageRouterProtocol {
  onLoad(): void {}

  onUnLoad(): void {}

  openUrl(url: string): void {
    console.log('welcome to page router');
  }

  pushNamed(routeName: string, params?: any): void {
    if (navigationRef.isReady()) {
      navigationRef.navigate(routeName, params);
    }
  }
}