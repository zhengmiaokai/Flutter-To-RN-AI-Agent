import React from 'react';
import {
  View,
  Pressable,
  Image,
  StyleSheet,
  useWindowDimensions,
  Platform,
  StatusBar,
} from 'react-native';

interface LoginHeaderProps {
  onClose?: () => void;
}

const LoginHeader: React.FC<LoginHeaderProps> = ({ onClose }) => {
  const { width } = useWindowDimensions();
  const statusBarHeight =
    Platform.OS === 'ios' ? 20 : (StatusBar.currentHeight ?? 0);
  const totalHeight = 44 + statusBarHeight;

  return (
    <View style={[styles.container, { width, height: totalHeight }]}>
      <View style={{ width: 14 }} />
      <Pressable
        onPress={() => onClose?.()}
        style={[
          styles.closeButton,
          { height: totalHeight, paddingTop: statusBarHeight + 9 },
        ]}
      >
        <View style={styles.imageBackground}>
          <Image
            source={require('../images/login_back.png')}
            style={styles.image}
            resizeMode="contain"
          />
        </View>
      </Pressable>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  closeButton: {
    width: 26,
    alignItems: 'center',
  },
  imageBackground: {
    backgroundColor: 'white',
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  image: {
    width: 11,
    height: 18,
  },
});

export default LoginHeader;