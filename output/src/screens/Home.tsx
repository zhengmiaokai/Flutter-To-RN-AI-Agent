import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

export default function HomeScreen(): React.JSX.Element {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Hello, React Native!</Text>
      <Text style={styles.subtitle}>Converted from Flutter</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  subtitle: {
    fontSize: 14,
    color: '#666',
    marginTop: 8,
  },
});
