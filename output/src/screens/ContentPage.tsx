import React, { useState, useRef, useCallback } from 'react';
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  Image,
  Animated,
  Pressable,
  useWindowDimensions,
  SafeAreaView,
  ScrollView,
} from 'react-native';

interface ContentPageProps {
  name: string;
}

const ContentPage: React.FC<ContentPageProps> = ({ name }) => {
  const { width: screenWidth } = useWindowDimensions();
  const [password, setPassword] = useState('');
  const [isAnimating, setIsAnimating] = useState(false);
  const opacityAnim = useRef(new Animated.Value(0.5)).current;
  const inputRef = useRef<TextInput>(null);

  const handleNetworkPress = useCallback(() => {
    if (isAnimating) return;
    setIsAnimating(true);
    Animated.timing(opacityAnim, {
      toValue: 1,
      duration: 500,
      useNativeDriver: true,
    }).start(() => {
      console.log('动画结束');
      setIsAnimating(false);
    });
  }, [opacityAnim, isAnimating]);

  const changeText = () => {
    setPassword('123456');
  };

  // Simple double-tap detection
  const lastTapRef = useRef<number>(0);
  const handleDoubleTap = (onSingleTap?: () => void, onDoubleTap?: () => void) => {
    const now = Date.now();
    if (now - lastTapRef.current < 300) {
      lastTapRef.current = 0;
      onDoubleTap?.();
    } else {
      lastTapRef.current = now;
      setTimeout(() => {
        if (Date.now() - lastTapRef.current >= 300) {
          onSingleTap?.();
        }
      }, 300);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.container}>
        {/* AppBar */}
        <View style={styles.appBar}>
          <Text style={styles.appBarTitle}>{name}</Text>
        </View>

        <ScrollView contentContainerStyle={styles.bodyContent}>
          <View style={{ height: 6 }} />
          <SizeRow />
          <PasswordInput
            password={password}
            onChangePassword={setPassword}
            inputRef={inputRef}
          />
          <FirstText />
          <AssetImage
            screenWidth={screenWidth}
            onTap={() => console.log('单击')}
            onDoubleTap={() => console.log('双击')}
            onLongPress={() => console.log('长按')}
          />
          <NetworkImage
            screenWidth={screenWidth}
            opacityAnim={opacityAnim}
            onPress={handleNetworkPress}
          />
          <SizeStack />
          <SizeFlex />
          <SizeText />
        </ScrollView>
      </View>
    </SafeAreaView>
  );
};

// --- Sub-components ---

interface PasswordInputProps {
  password: string;
  onChangePassword: (text: string) => void;
  inputRef: React.RefObject<TextInput>;
}

const PasswordInput: React.FC<PasswordInputProps> = ({
  password,
  onChangePassword,
  inputRef,
}) => {
  return (
    <TextInput
      ref={inputRef}
      style={styles.passwordInput}
      placeholder="请输入密码"
      placeholderTextColor="rgba(0,0,0,0.12)"
      value={password}
      onChangeText={onChangePassword}
      secureTextEntry
      keyboardType="default"
      returnKeyType="done"
      onSubmitEditing={() => {
        console.log('编辑完成');
        inputRef.current?.blur();
      }}
      onBlur={() => {}}
    />
  );
};

const SizeRow: React.FC = () => (
  <View style={styles.sizeRowContainer}>
    <View style={styles.sizeRow}>
      <View style={{ width: 10 }} />
      <View style={[styles.colorBlock, { backgroundColor: 'blue' }]} />
      <View style={{ width: 10 }} />
      <View style={[styles.colorBlock, { backgroundColor: 'brown' }]} />
      <View style={{ width: 10 }} />
      <View style={[styles.colorBlock, { backgroundColor: 'green' }]} />
      <View style={{ width: 10 }} />
    </View>
  </View>
);

const FirstText: React.FC = () => (
  <Text
    style={styles.firstText}
    numberOfLines={2}
    ellipsizeMode="tail"
  >
    {'掌握Flutter布局需深入理解约束传递机制，合理组合Row/Column/Stack/Flex等核心组件，并通过动画微交互提升体验。'}
  </Text>
);

interface AssetImageProps {
  screenWidth: number;
  onTap?: () => void;
  onDoubleTap?: () => void;
  onLongPress?: () => void;
}

const AssetImage: React.FC<AssetImageProps> = ({
  screenWidth,
  onTap,
  onDoubleTap,
  onLongPress,
}) => {
  const lastTapRef = useRef<number>(0);

  const handlePress = () => {
    const now = Date.now();
    if (now - lastTapRef.current < 300) {
      lastTapRef.current = 0;
      onDoubleTap?.();
    } else {
      lastTapRef.current = now;
      setTimeout(() => {
        if (Date.now() - lastTapRef.current >= 300) {
          onTap?.();
        }
      }, 300);
    }
  };

  return (
    <Pressable onPress={handlePress} onLongPress={onLongPress}>
      <Image
        source={require('../../images/logo.png')}
        style={{ width: screenWidth - 40, height: 40 }}
        resizeMode="contain"
      />
    </Pressable>
  );
};

interface NetworkImageProps {
  screenWidth: number;
  opacityAnim: Animated.Value;
  onPress: () => void;
}

const NetworkImage: React.FC<NetworkImageProps> = ({
  screenWidth,
  opacityAnim,
  onPress,
}) => (
  <Pressable onPress={onPress}>
    <Animated.View style={{ opacity: opacityAnim }}>
      <Image
        source={{
          uri: 'http://gips2.baidu.com/it/u=195724436,3554684702&fm=3028&app=3028&f=JPEG&fmt=auto?w=1280&h=960',
        }}
        style={{ width: screenWidth - 40, height: 80 }}
        resizeMode="cover"
      />
    </Animated.View>
  </Pressable>
);

const SizeStack: React.FC = () => (
  <View style={styles.stackContainer}>
    <View style={styles.stackBase} />
    <View style={styles.starIcon}>
      <Text style={{ fontSize: 18 }}>★</Text>
    </View>
    <View style={styles.stackOverlay} />
  </View>
);

const SizeFlex: React.FC = () => (
  <View style={styles.flexContainer}>
    <View style={styles.flexRow}>
      <View style={[styles.flexItem, { flex: 1, backgroundColor: 'grey' }]} />
      <View style={[styles.flexItem, { flex: 2, backgroundColor: 'red' }]} />
    </View>
  </View>
);

const SizeText: React.FC = () => (
  <View style={styles.sizeTextContainer}>
    <Text style={styles.sizeText}>SizeText</Text>
  </View>
);

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: 'white',
  },
  container: {
    flex: 1,
    backgroundColor: 'white',
  },
  appBar: {
    height: 56,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  appBarTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  bodyContent: {
    paddingHorizontal: 20,
    paddingTop: 8,
  },
  passwordInput: {
    height: 40,
    fontSize: 16,
    fontWeight: 'bold',
    borderBottomWidth: 1,
    borderBottomColor: '#ccc',
    marginTop: 8,
  },
  sizeRowContainer: {
    height: 40,
    width: 160,
    backgroundColor: 'rgba(0,0,0,0.12)',
    borderRadius: 6,
    justifyContent: 'center',
    marginTop: 8,
  },
  sizeRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
  },
  colorBlock: {
    width: 20,
    height: 20,
  },
  firstText: {
    color: '#333333',
    fontSize: 16,
    marginTop: 8,
  },
  stackContainer: {
    height: 44,
    marginTop: 8,
  },
  stackBase: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'blue',
  },
  starIcon: {
    position: 'absolute',
    top: 10,
    left: 10,
  },
  stackOverlay: {
    position: 'absolute',
    top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.2)',
  },
  flexContainer: {
    height: 60,
    backgroundColor: 'rgba(0,0,0,0.12)',
    marginTop: 8,
    justifyContent: 'center',
  },
  flexRow: {
    flexDirection: 'row',
    gap: 20,
    paddingHorizontal: 8,
  },
  flexItem: {
    height: 44,
  },
  sizeTextContainer: {
    width: 180,
    height: 20,
    justifyContent: 'center',
    alignItems: 'flex-start',
    marginTop: 8,
  },
  sizeText: {
    fontSize: 16,
    color: '#333',
  },
});

export default ContentPage;