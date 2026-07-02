import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';

import { ServiceManager } from '../services/service_manager';
import { ServiceConstants } from '../services/service_interface';
import { CommonNetwork } from '../services/common_network';
import { PageRouter } from '../services/page_router';
import { GlobalChannel } from '../services/GlobalChannel';

import HomePage from '../screens/HomePage';
import ContentPage from '../screens/ContentPage';
import ListPage from '../screens/ListPage';
import LoginPage from '../screens/LoginPage';

const Stack = createNativeStackNavigator();

interface AppContainerProps {
  initialRoute: string;
  key?: React.Key;
}

const AppContainer: React.FC<AppContainerProps> = ({ initialRoute, key }) => {
  return (
    <NavigationContainer key={key}>
      <Stack.Navigator initialRouteName={initialRoute}>
        <Stack.Screen name="/" component={HomePageScreen} options={{ title: '首页' }} />
        <Stack.Screen name="/HomePage" component={HomePageScreen} options={{ title: '首页' }} />
        <Stack.Screen name="/ContentPage" component={ContentPageScreen} options={{ title: '内容' }} />
        <Stack.Screen name="/ListPage" component={ListPageScreen} options={{ title: '列表' }} />
        <Stack.Screen name="/LoginPage" component={LoginPageScreen} options={{ title: '登录' }} />
      </Stack.Navigator>
    </NavigationContainer>
  );
};

const HomePageScreen: React.FC = () => <HomePage name="首页" />;
const ContentPageScreen: React.FC = () => <ContentPage name="内容" />;
const ListPageScreen: React.FC = () => <ListPage name="列表" />;
const LoginPageScreen: React.FC = () => <LoginPage name="登录" />;

class Application {
  static init(): void {
    registerService();

    // In Flutter: initialRoute = ui.PlatformDispatcher.instance.defaultRouteName
    // React Native: obtain initial route from deep link or launch arguments
    const initialRoute = '/'; // TODO: [Flutter→RN] Get initial route from deep link (Linking.getInitialURL())
    // runApp equivalent is handled by registering AppContainer as root component elsewhere
  }
}

function registerService(): void {
  ServiceManager.getInstance().setProtocol(ServiceConstants.NETWORK, new CommonNetwork());
  ServiceManager.getInstance().setProtocol(ServiceConstants.PAGE_ROUTER, new PageRouter());

  GlobalChannel.setMethodCallHandler();
  GlobalChannel.setMessageHandler();
}

export { Application, AppContainer, registerService };