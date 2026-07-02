import React, { useCallback, useState } from 'react';
import { Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import LoginHeader from './LoginHeader';
import LoginMainView from './LoginMainView';
import AccountLoginView from './AccountLoginView';
import LoginViewModel, {
  LoginScence,
  LoginViewModelProvider,
} from '../providers/LoginViewModel';
import { LoginMainProvider } from '../providers/LoginMainViewModel';

interface LoginPageProps {
  name: string;
}

const LoginPage: React.FC<LoginPageProps> = ({ name }) => {
  const navigation = useNavigation();

  // Create view model instance – stored in state to maintain reference
  const [viewModel] = useState(() => new LoginViewModel());

  // Force re-render trigger (since viewModel mutates internally without ref change)
  const [, forceUpdate] = useState(0);

  const changeLoginScence = useCallback(() => {
    viewModel.changeLoginScence();
    forceUpdate((t) => t + 1);
  }, [viewModel]);

  const closeAction = useCallback(() => {
    navigation.goBack();
  }, [navigation]);

  return (
    <LoginViewModelProvider value={viewModel}>
      <LoginMainProvider>
        <SafeAreaView style={styles.safeArea}>
          <View style={styles.body}>
            <LoginHeader onClose={closeAction} />
            {viewModel.loginScene === LoginScence.MainView ? (
              <LoginMainView />
            ) : (
              <AccountLoginView />
            )}
          </View>
          <Pressable
            style={styles.fab}
            onPress={changeLoginScence}
            accessibilityLabel="Change login scene"
          >
            <Text style={styles.fabText}>+</Text>
          </Pressable>
        </SafeAreaView>
      </LoginMainProvider>
    </LoginViewModelProvider>
  );
};

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  body: {
    flex: 1,
    flexDirection: 'column',
  },
  fab: {
    position: 'absolute',
    bottom: 16,
    right: 16,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#2196F3', // typical Material FAB color
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 6,
  },
  fabText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
});

export default LoginPage;
