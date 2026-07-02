import React from 'react';
import { View, Image } from 'react-native';

interface AccountLoginViewProps {
  key?: React.Key;
}

const AccountLoginView: React.FC<AccountLoginViewProps> = () => {
  return (
    <View>
      <View style={{ height: 48 }} />
      <Image
        source={require('../../assets/images/login_logo.png')}
        style={{ width: 155, height: 76 }}
        resizeMode="contain"
      />
      <View style={{ height: 38 }} />
    </View>
  );
};

export default AccountLoginView;