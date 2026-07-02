import React from 'react';
import { View, Text, FlatList, TouchableOpacity, SafeAreaView, StyleSheet } from 'react-native';

interface ListPageProps {
  name: string;
}

const ListPage: React.FC<ListPageProps> = ({ name }) => {
  const data = Array.from({ length: 20 });

  const renderItem = ({ index }: { index: number }) => (
    <TouchableOpacity
      style={styles.item}
      onPress={() => console.log(`Row ${index + 1}`)}
    >
      <Text>{`Row ${index + 1}`}</Text>
    </TouchableOpacity>
  );

  const renderSeparator = () => <View style={styles.separator} />;

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>{name}</Text>
      </View>
      <FlatList
        data={data}
        renderItem={({ index }) => renderItem({ index })}
        keyExtractor={(_, index) => index.toString()}
        ItemSeparatorComponent={renderSeparator}
      />
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: 'white',
  },
  header: {
    backgroundColor: '#2196F3',
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  headerTitle: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold',
  },
  item: {
    height: 50,
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  separator: {
    height: 1,
    backgroundColor: '#e0e0e0',
  },
});

export default ListPage;