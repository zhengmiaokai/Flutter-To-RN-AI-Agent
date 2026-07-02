import AsyncStorage from '@react-native-async-storage/async-storage';

export interface PreferencesProtocol {
  setInt(key: string, value: number): Promise<boolean>;
  getInt(key: string): Promise<number>;
  setDouble(key: string, value: number): Promise<boolean>;
  getDouble(key: string): Promise<number>;
  setBool(key: string, value: boolean): Promise<boolean>;
  getBool(key: string): Promise<boolean>;
  setString(key: string, value: string): Promise<boolean>;
  getString(key: string): Promise<string>;
}

class BasePreferences implements PreferencesProtocol {
  private static readonly sInstance: BasePreferences = new BasePreferences();

  static getInstance(): BasePreferences {
    return BasePreferences.sInstance;
  }

  async setInt(key: string, value: number): Promise<boolean> {
    await AsyncStorage.setItem(key, value.toString());
    return true;
  }

  async getInt(key: string): Promise<number> {
    const val = await AsyncStorage.getItem(key);
    return val !== null ? parseInt(val, 10) : 0;
  }

  async setDouble(key: string, value: number): Promise<boolean> {
    await AsyncStorage.setItem(key, value.toString());
    return true;
  }

  async getDouble(key: string): Promise<number> {
    const val = await AsyncStorage.getItem(key);
    return val !== null ? parseFloat(val) : 0;
  }

  async setBool(key: string, value: boolean): Promise<boolean> {
    await AsyncStorage.setItem(key, value.toString());
    return true;
  }

  async getBool(key: string): Promise<boolean> {
    const val = await AsyncStorage.getItem(key);
    return val === 'true';
  }

  async setString(key: string, value: string): Promise<boolean> {
    await AsyncStorage.setItem(key, value);
    return true;
  }

  async getString(key: string): Promise<string> {
    const val = await AsyncStorage.getItem(key);
    return val !== null ? val : '';
  }
}

export default BasePreferences;