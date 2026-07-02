import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  StatusBar,
} from 'react-native';

interface MyHomePageProps {
  title: string;
}

const MyHomePage: React.FC<MyHomePageProps> = ({ title }) => {
  const [counter, setCounter] = useState(0);

  const incrementCounter = () => {
    setCounter(prev => prev + 1);
  };

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar barStyle="dark-content" backgroundColor="#E8DEF8" />
      {/* AppBar */}
      <View style={styles.appBar}>
        <Text style={styles.appBarTitle}>{title}</Text>
      </View>

      {/* Body */}
      <View style={styles.body}>
        <Text style={styles.promptText}>
          You have pushed the button this many times:
        </Text>
        <Text style={styles.counterText}>{counter}</Text>
      </View>

      {/* FloatingActionButton */}
      <TouchableOpacity
        style={styles.fab}
        onPress={incrementCounter}
        activeOpacity={0.8}
        accessibilityLabel="Increment counter"
        accessibilityRole="button"
      >
        <Text style={styles.fabIcon}>+</Text>
      </TouchableOpacity>
    </SafeAreaView>
  );
};

const App: React.FC = () => {
  return <MyHomePage title="Flutter Demo Home Page" />;
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  appBar: {
    backgroundColor: '#E8DEF8', // inversePrimary shade from deepPurple
    paddingVertical: 16,
    paddingHorizontal: 16,
    elevation: 4,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 3.84,
  },
  appBarTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#1D1B20',
  },
  body: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  promptText: {
    fontSize: 16,
    color: '#333',
    marginBottom: 12,
  },
  counterText: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#1D1B20',
  },
  fab: {
    position: 'absolute',
    right: 24,
    bottom: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#6750A4', // Deep Purple primary
    justifyContent: 'center',
    alignItems: 'center',
    elevation: 6,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.27,
    shadowRadius: 4.65,
  },
  fabIcon: {
    color: '#FFFFFF',
    fontSize: 28,
    lineHeight: 30,
    fontWeight: '300',
  },
});

export default App;