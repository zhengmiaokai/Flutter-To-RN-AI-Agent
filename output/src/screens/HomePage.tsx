import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  Image,
  StyleSheet,
  Pressable,
  SafeAreaView,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { ServiceManager } from '../services/ServiceManager';
import { ServiceConstants, PageRouterProtocol } from '../services/service_interface';
import BydCar from '../tests/BydCar';

interface HomePageProps {
  name: string;
  key?: React.Key;
}

const HomePage: React.FC<HomePageProps> = ({ name }) => {
  const [counter, setCounter] = useState(0);
  const listName = '列表页';
  const bydCar = useRef(new BydCar('1.0.0')).current;

  const navigation = useNavigation<any>();
  const route = useRoute<any>();

  const incrementCounter = useCallback(() => {
    setCounter(prev => prev + 1);

    if (route) {
      console.log(`settings: name-${route.name}, arguments-${JSON.stringify(route.params)}`);
    }

    bydCar.execute();
    bydCar.drive();
    bydCar.automaticParking();
  }, [route, bydCar]);

  const jumpContentPage = useCallback(() => {
    const pageRouter = ServiceManager.getInstance().getProtocol(ServiceConstants.PAGE_ROUTER) as unknown as PageRouterProtocol;
    // Using React Navigation:
    if (pageRouter && pageRouter.pushNamed) {
      pageRouter.pushNamed('ContentPage', { title: '内容' });
    } else {
      navigation.navigate('ContentPage', { title: '内容' });
    }
  }, [navigation]);

  const jumpListPage = useCallback(() => {
    const pageRouter = ServiceManager.getInstance().getProtocol(ServiceConstants.PAGE_ROUTER) as unknown as PageRouterProtocol;
    if (pageRouter && pageRouter.pushNamed) {
      pageRouter.pushNamed('ListPage', { title: '列表' });
    } else {
      navigation.navigate('ListPage', { title: '列表' });
    }
  }, [navigation]);

  const jumpMinePage = useCallback(() => {
    const pageRouter = ServiceManager.getInstance().getProtocol(ServiceConstants.PAGE_ROUTER) as unknown as PageRouterProtocol;
    if (pageRouter && pageRouter.pushNamed) {
      pageRouter.pushNamed('LoginPage', undefined);
    } else {
      navigation.navigate('LoginPage');
    }
  }, [navigation]);

  const jumpDetailPage = useCallback(() => {
    console.log('DetailPage is building!');
  }, []);

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.appBar}>
        <Text style={styles.appBarTitle}>{name}</Text>
      </View>
      <View style={styles.container}>
        <TouchableOpacity
          style={styles.elevatedButton}
          onPress={incrementCounter}
          activeOpacity={0.8}
        >
          <Text style={styles.elevatedButtonText}>Click: {counter}</Text>
        </TouchableOpacity>

        <Pressable style={styles.textButton} onPress={jumpContentPage}>
          <Text style={styles.textButtonText}>内容页</Text>
        </Pressable>

        <Pressable style={styles.filledButton} onPress={jumpListPage}>
          <Text style={styles.filledButtonText}>{listName}</Text>
        </Pressable>

        <Pressable style={styles.outlinedButton} onPress={jumpMinePage}>
          <View style={styles.outlinedButtonContent}>
            <Text style={styles.icon}>📷</Text>
            <Text style={styles.outlinedButtonText}>登录页</Text>
          </View>
        </Pressable>

        <Pressable style={styles.imageButton} onPress={jumpDetailPage}>
          <Image
            source={{
              uri: 'http://gips2.baidu.com/it/u=195724436,3554684702&fm=3028&app=3028&f=JPEG&fmt=auto?w=1280&h=960',
            }}
            style={styles.imageButtonBackground}
            resizeMode="cover"
          />
          <Text style={styles.imageButtonText}>图文按钮</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#ffffff',
  },
  appBar: {
    height: 56,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f8f8f8',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  appBarTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#000000',
  },
  container: {
    flex: 1,
    justifyContent: 'flex-start',
    alignItems: 'center',
    paddingTop: 50,
    gap: 50,
  },
  elevatedButton: {
    backgroundColor: '#52d0c2',
    borderRadius: 20,
    paddingHorizontal: 30,
    paddingVertical: 15,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  elevatedButtonText: {
    fontSize: 20,
    color: '#ffffff',
  },
  textButton: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#000000',
    paddingHorizontal: 30,
    paddingVertical: 15,
    borderRadius: 4,
  },
  textButtonText: {
    fontSize: 20,
    color: '#000000',
  },
  filledButton: {
    backgroundColor: '#000000',
    paddingHorizontal: 30,
    paddingVertical: 15,
    borderRadius: 4,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  filledButtonText: {
    fontSize: 20,
    color: '#ffffff',
  },
  outlinedButton: {
    backgroundColor: '#ffffff',
    borderWidth: 1,
    borderColor: '#000000',
    paddingHorizontal: 10,
    paddingVertical: 15,
    borderRadius: 4,
  },
  outlinedButtonContent: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 10,
  },
  icon: {
    fontSize: 18,
    color: '#000000',
  },
  outlinedButtonText: {
    fontSize: 18,
    color: '#000000',
  },
  imageButton: {
    width: 200,
    height: 80,
    borderRadius: 4,
    overflow: 'hidden',
    justifyContent: 'center',
    alignItems: 'center',
  },
  imageButtonBackground: {
    ...StyleSheet.absoluteFillObject,
    width: '100%',
    height: '100%',
  },
  imageButtonText: {
    fontSize: 20,
    color: '#ffffff',
    position: 'absolute',
  },
});

export default HomePage;
