import React from 'react';
import {
  View,
  Text,
  Image,
  ScrollView,
  TextInput,
  Pressable,
  Keyboard,
  Platform,
  StyleSheet,
} from 'react-native';
import { useLoginMainViewModel } from '../providers/LoginMainViewModel';

interface LoginMainViewProps {
  key?: React.Key;
}

const LoginMainView: React.FC<LoginMainViewProps> = () => {
  const mainViewModel = useLoginMainViewModel();

  const handlePhoneChange = (text: string) => {
    const filtered = text.replace(/[^0-9]/g, '');
    mainViewModel.phoneInputChange(filtered);
  };

  const handleCodeChange = (text: string) => {
    const filtered = text.replace(/[^0-9]/g, '');
    mainViewModel.codeInputChange(filtered);
  };

  const dismissKeyboard = () => {
    Keyboard.dismiss();
    mainViewModel.phoneFocusRef.current?.blur();
    mainViewModel.codeFocusRef.current?.blur();
  };

  return (
    <Pressable onPress={dismissKeyboard} style={styles.container}>
      <ScrollView
        style={styles.scrollView}
        bounces={Platform.OS === 'ios'}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.column}>
          <View style={styles.spacer48} />
          <Image
            source={require('../../assets/images/login_logo.png')}
            style={styles.logo}
            resizeMode="contain"
          />
          <View style={styles.spacer38} />

          {/* Phone input */}
          <View style={styles.inputContainer}>
            <TextInput
              ref={mainViewModel.phoneFocusRef}
              style={[styles.inputText, { paddingTop: 6 }]}
              value={mainViewModel.phone}
              onChangeText={handlePhoneChange}
              placeholder="请输入手机号"
              placeholderTextColor="#ABADB2"
              maxLength={11}
              keyboardType="phone-pad"
              returnKeyType="done"
              onSubmitEditing={() => mainViewModel.phoneFocusRef.current?.blur()}
            />
          </View>

          <View style={styles.divider} />

          {/* Code input + button */}
          <View style={styles.inputContainer}>
            <View style={styles.codeRow}>
              <TextInput
                ref={mainViewModel.codeFocusRef}
                style={styles.inputText}
                value={mainViewModel.code}
                onChangeText={handleCodeChange}
                placeholder="请输入验证码"
                placeholderTextColor="#ABADB2"
                maxLength={6}
                keyboardType="phone-pad"
                returnKeyType="done"
                onSubmitEditing={() => mainViewModel.codeFocusRef.current?.blur()}
              />
              <View style={styles.codeButtonWrapper}>
                <Pressable
                  onPress={() => console.log('获取验证码')}
                  style={({ pressed }) => [
                    styles.codeButton,
                    {
                      borderColor: mainViewModel.model.obtainCodeEnable
                        ? '#407AFF'
                        : '#DCDCDE',
                      backgroundColor: 'white',
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.codeButtonText,
                      {
                        color: mainViewModel.model.obtainCodeEnable
                          ? '#267DFF'
                          : '#ABADB2',
                      },
                    ]}
                  >
                    {mainViewModel.model.obtainCodeTitle}
                  </Text>
                </Pressable>
              </View>
            </View>
          </View>

          <View style={styles.divider} />

          {/* Bottom links */}
          <View style={styles.bottomLinksContainer}>
            <View style={styles.linksRow}>
              <Pressable onPress={() => console.log('账号密码登录')}>
                <Text style={styles.linkTextPrimary}>账号密码登录</Text>
              </Pressable>
              <View style={styles.spacerFlex} />
              <Pressable onPress={() => console.log('登录遇到问题')}>
                <Text style={styles.linkTextSecondary}>登录遇到问题</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </ScrollView>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollView: {
    flex: 1,
  },
  column: {
    flexDirection: 'column',
  },
  spacer48: {
    height: 48,
  },
  spacer38: {
    height: 38,
  },
  spacerFlex: {
    flex: 1,
  },
  logo: {
    width: 155,
    height: 76,
    alignSelf: 'center',
  },
  inputContainer: {
    height: 56,
    paddingHorizontal: 24,
    justifyContent: 'center',
  },
  inputText: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#1D1E1F',
  },
  divider: {
    height: 0.5,
    backgroundColor: '#EDEDEE',
    marginHorizontal: 24,
  },
  codeRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  codeButtonWrapper: {
    flex: 1,
    alignItems: 'flex-end',
    paddingVertical: 14,
  },
  codeButton: {
    borderWidth: 0.5,
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 0,
    justifyContent: 'center',
    alignItems: 'center',
  },
  codeButtonText: {
    fontSize: 12,
  },
  bottomLinksContainer: {
    paddingHorizontal: 24,
    paddingVertical: 8,
  },
  linksRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  linkTextPrimary: {
    fontSize: 13,
    color: '#267DFF',
    fontWeight: 'bold',
  },
  linkTextSecondary: {
    fontSize: 13,
    color: '#ABADB2',
    fontWeight: 'bold',
  },
});

export default LoginMainView;
